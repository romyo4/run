# IS03 Knowledge Manager 実装仕様書

> 本書は `M03_Knowledge_Manager_詳細設計.md`(Design Freeze v1.0、旧M18統合済み)を唯一の正とし、
> `M00 Foundation.txt` が定義する F00〜F03 を前提として実装レベルまで具体化したものである。
> 設計書に明記のない機能(Vector Database・Semantic Search等)は一切追加しない。

---

## 0. 設計上の補足・確認事項(実装前に明示しておくべき解釈)

設計書の記述だけでは実装粒度まで一意に決まらない箇所が2点ある。いずれも**新機能の追加ではなく**、設計書の既存記述(3.2/3.4/3.5)を矛盾なく実装するための解釈である。Architect/Reviewerの確認を推奨する。

1. **`get()` と `get_latest()` の違い**(3.3節)
   設計書は両者とも入力 `document_id` / 出力 `Result[KnowledgeDocument]` で同一シグネチャに見えるが、3.4節「最新版を既定で利用」「必要に応じて過去版参照可能」と整合させるため、以下のように役割を分離する。
   - `get_latest(document_id)`: 常にバージョン番号が最大の版を返す。
   - `get(document_id)`: `document_id` に過去版参照(3.4)のための版指定が含まれる場合はその版を返し、含まれない場合は `get_latest()` と同じ結果(既定=最新版)を返す。
   version指定を含まない通常利用では両者は同じ結果になる。

2. **`create_version()` の権限チェック**(3.3/3.5節)
   3.5節は「更新は Planner・Architect・Reviewerのみ許可する」と定めるが、`update()` は入力が `KnowledgeDocument`(内部に `updated_by` を持つ)であるため呼び出し元ロールを検証できる一方、`create_version()` は入力が `document_id, content` のみであり、設計書のシグネチャ通りに実装すると呼び出し元ロールを受け取る手段がない。
   本仕様では**設計書のシグネチャを変更しない**ことを優先し、`create_version()` 自体では権限判定を行わず、権限制御は `update()` に一元化する(`create_version()` は Planner/Architect/Reviewer 用のワークフローから `update()` 経由でのみ呼び出される運用を前提とする)。この前提の是非はArchitectの確認事項として残す。

---

## 1. モジュール概要

Knowledge Manager(M03)は、AI Development PipelineにおいてBusiness Goal・MVP方針・設計原則・開発ルール・コーディングルールなど、AIエージェント各モジュールが継続的に参照すべき知識(Knowledge)を一元管理し、取得・検索・更新・バージョン管理機能として提供する単一責務モジュールである。Knowledgeは「カテゴリ・タイトル・本文・バージョン」の構造化形式でのみ保持し、Context生成(Context Managerの責務)・Configuration管理・Workflow制御・Repository情報は一切扱わない。更新操作はPlanner・Architect・Reviewerにのみ許可され、Executor・Context Manager等は参照専用(read-only)となる。MVPではMarkdownファイルを知識ソースとし、キーワード一致による検索のみを提供し、Vector Database・Embedding・Knowledge Graph等は対象外とする。

---

## 2. ファイル構成

```text
src/knowledge_manager/
├── __init__.py            # パッケージ公開API定義。KnowledgeManager/KnowledgeDocument等の再エクスポート
├── models.py               # KnowledgeDocument dataclass, KnowledgeCategory Enum, KnowledgeStatus Enum
├── exceptions.py            # Foundationのエラー階層を継承するM03固有例外(バージョン競合・整合性エラー)
├── permissions.py           # 更新許可ロール定義(Planner/Architect/Reviewer)と権限判定関数
├── markdown_loader.py        # Markdownファイル→KnowledgeDocument変換(load()の実処理、4.3構造検証を含む)
├── store.py                 # KnowledgeStore: 文書と全バージョン履歴のインメモリ/ファイル永続化管理
├── search_index.py           # search()のキーワード一致検索(単純部分一致、Embedding等は使用しない)
├── knowledge_manager.py       # KnowledgeManager(BaseModule)本体。公開インターフェース7メソッドを実装
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_markdown_loader.py
    ├── test_store.py
    ├── test_search_index.py
    ├── test_permissions.py
    └── test_knowledge_manager.py
```

Foundation(`foundation.result.Result`, `foundation.errors.*`, `foundation.base_module.BaseModule`, `foundation.logger.get_logger`, `foundation.types.Knowledge` 等)は既存の共有パッケージとして`import`のみ行い、本モジュール配下には複製しない。

---

## 3. データクラス定義

### 3.1 KnowledgeCategory(Enum)

設計書3.1節の「管理対象文書」カテゴリをそのままEnum化する(新規カテゴリの追加はしない)。

```python
# src/knowledge_manager/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class KnowledgeCategory(str, Enum):
    """設計書 3.1 の管理対象文書カテゴリ。"""

    BUSINESS_GOAL = "business_goal"
    MVP_POLICY = "mvp_policy"
    ARCHITECTURE_PRINCIPLES = "architecture_principles"
    DEVELOPMENT_RULES = "development_rules"
    CODING_RULES = "coding_rules"


class KnowledgeStatus(str, Enum):
    """設計書 3.4 バージョン管理(最新版を既定利用/過去版参照可能)を表現する最小限のステータス。"""

    CURRENT = "current"
    ARCHIVED = "archived"
```

### 3.2 KnowledgeDocument(dataclass)

Foundation(F01)の `Knowledge` Domainが持つ共通属性(`id`, `created_at`, `updated_at`, `metadata`)を土台に、設計書3.2節の固有属性を追加する。`content` は設計書3.2の構造図には明記されていないが、4.3節「Category/Title/Content/Version」の構造化必須要件を満たすために必須フィールドとする。

```python
# src/knowledge_manager/models.py（続き）

@dataclass
class KnowledgeDocument:
    # --- Foundation Knowledge Domain 共通属性 (F01) ---
    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    # --- M03 固有属性 (設計書 3.2 / 4.3) ---
    document_id: str = ""
    category: KnowledgeCategory = KnowledgeCategory.DEVELOPMENT_RULES
    title: str = ""
    content: str = ""
    version: int = 1
    status: KnowledgeStatus = KnowledgeStatus.CURRENT
    tags: list[str] = field(default_factory=list)
    updated_by: str = ""
    content_hash: str = ""
```

- `id`: Foundation共通のオブジェクト内部ID。
- `document_id`: 設計書3.3の各インターフェースが入力として受け取る業務上の文書識別子。
- `updated_by`: 更新者のロール名(`"planner"` / `"architect"` / `"reviewer"` 等)。`update()` の権限判定に用いる(4.6・3.5節)。
- `content_hash`: 整合性エラー検知(4.6節)のためのハッシュ値。

---

## 4. クラス・関数シグネチャ

### 4.1 KnowledgeManager本体

```python
# src/knowledge_manager/knowledge_manager.py
from __future__ import annotations

from logging import Logger
from pathlib import Path

from foundation.base_module import BaseModule
from foundation.result import Result

from knowledge_manager.models import KnowledgeCategory, KnowledgeDocument
from knowledge_manager.store import KnowledgeStore


class KnowledgeManager(BaseModule):
    """Knowledgeの読込・取得・検索・更新・バージョン管理を担当する(設計書 2.1)。"""

    def __init__(self, store: KnowledgeStore, logger: Logger | None = None) -> None: ...

    # --- BaseModule (F02) ---
    def name(self) -> str: ...
    def health_check(self) -> Result[bool]: ...

    # --- 公開インターフェース (設計書 3.3) ---
    def load(self, source: Path) -> Result[KnowledgeDocument]: ...
    def get(self, document_id: str) -> Result[KnowledgeDocument]: ...
    def get_latest(self, document_id: str) -> Result[KnowledgeDocument]: ...
    def search(self, keyword: str) -> Result[list[KnowledgeDocument]]: ...
    def list_documents(self, category: KnowledgeCategory) -> Result[list[KnowledgeDocument]]: ...
    def update(self, document: KnowledgeDocument) -> Result[KnowledgeDocument]: ...
    def create_version(self, document_id: str, content: str) -> Result[KnowledgeDocument]: ...
```

### 4.2 各メソッドの契約

| メソッド | 入力 | 出力(成功時) | 主な失敗理由 |
|---|---|---|---|
| `load` | `source: Path`(Knowledgeソースファイル) | `Result[KnowledgeDocument]` | ファイル不存在→`NotFoundError`、構造不備→`ValidationError` |
| `get` | `document_id: str` | `Result[KnowledgeDocument]` | 文書不存在→`NotFoundError` |
| `get_latest` | `document_id: str` | `Result[KnowledgeDocument]` | 文書不存在→`NotFoundError` |
| `search` | `keyword: str` | `Result[list[KnowledgeDocument]]`(0件時は空リストで成功) | 該当なしはエラーではない |
| `list_documents` | `category: KnowledgeCategory` | `Result[list[KnowledgeDocument]]` | 該当なしはエラーではない |
| `update` | `document: KnowledgeDocument` | `Result[KnowledgeDocument]` | 不存在→`NotFoundError`、`document.updated_by`が許可ロール外→`PermissionDeniedError`、`document.version`が最新でない→`KnowledgeVersionConflictError` |
| `create_version` | `document_id: str`, `content: str` | `Result[KnowledgeDocument]` | 不存在→`NotFoundError` |

補助モジュール(`store.py` / `markdown_loader.py` / `search_index.py` / `permissions.py`)は公開APIではなく、`KnowledgeManager`内部からのみ呼び出す。

---

## 5. エラー処理

Foundation(F02/3.6節)のエラー階層 `FoundationError → NotFoundError / ValidationError / PermissionDeniedError / StateTransitionError / ConfigurationError / ExternalServiceError` を継承し、M03固有のケースはサブクラスとして`exceptions.py`に定義する(Foundation側でのみ新規基底例外を追加できるため、既存の基底クラスを継承する)。

```python
# src/knowledge_manager/exceptions.py
from __future__ import annotations

from foundation.errors import NotFoundError, ValidationError, PermissionDeniedError


class KnowledgeDocumentNotFoundError(NotFoundError):
    """document_id に対応するKnowledgeDocumentが存在しない(4.6: 文書不存在)。"""


class KnowledgeVersionConflictError(ValidationError):
    """update()時、渡されたversionがStore上の最新versionと一致しない(4.6: バージョン競合)。"""


class KnowledgeIntegrityError(ValidationError):
    """content_hashが内容と一致しない等の整合性エラー(4.6: 整合性エラー)。"""


class KnowledgeUpdatePermissionDeniedError(PermissionDeniedError):
    """updated_by が Planner/Architect/Reviewer 以外(4.6: 権限不足、3.5節)。"""
```

対応方針:

- **文書不存在**: `get` / `get_latest` / `update` / `create_version` で対象`document_id`がStoreに存在しない場合、`Result(success=False, value=None, error=KnowledgeDocumentNotFoundError(...))`を返す。例外を送出せず`Result`で返却する(F02のResult[T]パターンに従う)。
- **バージョン競合**: `update()`に渡された`document.version`がStore上の最新版と異なる場合、楽観ロックとして`KnowledgeVersionConflictError`を返す。呼び出し元は`get_latest()`で最新版を取得し再試行する。
- **権限不足**: `update()`実行時、`permissions.py`の`is_update_allowed(role: str) -> bool`(許可ロール: `"planner"`, `"architect"`, `"reviewer"`)で`document.updated_by`を検証し、不許可であれば`KnowledgeUpdatePermissionDeniedError`を返す。`create_version()`は0節に記載の通り本メソッド単体では権限判定を行わない。
- **整合性エラー**: `content_hash`が実際の`content`から再計算した値と一致しない場合、`KnowledgeIntegrityError`を返す。
- 全メソッドは例外をそのまま送出せず、`Result[T]`にラップして返す(BaseModule/F02準拠)。内部実装では例外を捕捉し`Result`に変換する。

---

## 6. ロギング仕様

`foundation.logger.get_logger("knowledge_manager")` を通じてモジュール共通のLoggerを取得する。標準ライブラリ`logging`のみを使用し、独自のログ基盤は持たない。

```python
# knowledge_manager.py 内での使用例(概念コード)
self._logger: Logger = logger or get_logger("knowledge_manager")

def _log_operation(
    self,
    operation: str,
    category: KnowledgeCategory | None,
    knowledge_version: int | None,
    result: str,
) -> None:
    """4.5節のログ必須項目(timestamp/knowledge_version/operation/category/result)のみを出力する。

    Knowledge本文(content)・タイトル・タグ等は一切引数に取らず、
    呼び出し側からログ関数へ KnowledgeDocument オブジェクト自体を渡さないことで
    本文がログに混入する経路を構造的に排除する。
    """
    self._logger.info(
        "operation=%s category=%s version=%s result=%s",
        operation,
        category.value if category else "-",
        knowledge_version if knowledge_version is not None else "-",
        result,
    )
```

- `timestamp`は`logging`の標準フォーマッタ(Foundation 3.7節の`timestamp | module_name | level | message`)が自動付与するため、明示的な引数にしない。
- `_log_operation`のシグネチャに`content`や`KnowledgeDocument`本体を含めないことで、「Knowledge本文はログへ出力してはならない」(4.5節)という制約を型レベルで担保する。`update`/`create_version`/`load`成功時も、ログには`document_id`・`category`・`version`・`result`のみを渡す。

---

## 7. Unit Testケース一覧

`unittest`(`pytest`は使用しない)。テストクラスは`src/knowledge_manager/tests/test_knowledge_manager.py`を中心に配置する。

### `TestKnowledgeManagerLoad`
- `test_load_valid_markdown_file_returns_success_result`
- `test_load_missing_file_returns_not_found_error`
- `test_load_missing_category_section_returns_validation_error`(4.3構造要件違反)
- `test_load_assigns_initial_version_number_one`
- `test_load_sets_status_current`

### `TestKnowledgeManagerGet`
- `test_get_existing_document_returns_success`
- `test_get_nonexistent_document_returns_not_found_error`
- `test_get_without_version_qualifier_returns_latest_version`

### `TestKnowledgeManagerGetLatest`
- `test_get_latest_returns_highest_version_number`
- `test_get_latest_nonexistent_document_returns_not_found_error`
- `test_get_latest_reflects_recently_created_version`

### `TestKnowledgeManagerSearch`(検索精度)
- `test_search_keyword_in_title_returns_matching_documents`
- `test_search_keyword_in_content_returns_matching_documents`
- `test_search_no_match_returns_empty_list_not_error`
- `test_search_is_case_insensitive`
- `test_search_does_not_depend_on_embedding_or_vector_store`(5.3のMVP対象外機能を使っていないことの回帰確認)

### `TestKnowledgeManagerListDocuments`
- `test_list_documents_filters_by_category`
- `test_list_documents_unknown_category_returns_empty_list`
- `test_list_documents_returns_only_current_status_per_document_id`

### `TestKnowledgeManagerUpdate`(バージョン管理・更新競合・権限制御)
- `test_update_by_planner_role_succeeds`
- `test_update_by_architect_role_succeeds`
- `test_update_by_reviewer_role_succeeds`
- `test_update_by_executor_role_returns_permission_denied_error`
- `test_update_by_context_manager_role_returns_permission_denied_error`
- `test_update_with_stale_version_returns_version_conflict_error`
- `test_update_with_latest_version_succeeds_and_preserves_history`
- `test_update_persists_new_content_hash`
- `test_update_nonexistent_document_returns_not_found_error`

### `TestKnowledgeManagerCreateVersion`(バージョン管理)
- `test_create_version_increments_version_number`
- `test_create_version_marks_previous_version_as_archived`
- `test_create_version_keeps_previous_version_retrievable_by_get`(過去版参照可能、3.4節)
- `test_create_version_nonexistent_document_returns_not_found_error`
- `test_create_version_updates_content_hash`

### `TestKnowledgeManagerLogging`
- `test_update_log_message_does_not_contain_document_content`
- `test_load_log_message_does_not_contain_document_content`
- `test_log_message_includes_operation_category_version_result`

### `TestKnowledgeManagerHealthCheck`
- `test_health_check_returns_success_when_store_available`

### `TestKnowledgeCategoryAndStatusEnums`
- `test_all_five_categories_are_defined`
- `test_category_enum_has_no_extra_members`(勝手なカテゴリ追加防止の回帰テスト)

---

## 8. MVP範囲の明記

設計書5.3節「重厚壮大化監査」において**削除済み(対象外)**と判定された以下の機能は、本モジュールでは一切実装しない。

- Vector Database
- Semantic Search
- Knowledge Graph
- Embedding生成
- AI自動要約
- RAGパイプライン
- External Wiki連携
- 自動知識抽出
- AIによる陳腐化検知

`search()`は`search_index.py`による**単純なキーワード部分一致検索**(大文字小文字を区別しない文字列検索)のみを提供し、形態素解析・類似度スコアリング・埋め込みベクトルは使用しない。Knowledgeソースは**Markdownファイル**のみを対象とし、外部Wiki・DB連携は行わない。また、Context生成(Context Managerの責務)・Configuration管理(Configuration Managerの責務)・Workflow管理・Repository情報の保持は、設計書2.2/4.1/4.4節により本モジュールの実装範囲から明確に除外する。
