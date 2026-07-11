# IS09 Executor (Codex) 実装仕様書

> 本書は `M09 Executor (Codex).txt`(確定済み詳細設計書)を唯一の正とし、その実装仕様を具体化するものである。設計書に記載のない機能は追加しない。Build実行・Test実行・Lint実行・Pull Request作成のロジックは本書に一切含まない(Design Freeze監査によりTester/PR Creatorへ移管済み)。

---

## 1. モジュール概要

Executor (Codex) は、Architect が作成し Design Auditor が承認した Design Document(Approved Design)を入力として、Codex を実装エンジンに用いて実装コードとテストコードを生成するモジュールである。責務は「承認済み設計をコード・テストコードへ変換すること」に限定され、要件分析・設計・設計監査・テスト実行・Build実行・Lint実行・コードレビュー・Pull Request作成・GitHubマージは一切行わない。生成した実装は Modified Files・Generated Tests・Execution Report としてまとめられ、品質判定は行わずそのまま Tester へ引き渡される。変更対象は単一 Repository に限定される(MVP制約)。

---

## 2. ファイル構成

```text
src/executor/
├── __init__.py            # パッケージ公開シンボル(Executor, 主要dataclass)のみexport
├── executor.py             # Executor(BaseModule)本体: load_design() / implement()
├── models.py                # ImplementationContext, ImplementationResult, ExecutionReport等のdataclass定義
├── errors.py                 # Executor固有例外(Foundation errors.py/exceptions.pyを継承)
├── codex_adapter.py          # Codex外部呼び出しの唯一のアダプタ(Adapter Pattern)
├── repository_guard.py       # 単一Repository制約を強制するファイルアクセスガード
└── tests/
    ├── __init__.py
    ├── test_executor.py
    ├── test_codex_adapter.py
    └── test_repository_guard.py
```

| ファイル | 役割 |
|---|---|
| `executor.py` | 公開インターフェース`load_design()`/`implement()`を提供する唯一のエントリポイント。処理手順(Design Document読込→Repository取得→実装対象特定→コード生成→ファイル更新→テストコード生成→実装結果レポート作成)を統括する。 |
| `models.py` | Foundationの`Implementation` Domain(F01)を利用しつつ、Executor固有の作業用dataclass(`ImplementationContext`, `ImplementationResult`, `ExecutionReport`等)を定義する。 |
| `errors.py` | Foundationの`FoundationError`階層を継承したExecutor固有例外を定義する。新しい基底例外は追加せず、既存階層のサブクラスのみを追加する。 |
| `codex_adapter.py` | Codexへの外部呼び出しのみを担当するアダプタ層(F00: Adapter Pattern)。`executor.py`はCodexの呼び出し方法(API/CLI等)の詳細を知らない。 |
| `repository_guard.py` | 「Executorが変更できるのは対象Repositoryのみ」(4.4)を機械的に強制するためのパス検証ユーティリティ。対象Repositoryルート配下以外へのファイル書込みを拒否する。 |

Build/Test/Lint実行、Pull Request作成に関するファイル・モジュールは本構成に含めない(対象外)。

---

## 3. データクラス定義

FoundationのDomain Model(F01)のうち、Executorが主たる利用者となる`Implementation`を用いる。`Implementation`の共通属性(`id`, `created_at`, `updated_at`, `metadata`)はFoundation `types.py`が保証し、Executor固有属性は本書で追加定義する(Design Freeze後もtypes.py既存属性の削除・型変更は行わない。属性追加のみ)。

```python
# src/executor/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from foundation.types import Design, Implementation  # F01: Foundation Domain Model


class ChangeType:
    """ファイル変更種別(列挙の代わりにStrで簡潔に表現する)。"""
    CREATED = "created"
    MODIFIED = "modified"


@dataclass(frozen=True)
class RepositoryInfo:
    """入力`repository_information`を表す。単一Repository制約(4.4)の判定基準となる。"""
    repository_id: str
    root_path: Path
    default_branch: str


@dataclass(frozen=True)
class ModifiedFile:
    """実装により変更・作成されたファイル1件を表す。"""
    path: Path            # repository_information.root_path からの相対パス
    change_type: str      # ChangeType.CREATED / ChangeType.MODIFIED
    summary: str          # 変更内容の要約(Codexが生成した説明文)


@dataclass(frozen=True)
class GeneratedTest:
    """生成されたテストコード1件を表す。テストの実行は行わない(対象外)。"""
    path: Path             # 生成先の相対パス
    target_path: Path      # テスト対象実装ファイルの相対パス
    summary: str


@dataclass(frozen=True)
class ImplementationContext:
    """load_design()の出力。implement()への唯一の入力。"""
    workflow_id: str
    design_id: str
    approved_design: Design                 # Design Auditorが承認したDesign(F01)
    design_document: Design                 # Architectが作成した元のDesign Document(F01)
    project_context: Mapping[str, Any]
    repository_information: RepositoryInfo
    execution_plan: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ExecutionReport:
    """実装結果レポート。成果物3件(Implementation/Modified Files/Generated Tests)の要約。"""
    workflow_id: str
    design_id: str
    repository_id: str
    modified_files: tuple[ModifiedFile, ...]
    generated_tests: tuple[GeneratedTest, ...]
    summary: str
    created_at: datetime


@dataclass(frozen=True)
class ImplementationResult:
    """implement()の出力。"""
    implementation: Implementation          # F01 Domain(id/created_at/updated_at/metadataを含む)
    modified_files: tuple[ModifiedFile, ...]
    generated_tests: tuple[GeneratedTest, ...]
    execution_report: ExecutionReport
```

補足:

- `approved_design` / `design_document` はいずれもFoundation `Design` Domainのインスタンスであり、承認関連の属性(承認ステータス・承認者・承認日時等)はDesign Auditor(M08)側の詳細設計書が定義する範囲であるため、Executor側では`Design.metadata`等の既定フィールド経由で参照する読み取り専用の値として扱い、Executor独自の新規属性としては追加しない。
- `Implementation.metadata` には、Codex呼び出しに用いたモデル名・所要時間等、Secret/Token/Credentialを含まない技術情報のみを格納する。

---

## 4. クラス・関数シグネチャ

```python
# src/executor/executor.py
from __future__ import annotations

from foundation.base_module import BaseModule
from foundation.result import Result
from foundation.logger import get_logger

from executor.models import ImplementationContext, ImplementationResult
from executor.codex_adapter import CodexAdapter
from executor.repository_guard import RepositoryGuard


class Executor(BaseModule):
    """Design Document読込と実装(コード生成・テストコード生成)のみを担当する。"""

    def __init__(self, codex_adapter: CodexAdapter, repository_guard: RepositoryGuard) -> None:
        self._codex_adapter = codex_adapter
        self._repository_guard = repository_guard
        self._logger = get_logger("executor")

    def name(self) -> str:
        """BaseModule(F02)実装。"""
        ...

    def health_check(self) -> Result[bool]:
        """BaseModule(F02)実装。"""
        ...

    def load_design(
        self,
        workflow_id: str,
        approved_design: "Design",
        design_document: "Design",
        project_context: dict,
        repository_information: "RepositoryInfo",
        execution_plan: dict | None = None,
    ) -> Result[ImplementationContext]:
        """Approved Designを検証し、ImplementationContextを構築する。

        設計書 3.4 に定義された入出力: 入力 Approved Design → 出力 Implementation Context。
        承認確認・Repository単一性チェックは本メソッド内で行う。
        """
        ...

    def implement(self, context: ImplementationContext) -> Result[ImplementationResult]:
        """ImplementationContextを基にCodexで実装コード・テストコードを生成する。

        設計書 3.4 に定義された入出力: 入力 Implementation Context → 出力 Implementation Result。
        Build/Test/Lint実行、Pull Request作成は一切行わない(4.5)。
        """
        ...
```

```python
# src/executor/codex_adapter.py
from __future__ import annotations
from dataclasses import dataclass
from foundation.result import Result
from executor.models import ImplementationContext, ModifiedFile, GeneratedTest


@dataclass(frozen=True)
class CodexConfig:
    model: str
    timeout: int
    max_retry: int


class CodexAdapter:
    """Codex外部呼び出しの唯一の窓口(Adapter Pattern, F00)。"""

    def __init__(self, config: CodexConfig) -> None:
        self._config = config

    def generate_implementation(
        self, context: ImplementationContext
    ) -> Result[tuple[ModifiedFile, ...]]:
        """設計内容に基づき実装コードを生成し、変更ファイル一覧を返す。"""
        ...

    def generate_tests(
        self, context: ImplementationContext, modified_files: tuple[ModifiedFile, ...]
    ) -> Result[tuple[GeneratedTest, ...]]:
        """生成済み実装に対応するテストコードを生成する。テストの実行は行わない。"""
        ...
```

```python
# src/executor/repository_guard.py
from __future__ import annotations
from pathlib import Path
from foundation.result import Result
from executor.models import RepositoryInfo


class RepositoryGuard:
    """単一Repository制約(4.4)を強制する。"""

    def ensure_within_repository(
        self, repository_information: RepositoryInfo, target_path: Path
    ) -> Result[bool]:
        """target_pathがrepository_information.root_path配下であることを検証する。
        配下でない場合はResult[bool](success=False)を返す。
        """
        ...
```

すべての公開メソッドは `Result[T]` を戻り値とし、失敗時は `Result(success=False, value=None, error=<FoundationError系>)` を返す(F02)。

---

## 5. エラー処理

`errors.py` にて、Foundationのエラー階層(`FoundationError`)配下にExecutor固有例外を追加する。新しい基底例外は追加しない。

```python
# src/executor/errors.py
from __future__ import annotations
from foundation.errors import (
    ValidationError,
    NotFoundError,
    ExternalServiceError,
)


class DesignNotApprovedError(ValidationError):
    """承認されていないDesign Documentを実装しようとした場合に送出する(4.3)。

    - design_document に対応する approved_design が存在しない場合
    - design_document.id と approved_design が参照するdesign_idが一致しない場合
    に発生する。
    """


class DesignDocumentNotFoundError(NotFoundError):
    """入力として渡されたDesign Documentが特定できない場合に送出する。"""


class MultiRepositoryNotAllowedError(ValidationError):
    """複数Repositoryにまたがる変更を試みた場合に送出する(4.4, MVP制約)。"""


class RepositoryBoundaryViolationError(ValidationError):
    """対象Repositoryルート配下以外への書込みを試みた場合に送出する(4.4)。"""


class CodexGenerationError(ExternalServiceError):
    """Codex呼び出しが失敗した場合に送出する(外部サービスエラー)。"""
```

運用方針:

- `load_design()` は、`design_document` と `approved_design` の対応関係を検証し、承認が確認できない場合は `Result(success=False, error=DesignNotApprovedError(...))` を返す。例外はモジュール境界を越えて送出せず、`Result[T].error` に格納する(F02)。
- `implement()` は、Codex呼出し失敗を `CodexGenerationError` として、Repository境界違反を `RepositoryBoundaryViolationError` / `MultiRepositoryNotAllowedError` として `Result` に格納する。
- 設計変更が必要と判断されるケース(Architecture変更・Module追加判断等)は、Executorが自ら解決せず、`Result(success=False, error=ValidationError("設計変更が必要なためArchitectへ差し戻し"))` 相当のエラーを返すに留める(4.1)。Executorが設計を書き換えることはない。

---

## 6. ロギング仕様

`foundation.logger.get_logger("executor")` を用いる。出力形式はFoundation規約 `timestamp | module_name | level | message` に従う。

出力必須項目(4.6): `timestamp`, `workflow_id`, `design_id`, `modified_files`, `result`

```python
self._logger.info(
    "implementation completed",
    extra={
        "workflow_id": context.workflow_id,
        "design_id": context.design_id,
        "modified_files": [str(f.path) for f in modified_files],  # パスのみ、内容は出力しない
        "result": "success",
    },
)
```

Secret/Token/Credentialを出力しない実装方針:

- `project_context` / `repository_information` / Codex設定(`CodexConfig`)は**丸ごとログへ渡さない**。ログに含めてよいのは `workflow_id`, `design_id`, `repository_id`, ファイルパス一覧、`result`(success/failure文字列およびエラー種別名)のみとする。
- `Implementation.metadata` や `ExecutionReport.summary` に外部から渡された任意文字列(APIキー・トークン等を含み得る自由記述)をそのまま転記しない。ログ出力用のフィールドは上記の固定キーのみを許可するホワイトリスト方式とし、`context`や`config`オブジェクトを`str()`化してログへ渡す実装は禁止する。
- Codex呼出し失敗時のエラーメッセージに認証情報が含まれ得る場合は、`CodexGenerationError`のメッセージを定型文(例: "Codex呼び出しに失敗しました")に正規化し、詳細原因は例外の`__cause__`にのみ保持してログ本文へは出力しない。

---

## 7. Unit Testケース一覧(unittest)

`tests/test_executor.py`

- `test_name_returns_module_name`
- `test_health_check_returns_success_result`
- `test_load_design_returns_success_result_for_approved_design`
- `test_load_design_returns_design_not_approved_error_when_no_matching_approved_design`
- `test_load_design_returns_design_not_approved_error_when_design_id_mismatch`
- `test_load_design_returns_error_when_repository_information_missing`
- `test_implement_returns_implementation_result_for_valid_context`
- `test_implement_populates_execution_report_with_workflow_and_design_id`
- `test_implement_generates_tests_corresponding_to_modified_files`
- `test_implement_returns_multi_repository_not_allowed_error_when_paths_span_multiple_repositories`
- `test_implement_returns_repository_boundary_violation_error_for_path_outside_root`
- `test_implement_does_not_expose_test_execution_method`(Executorが`run_tests`等の実行系メソッドを公開しないことの構造的確認)
- `test_implement_does_not_expose_build_or_lint_execution_method`
- `test_implement_does_not_expose_pull_request_creation_method`
- `test_implement_wraps_codex_failure_as_codex_generation_error`
- `test_load_design_and_implement_never_raise_uncaught_exception`(境界を越えて例外を送出しないことの確認)

`tests/test_codex_adapter.py`

- `test_generate_implementation_returns_modified_files_on_success`
- `test_generate_implementation_returns_error_result_on_external_failure`
- `test_generate_tests_returns_generated_tests_on_success`
- `test_generate_tests_returns_error_result_on_external_failure`
- `test_codex_adapter_does_not_log_credentials`

`tests/test_repository_guard.py`

- `test_ensure_within_repository_returns_true_for_path_inside_root`
- `test_ensure_within_repository_returns_false_for_path_outside_root`
- `test_ensure_within_repository_returns_false_for_path_traversal_attempt`(`../`等によるRepository外アクセス試行)
- `test_ensure_within_repository_rejects_second_repository_root`(単一Repository制約: 別Repositoryのroot_pathを混在させた場合に拒否されることの確認)

---

## 8. MVP範囲の明記

設計書5.3節(重厚壮大化監査)により、以下はMVP対象外であり、本モジュールには実装しない。

- 自動マージ
- 自動リリース
- マルチRepository実装(Executorが同時に変更できるRepositoryは常に1つ)
- 自動デプロイ
- 自動ロールバック
- Blue/Green Deployment
- Canary Deployment
- Infrastructure変更
- Database Migration管理
- **Executor内でのテスト実行・Build実行・Lint実行・Pull Request作成の内製化**

特に以下はDesign Freeze監査によりTester/PR Creatorへ責務が一本化されたため、本モジュールの範囲外であることを明記する。

- テスト実行(Testerが担当)
- Build実行(Testerが担当)
- Lint実行(Testerが担当)
- Pull Request作成(PR Creatorが担当、Testerの品質ゲートPASS後)
- コードレビュー・品質判定・マージ判定(Executorは行わない)

公開インターフェースは `load_design()` / `implement()` の2つのみとし、`validate()` や `create_pull_request()` に相当するメソッドは実装しない。
