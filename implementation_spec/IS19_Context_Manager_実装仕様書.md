# IS19 Context Manager 実装仕様書

- 対象設計書: `M19 Context Manager.txt`（Design Freeze v1.0）
- 参照先設計書: `M03_Knowledge_Manager_詳細設計.md`（Knowledge取得: `get()`/`search()`/`list_documents()`）、`M17 Configuration Manager.txt`（Configuration取得。呼び出し規約は `M00 Foundation.txt` 3.5節 F03 `ConfigurationClient`）、`M20 GitHub Manager.txt`（Repository Context取得: `build_repository_context()`）
- 対象バージョン: `DESIGN_VERSION = "v1.0"`
- 実装言語: Python 3.13
- 配置先: `src/context_manager/`

本書は M19 Context Manager の詳細設計書を実装可能な粒度に具体化したものであり、設計書に記載のない機能・APIを追加しない。設計書の記述と本書が矛盾する場合は設計書を正とする。設計書の記述だけでは実装粒度に不足する箇所（後述の「実装判断」注記）は、Foundation(M00)・Knowledge Manager(M03)・GitHub Manager(M20)の確定済み設計と矛盾しない最小限の補完として明示する。

---

## 1. モジュール概要

Context Manager は、AI Development Pipeline において Planner・Architect・Executor(Codex)・Reviewer・Weekly Reviewer(Fable) の各ワークフローへ渡す Context を生成・選択・組み立て・検証・提供するモジュールである。Knowledge Manager(M03)・Configuration Manager(M17)・GitHub Manager(M20) の3モジュールのみを情報の唯一の参照元とし、Repository の解析、Knowledge・Configurationの内容変更、コード生成、AI実行、Workflow制御は一切行わない。Workflowごとに必要最小限の情報だけを選択して `AI Context` として組み立て、`Context Metadata` と `Context Version` を付与したうえで提供し、Knowledge本文・Repository情報を自身のストアとして複製・保持しない（都度、参照元モジュールを呼び出して取得する）。

---

## 2. ファイル構成

`src/context_manager/` 配下に以下を配置する。

| ファイル | 役割 |
|---|---|
| `__init__.py` | パッケージの公開API（`ContextManager`、`types.py` の公開dataclass/Enum、`errors.py` の例外クラス）を re-export する。新規ロジックは持たない。 |
| `types.py` | Context Manager 固有の dataclass・Enum を定義する（3章参照）。Foundation(F01)の `Context` Domainを継承・利用する。 |
| `ports.py` | Knowledge Manager(M03)・GitHub Manager(M20) の呼び出し先を`typing.Protocol`で抽象化した最小限のポート定義（`KnowledgeManagerPort`, `GitHubManagerPort`）。実体は各モジュールの実装を注入する。Configuration Managerは Foundation の `ConfigurationClient`(F03) を直接利用するため、ここには含めない。 |
| `errors.py` | Foundation(`foundation.errors`)の例外階層を継承した Context Manager 固有例外を定義する（5章参照）。 |
| `collector.py` | 処理フローの「Collect」段階。`ports.py` 経由で Knowledge Manager・GitHub Manager を呼び出し、Foundation `ConfigurationClient` 経由で Configuration を取得し、`CollectedContext` を組み立てる。 |
| `selector.py` | 処理フローの「Select」段階。Workflow種別ごとに必要な項目のみを `CollectedContext` から選び `SelectedContext` を生成する（3.3節のWorkflow別Context対応表 `WORKFLOW_FIELD_MAP` を保持）。 |
| `validator.py` | 処理フローの「Validate」段階。`AI Context` の不足情報を確認し `ValidationResult` を返す。 |
| `store.py` | `get()` 実装のための最小限のインメモリストア（`ContextStore`）。Workflow ID をキーに直近ビルド済みの `AIContext` のみを保持し、Knowledge本文・Repository情報そのものをキャッシュする責務は持たない。 |
| `manager.py` | 公開インターフェース（`build()`/`select()`/`validate()`/`get()`）を実装する `ContextManager`（`BaseModule`継承）本体。Collect→Select→Build→Validateの一連のオーケストレーションを行う。 |
| `logging_utils.py` | 4.6節のログ項目（`workflow_id`, `workflow_type`, `context_version`, `context_size`, `validation_result`）を組み立てて `get_logger()` 経由で出力するための薄いヘルパー。Context本文・Knowledge本文・Repository情報・Secretを引数に取らない設計とし、誤って本文を渡せないようにする。 |
| `tests/` | unittest によるテスト一式（7章参照）。 |

---

## 3. データクラス定義

### 3.1 Foundation Domain の利用

Context Manager は Foundation(F01) の `Context` dataclass（`id: str`, `created_at: datetime`, `updated_at: datetime`, `metadata: dict[str, Any]`）をそのまま継承し、モジュール固有属性を追加する（IS00 4.3節の方針と同様、Foundation側の `types.py` は変更しない）。

### 3.2 Enum・スコープ関連

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from foundation.types import Context
from foundation.utils import generate_id, utc_now


class WorkflowType(str, Enum):
    """設計書 3.3節『Workflow別Context』および適用対象(1章)に定義された5種のみ。"""
    PLANNER = "planner"
    ARCHITECT = "architect"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    WEEKLY_REVIEWER = "weekly_reviewer"


@dataclass
class WorkflowScope:
    """GitHub Manager `build_repository_context()` へ渡すスコープ情報（設計書3.5 GitHub Managerの入力『Workflow Scope』に対応）。

    `repository` はGitHub Manager実装仕様書(IS20)がGitHub API呼び出しの必須共通入力として
    定めたRepository識別子(owner/repo形式)。本仕様書の初版には無かったが、IS20との統合時に
    判明した不足フィールドとして追加した(CHANGELOG.md参照)。既定値""は後方互換用。
    """
    workflow_id: str
    workflow_type: WorkflowType
    target_paths: list[str] = field(default_factory=list)
    repository: str = ""
```

### 3.3 リクエスト・収集・選択結果

> **実装判断（要確認事項）**: 設計書 3.5節の `build()`/`select()` の入出力表は代表入力（Workflow Type）のみを記載する簡略表記である。一方 3.1節は Context Manager 全体の入力として `workflow_type / knowledge / configuration / repository_context / execution_plan / user_instruction` を列挙しており、Execution Plan は Planner から、User Instruction は Command Router からの提供とされ、Knowledge Manager・Configuration Manager・GitHub Managerのように Context Manager が能動的に問い合わせる「参照元」とは区別されている（4.4/4.5節はKnowledge/Configurationの参照のみを規定し、Execution Plan/User Instructionの取得元には言及していない）。そのため本書では、呼び出し元（Command RouterないしWorkflow制御層）が `build()` 呼び出し時に Execution Plan・User Instruction 等の「呼び出し時点で既に生成済みの上流成果物」を `ContextRequest` としてまとめて渡す構成としてAPIを具体化する。Reviewer向けの Implementation・Test Report、Weekly Reviewer向けの Merged Pull Requests・Review Reports・Technical Debt Reports についても、設計書3.1節の入力表に明示的な取得元が定義されていない（Knowledge Manager/Configuration Manager/GitHub Managerのいずれの管理対象にも該当しない）ため、Execution Plan/User Instructionと同様に「呼び出し元が既に保有する成果物」として `ContextRequest` 経由で受け渡すものとし、Context Manager側で新たな取得手段を発明しない。

```python
@dataclass
class ContextRequest:
    """build() の入力。Context Manager が能動的に参照するのは
    Knowledge Manager / Configuration Manager / GitHub Manager の3モジュールのみであり、
    以下フィールドは呼び出し元（Command Router等）が既に保有する成果物をそのまま渡す。"""
    workflow_id: str
    workflow_type: WorkflowType
    workflow_scope: WorkflowScope
    execution_plan: Any | None = None          # Planner(M06)成果物。具体型はM06側で定義、本モジュールでは不透明値として扱う
    user_instruction: str | None = None        # Command Router経由のユーザー指示
    implementation: Any | None = None          # Reviewer Context用。Executor(M09)成果物（不透明値）
    test_report: Any | None = None             # Reviewer Context用。Tester(M10)成果物（不透明値）
    merged_pull_requests: list[Any] = field(default_factory=list)   # Weekly Reviewer Context用（不透明値）
    review_reports: list[Any] = field(default_factory=list)         # Weekly Reviewer Context用（不透明値）
    technical_debt_reports: list[Any] = field(default_factory=list) # Weekly Reviewer Context用（不透明値）


@dataclass
class CollectedContext:
    """処理フロー『Collect』段階の出力。Workflow種別に関わらず収集可能な全情報を保持する中間データ。"""
    knowledge_documents: list[Any] = field(default_factory=list)   # Knowledge Manager `KnowledgeDocument` のリスト
    repository_context: Any | None = None                          # GitHub Manager `build_repository_context()` の戻り値
    environment: str | None = None                                  # ConfigurationClient経由で取得（3.4節注記参照）
    execution_plan: Any | None = None
    user_instruction: str | None = None
    implementation: Any | None = None
    test_report: Any | None = None
    merged_pull_requests: list[Any] = field(default_factory=list)
    review_reports: list[Any] = field(default_factory=list)
    technical_debt_reports: list[Any] = field(default_factory=list)


@dataclass
class SelectedContext:
    """処理フロー『Select』段階の出力。設計書3.3節のWorkflow別Context対応表に従い、
    workflow_typeに必要な項目のみをNone/空以外で保持する（不要な項目は追加しない、設計書4.2節）。"""
    workflow_type: WorkflowType
    business_goal: Any | None = None            # Knowledge Managerの「Business Goal」カテゴリ文書
    user_instruction: str | None = None
    knowledge: list[Any] = field(default_factory=list)              # Planner向け「Knowledge」自由項目
    requirements: list[Any] = field(default_factory=list)           # Architect向け「Requirements」
    architecture_principles: list[Any] = field(default_factory=list)
    execution_plan: Any | None = None
    repository_context: Any | None = None
    coding_rules: list[Any] = field(default_factory=list)
    design_documents: list[Any] = field(default_factory=list)
    implementation: Any | None = None
    test_report: Any | None = None
    merged_pull_requests: list[Any] = field(default_factory=list)
    review_reports: list[Any] = field(default_factory=list)
    technical_debt_reports: list[Any] = field(default_factory=list)
```

### 3.4 成果物（AI Context / Context Metadata / Context Version）

```python
@dataclass
class ContextMetadata:
    """設計書3.4節『Context Metadata』。ログ4.6節の記録項目と対応させる。"""
    workflow_id: str
    workflow_type: WorkflowType
    context_version: str
    built_at: datetime = field(default_factory=utc_now)
    environment: str | None = None   # 3.4節注記参照


@dataclass
class AIContext(Context):
    """設計書3.4節『AI Context』。Foundation `Context`(F01)の共通属性(id/created_at/updated_at/metadata)を継承し、
    Context Manager固有属性を追加する。"""
    workflow_id: str = ""
    workflow_type: WorkflowType = WorkflowType.PLANNER
    selected_context: SelectedContext | None = None
    context_metadata: ContextMetadata | None = None
    context_version: str = ""


@dataclass
class ValidationResult:
    """validate()の出力『Validation Result』。"""
    is_valid: bool
    missing_fields: list[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=utc_now)
```

> **実装判断（要確認事項）**: 「Context Version」の採番規則は設計書に明記がない。本書ではKnowledge Manager(M03 3.4節)のバージョン管理方針に倣い、`ContextStore`（3.5節参照）がWorkflow IDごとに単調増加する版番号を管理し、`build()`のたびに`f"v{n}"`形式で採番する方針を採用する。この解釈は実装上の必要性からの補完であり、設計書の明文規定ではない。

### 3.5 ストア（`ContextStore`）

```python
@dataclass
class ContextStore:
    """get()実装のための最小限のインメモリ保持。Context Manager自身が生成したAIContextの
    『最新版のみ』をworkflow_id単位で保持する（Knowledge本文・Repository情報を複製・保持するものではない）。"""
    _latest: dict[str, AIContext] = field(default_factory=dict)
    _version_counters: dict[str, int] = field(default_factory=dict)

    def next_version(self, workflow_id: str) -> str: ...
    def save(self, context: AIContext) -> None: ...
    def get(self, workflow_id: str) -> AIContext | None: ...
```

---

## 4. クラス・関数シグネチャ

### 4.1 `ports.py`（依存先の抽象化）

```python
from typing import Any, Protocol

from foundation.result import Result


class KnowledgeManagerPort(Protocol):
    """Knowledge Manager(M03) 3.3節の公開インターフェースのうち、
    Context Managerが利用する参照専用メソッドのみを抽出する（4.4節: 参照のみ）。"""

    def get(self, document_id: str) -> Result[Any]:
        """`KnowledgeDocument` 単体取得。"""

    def search(self, keyword: str) -> Result[list[Any]]:
        """キーワード検索。Planner Context の自由項目『Knowledge』等に利用する。"""

    def list_documents(self, category: str) -> Result[list[Any]]:
        """カテゴリ単位の一覧取得。Business Goal・MVP Policy・Architecture Principles・
        Coding Rules 等、M03 3.1節のカテゴリ単位の取得に利用する。"""


class GitHubManagerPort(Protocol):
    """GitHub Manager(M20) 3.5節の公開インターフェースのうち、
    Context Managerが利用する `build_repository_context()` のみを抽出する。"""

    def build_repository_context(
        self, repository: str, workflow_scope: "WorkflowScope"
    ) -> Result[Any]:
        """指定Workflowに必要なRepository情報のみを取得する（M20 3.3節: Repository全体は返却しない）。

        `repository` はIS20仕様書が全メソッド共通の必須入力として定めるRepository識別子。
        """
```

### 4.2 `collector.py`

```python
from foundation.interfaces import ConfigurationClient
from foundation.result import Result

from context_manager.ports import GitHubManagerPort, KnowledgeManagerPort
from context_manager.types import CollectedContext, ContextRequest


MODULE_NAME = "context_manager"


def collect(
    request: ContextRequest,
    knowledge_manager: KnowledgeManagerPort,
    github_manager: GitHubManagerPort,
    configuration_client: type[ConfigurationClient],
) -> Result[CollectedContext]:
    """Knowledge Manager・GitHub Manager・ConfigurationClient(F03)を都度呼び出し、
    CollectedContextを組み立てる。いずれかの呼び出しが失敗した場合、
    Result(success=False, error=...)を返し、以降の処理へ進めない（Safety原則）。
    Knowledge/Repository情報を内部にキャッシュせず、呼び出しごとに再取得する（設計書4.4/4.5節）。"""
```

- `knowledge_manager.list_documents("business_goal")` 等でカテゴリ別文書を取得し、必要に応じ `knowledge_manager.search(keyword)` を併用する。
- `github_manager.build_repository_context(request.workflow_scope.repository, request.workflow_scope)` でRepository Contextを取得する。
- `configuration_client.get(MODULE_NAME, "system.environment")` で`ContextMetadata.environment`用の値のみを取得する（4.3節注記のとおり、設計書はConfigurationの具体的な利用項目を列挙していないため、Configuration Manager(M17) 3.2節『System』カテゴリのうち、追跡用途に必要な`environment`のみを最小限利用する）。

### 4.3 `selector.py`

```python
from context_manager.types import CollectedContext, SelectedContext, WorkflowType

# 設計書 3.3節の対応をそのまま定数化する。
WORKFLOW_FIELD_MAP: dict[WorkflowType, frozenset[str]] = {
    WorkflowType.PLANNER: frozenset({"business_goal", "user_instruction", "knowledge"}),
    WorkflowType.ARCHITECT: frozenset({"requirements", "knowledge", "architecture_principles"}),
    WorkflowType.EXECUTOR: frozenset({"execution_plan", "repository_context", "coding_rules", "design_documents"}),
    WorkflowType.REVIEWER: frozenset({"implementation", "design_documents", "test_report", "business_goal"}),
    WorkflowType.WEEKLY_REVIEWER: frozenset({"merged_pull_requests", "review_reports", "business_goal", "technical_debt_reports"}),
}


def select(workflow_type: WorkflowType, collected: CollectedContext) -> SelectedContext:
    """WORKFLOW_FIELD_MAPに列挙された項目のみをCollectedContextから転記し、
    それ以外のフィールドはNone/空のままとする（設計書4.2節: 不要な情報を追加しない）。
    business_goal / knowledge / requirements / architecture_principles / coding_rules は、
    collected.knowledge_documents（Knowledge Manager `KnowledgeDocument.category`, M03 3.2節）を
    カテゴリ値で振り分けて割り当てる。design_documentsは同様にArchitecture Principlesカテゴリ由来の
    文書を割り当てる（3.3節注記のとおり、設計書はDesign Documentsの専用取得元を定めていないため、
    M03 3.1節の既存カテゴリで代替する）。"""
```

### 4.4 `validator.py`

```python
from context_manager.selector import WORKFLOW_FIELD_MAP
from context_manager.types import AIContext, ValidationResult


def validate(context: AIContext) -> ValidationResult:
    """WORKFLOW_FIELD_MAP[context.workflow_type] に列挙された必須項目が
    SelectedContext上でNone/空でないかを確認し、不足があれば missing_fields に記録する。
    Context本文はここでのみ参照し、戻り値(ValidationResult)には含めない。"""
```

### 4.5 `manager.py`

```python
from foundation.base_module import BaseModule
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result

from context_manager.errors import (
    ContextConfigurationRetrievalError,
    ContextNotFoundError,
    ContextValidationError,
    KnowledgeRetrievalError,
    RepositoryContextRetrievalError,
)
from context_manager.ports import GitHubManagerPort, KnowledgeManagerPort
from context_manager.store import ContextStore
from context_manager.types import (
    AIContext,
    ContextMetadata,
    ContextRequest,
    SelectedContext,
    ValidationResult,
    WorkflowType,
)

logger = get_logger("context_manager")


class ContextManager(BaseModule):
    def __init__(
        self,
        knowledge_manager: KnowledgeManagerPort,
        github_manager: GitHubManagerPort,
        configuration_client: type[ConfigurationClient],
        store: ContextStore | None = None,
    ) -> None: ...

    def name(self) -> str:
        """'context_manager' を返す。"""

    def health_check(self) -> Result[bool]:
        """依存先3モジュールへの疎通確認は行わず、自身の内部状態（store初期化済み等）のみを確認する
        （設計書2.2節: Repository解析・Knowledge管理・Configuration管理はContext Managerの責務外）。"""

    def build(self, request: ContextRequest) -> Result[AIContext]:
        """設計書3.5節 build()。Collect→Select→組み立て→Validateを順に実行し、
        Validate結果に関わらずAIContextをResult[AIContext]として返す
        （不足がある場合はContext自体は返しつつ、4.6節のvalidation_resultログでNGを記録する）。
        Collect段階でいずれかの参照元呼び出しが失敗した場合は、その時点で
        Result(success=False, error=KnowledgeRetrievalError|ContextConfigurationRetrievalError|RepositoryContextRetrievalError)
        を返す。"""

    def select(self, workflow_type: WorkflowType, request: ContextRequest) -> Result[SelectedContext]:
        """設計書3.5節 select()。内部でcollector.collect()を実行したうえでselector.select()を適用する
        単独呼び出し用の公開API（build()からも内部的に利用される）。"""

    def validate(self, context: AIContext) -> Result[ValidationResult]:
        """設計書3.5節 validate()。validator.validate()を呼び出しResultへラップする。"""

    def get(self, workflow_id: str) -> Result[AIContext]:
        """設計書3.5節 get()。ContextStoreから直近ビルド済みのAIContextを取得する。
        存在しない場合 Result(success=False, error=ContextNotFoundError(...)) を返す。"""
```

- Knowledge Manager(M03)への依存呼び出し: `KnowledgeManagerPort.get()` / `.search()` / `.list_documents()`（4.4節: 参照専用）。
- Configuration Manager(M17)への依存呼び出し: Foundation `ConfigurationClient.get(module_name="context_manager", key=...)`（F03の呼び出し規約、4.5節: 参照専用）。
- GitHub Manager(M20)への依存呼び出し: `GitHubManagerPort.build_repository_context(workflow_scope)`（4.3節: Repositoryを解析しない、提供されたRepository Contextのみ利用）。

---

## 5. エラー処理

Foundation(`foundation.errors`)の例外階層をそのまま利用し、Context Manager固有の新しい「基底例外」（`FoundationError`直下の兄弟クラス）は追加しない（M00 3.6節の制約）。既存の`FoundationError`サブクラスをさらに継承する形で `errors.py` に定義する。

```python
from foundation.errors import ConfigurationError, ExternalServiceError, NotFoundError, ValidationError


class ContextNotFoundError(NotFoundError):
    """get(workflow_id) に対応するAIContextが存在しない場合。"""


class ContextValidationError(ValidationError):
    """未定義のworkflow_typeが指定された場合、またはvalidate()呼び出し自体の入力不正。"""


class KnowledgeRetrievalError(ExternalServiceError):
    """Knowledge Manager(M03) の get()/search()/list_documents() 呼び出しが失敗した場合。"""


class ContextConfigurationRetrievalError(ConfigurationError):
    """ConfigurationClient.get() 呼び出しが失敗した場合。"""


class RepositoryContextRetrievalError(ExternalServiceError):
    """GitHub Manager(M20) の build_repository_context() 呼び出しが失敗した場合。"""
```

- 各例外は `Result(success=False, error=...)` として公開API境界（`build()`/`select()`/`validate()`/`get()`）から返却し、例外を呼び出し元へ送出しない（F02 `Result[T]` パターン）。
- `validate()` はValidationResult自体が`is_valid=False`であることと、API呼び出し自体の失敗（`ContextValidationError`）を区別する。前者は正常系の戻り値（`Result(success=True, value=ValidationResult(is_valid=False, ...))`）、後者は異常系（`Result(success=False, error=ContextValidationError(...))`）とする。

---

## 6. ロギング仕様

- `get_logger("context_manager")`（Foundation `foundation.logger.get_logger`）を各ファイルの先頭でモジュールレベルに1回だけ取得し、使い回す。
- 設計書4.6節の記録項目に厳密に従い、以下のみをログ出力する。

```text
timestamp           # loggerのFormatterが自動付与（Foundation LOG_FORMAT）
workflow_id
workflow_type
context_version
context_size
validation_result
```

- `context_size` は Context本文を出力せずにサイズ感のみを記録するため、`SelectedContext` の非None/非空フィールド数（`sum(1 for v in dataclasses.asdict(selected).values() if v not in (None, [], ""))`程度の単純な件数）を用いる。本文の文字列化・シリアライズは行わない。
- `logging_utils.py` に以下のヘルパーを定義し、呼び出し側がContext本文を誤って渡せないよう引数をプリミティブ型のみに限定する。

```python
def log_build_result(
    workflow_id: str,
    workflow_type: WorkflowType,
    context_version: str,
    context_size: int,
    validation_result: bool,
) -> None:
    """logger.info("workflow_id=%s workflow_type=%s context_version=%s context_size=%d validation_result=%s", ...) を出力する。"""
```

- Context本文・Knowledge本文・Repository情報・Secretはいかなるログレベルでも出力しない（設計書4.6節の絶対制約）。例外メッセージ（`errors.py`各クラス）にもこれらを含めない。

---

## 7. Unit Testケース一覧（unittest）

設計書には専用の「テスト観点」章がないため、2章（責務）・3章（Design/公開インターフェース）・4章（Constraints）を根拠にテスト観点を導出する。`context_manager/tests/` にファイル単位で配置する。

### 7.1 `test_types.py`

- `test_ai_context_inherits_foundation_context_common_fields`
- `test_ai_context_default_workflow_type_is_valid_enum_member`
- `test_selected_context_defaults_all_optional_fields_to_empty`
- `test_context_metadata_built_at_defaults_to_utc_now`
- `test_validation_result_missing_fields_defaults_to_empty_list`
- `test_workflow_scope_target_paths_defaults_to_empty_list`

### 7.2 `test_ports.py`

- `test_knowledge_manager_port_accepts_conforming_fake_implementation`
- `test_github_manager_port_accepts_conforming_fake_implementation`

### 7.3 `test_collector.py`

- `test_collect_calls_knowledge_manager_list_documents_for_required_categories`
- `test_collect_calls_github_manager_build_repository_context_with_workflow_scope`
- `test_collect_calls_configuration_client_get_for_environment_only`
- `test_collect_returns_failure_result_when_knowledge_manager_call_fails`
- `test_collect_returns_failure_result_when_github_manager_call_fails`
- `test_collect_returns_failure_result_when_configuration_client_call_fails`
- `test_collect_does_not_cache_knowledge_documents_across_calls`

### 7.4 `test_selector.py`

- `test_select_for_planner_includes_only_business_goal_user_instruction_knowledge`
- `test_select_for_architect_includes_only_requirements_knowledge_architecture_principles`
- `test_select_for_executor_includes_only_execution_plan_repository_context_coding_rules_design_documents`
- `test_select_for_reviewer_includes_only_implementation_design_documents_test_report_business_goal`
- `test_select_for_weekly_reviewer_includes_only_merged_prs_review_reports_business_goal_technical_debt_reports`
- `test_select_excludes_fields_not_in_workflow_field_map`

### 7.5 `test_validator.py`

- `test_validate_returns_valid_when_all_required_fields_for_workflow_are_present`
- `test_validate_returns_invalid_with_missing_fields_when_required_field_is_none`
- `test_validate_returns_invalid_with_missing_fields_when_required_list_field_is_empty`
- `test_validate_does_not_flag_fields_outside_workflow_field_map`

### 7.6 `test_store.py`

- `test_store_save_and_get_round_trip_returns_latest_context`
- `test_store_get_returns_none_for_unknown_workflow_id`
- `test_store_next_version_increments_per_workflow_id`
- `test_store_next_version_is_independent_across_different_workflow_ids`

### 7.7 `test_manager.py`

- `test_name_returns_context_manager`
- `test_health_check_returns_success_result_bool`
- `test_build_returns_ai_context_with_incremented_context_version`
- `test_build_returns_failure_result_when_knowledge_manager_call_fails`
- `test_build_returns_failure_result_when_github_manager_call_fails`
- `test_build_returns_failure_result_when_configuration_client_call_fails`
- `test_build_stores_result_retrievable_via_get`
- `test_select_public_method_returns_selected_context_for_given_workflow_type`
- `test_validate_public_method_wraps_validator_result`
- `test_get_returns_failure_result_with_context_not_found_error_when_absent`
- `test_get_returns_latest_built_context_for_known_workflow_id`
- `test_build_never_forwards_raw_knowledge_document_bodies_to_logger`

### 7.8 `test_errors.py`

- `test_context_not_found_error_is_not_found_error_subclass`
- `test_context_validation_error_is_validation_error_subclass`
- `test_knowledge_retrieval_error_is_external_service_error_subclass`
- `test_context_configuration_retrieval_error_is_configuration_error_subclass`
- `test_repository_context_retrieval_error_is_external_service_error_subclass`

### 7.9 `test_logging.py`

- `test_log_build_result_outputs_required_fields_only`
- `test_log_build_result_accepts_only_primitive_arguments`
- `test_log_build_result_does_not_accept_context_object_as_argument`

---

## 8. MVP範囲の明記

設計書 5.3節（重厚壮大化監査）にて対象外・削除済みとされた以下の機能は、本実装仕様の対象外とし、Context Managerには実装しない。

- RAG
- Embedding Search
- Vector Database
- Semantic Search
- AI Context Compression
- Token Optimization
- Long-term Memory
- Multi-Agent Context Sharing

また、以下も Context Manager の責務外（設計書2.2節・4章）であり、本仕様書の実装対象に含めない。

- Knowledge管理（Knowledge Manager, M03の責務。Context Managerは`get()`/`search()`/`list_documents()`経由の参照のみ）
- Configuration管理（Configuration Manager, M17の責務。Context Managerは`ConfigurationClient`経由の参照のみ）
- Repository解析（GitHub Manager, M20の責務。Context Managerは`build_repository_context()`が返すRepository Contextのみ利用し、Repository全体・差分解析・依存関係分析は行わない）
- コード生成
- AI実行
- Workflow制御

Context Managerは、`build()`/`select()`/`validate()`/`get()` の4公開APIと、その内部段階（Collect/Select/Build/Validate）の実装、および Knowledge Manager・Configuration Manager・GitHub Manager の3モジュールへの参照専用呼び出しの提供のみを実装範囲とする。
