# IS20 GitHub Manager 実装仕様書

- 対象設計書: `M20 GitHub Manager.txt`（Design Freeze v1.0）
- 前提モジュール: `M00 Foundation.txt`（`DESIGN_VERSION = "v1.0"`）
- 実装言語: Python 3.13
- 配置先: `src/github_manager/`

本書は M20 GitHub Manager の詳細設計書を実装可能な粒度に具体化したものであり、設計書に記載のない機能・APIを追加しない。設計書の記述と本書が矛盾する場合は設計書を正とする。Repository に対する書き込み・更新操作は Executor / PR Creator の責務であり、本モジュールでは実装しない（設計書4.3節）。

---

## 1. モジュール概要

GitHub Manager は、AI Development Pipeline において GitHub Repository に対する共通アクセスを一元的に提供するモジュールである。Repository・Branch・Commit・Pull Request・File・Diff の各情報取得と GitHub API 呼び出しのみを担当し、コード生成・Pull Request作成・Pull Requestレビュー・Repository解析（設計分析・依存関係分析・Business分析）・Workflow制御は一切行わない。MVPでは読み取り専用（Read Only）とし、Workflow に必要な最小限の情報のみを取得する。Context Manager・PR Creator・Weekly Reviewer は本モジュールを介してのみ GitHub の Repository 情報にアクセスする（引継ぎドキュメント5章: 「Repository操作は専用モジュールのみが担当する」）。

---

## 2. ファイル構成

`src/github_manager/` 配下に以下を配置する。

| ファイル | 役割 |
|---|---|
| `__init__.py` | パッケージの公開API（`GitHubManager`、本モジュールのdataclass群、例外クラス）を re-export する。新規ロジックは持たない。 |
| `github_manager.py` | 公開インターフェース（設計書3.5節: `get_repository` / `get_branch` / `get_pull_request` / `get_file` / `get_diff` / `build_repository_context`）を実装する `GitHubManager` クラス（`foundation.base_module.BaseModule` を継承）を定義する。GitHub APIの生データをdataclassへ変換し、`Result[T]` でラップし、ロギングを行う。Business判断・Repository解析は行わない。 |
| `client.py` | GitHub REST API との通信のみを担当する `GitHubClient`（Adapter層）を定義する。HTTP呼び出し・認証ヘッダー付与・レスポンスJSONの生成のみを行い、業務判断は行わない。`github_manager.py` からのみ利用される。 |
| `types.py` | 設計書3.2節・3.3節の成果物（Repository / Branch / Commit / Pull Request / File / Diff / Repository Context）をdataclassとして定義する（3章参照）。 |
| `errors.py` | Foundationのエラー階層を継承した本モジュール固有の例外クラスを定義する（5章参照）。新しい基底例外（`FoundationError`の兄弟）は追加しない。 |
| `constants.py` | `GITHUB_API_BASE_URL`・`DEFAULT_TIMEOUT_SECONDS` など本モジュール内でのみ使う軽量な定数を集約する。GitHub Enterprise対応（ベースURL可変化）はMVP対象外のため固定値とする。 |
| `tests/` | unittest によるテスト一式（7章参照）。 |

---

## 3. データクラス定義

設計書3.2節「管理対象」・3.3節「Repository Context」に定義された成果物をdataclassとして `types.py` に定義する。

### 3.1 Foundation Domain Model の利用方針

Design Freeze監査により、Foundation（F01, `M00 Foundation.txt` 3.3節）のDomain Model一覧に `Repository`（Repository/Branch/Commit/File/Diff情報、利用モジュール: GitHub Manager, Executor, PR Creator）が追加され、本設計書5.2節「F01: Repository Domain を利用する」との対応関係は解消済みである（`CHANGELOG.md` 参照）。

本書では以下の方針で実装する:

- **Pull Request** は Foundation側 `foundation.types.PullRequest`（`id` / `created_at` / `updated_at` / `metadata` の共通属性を持つ）が公式に定義するF01 Domainであるため、本モジュールの `PullRequestMetadata` はこれを **継承** し、設計書3.2節記載のモジュール固有属性（PR Number, Status, Changed Files）のみを追加する。
- **Repository / Branch / Commit / File / Diff / Repository Context** は Foundation側 `foundation.types.Repository`（`id` / `created_at` / `updated_at` / `metadata` の共通属性を持つ）を継承し、設計書3.2節・3.3節が個別に列挙するモジュール固有属性のみを追加する。

### 3.2 dataclass定義

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from foundation.types import PullRequest


@dataclass
class CommitMetadata:
    """設計書3.2節「Commit」"""

    commit_id: str
    author: str
    timestamp: datetime
    message: str


@dataclass
class RepositoryMetadata:
    """設計書3.2節「Repository」"""

    repository_name: str
    default_branch: str
    current_branch: str


@dataclass
class BranchMetadata:
    """設計書3.2節「Branch」"""

    branch_name: str
    latest_commit: CommitMetadata


@dataclass
class PullRequestMetadata(PullRequest):
    """設計書3.2節「Pull Request」。foundation.types.PullRequest（F01）を継承する。"""

    pr_number: int = 0
    status: str = ""
    changed_files: list[str] = field(default_factory=list)


@dataclass
class FileContent:
    """設計書3.2節「File」"""

    file_path: str
    file_content: str
    last_modified: datetime


@dataclass
class Diff:
    """設計書3.2節「Diff」"""

    changed_files: list[str]
    added_lines: int
    deleted_lines: int


@dataclass
class RepositoryContext:
    """設計書3.3節「Repository Context」。Context Manager へ提供する最小情報。
    Repository全体は含まない（設計書3.3節・4.4節）。"""

    repository_name: str
    current_branch: str
    target_files: list[str]
    changed_files: list[str]
    related_directories: list[str]
```

---

## 4. クラス・関数シグネチャ

### 4.1 `client.py`（Adapter層）

```python
from __future__ import annotations

from typing import Any

from foundation.interfaces import ConfigurationClient


class GitHubClient:
    """GitHub REST API との通信のみを担当するAdapter。業務判断・整形は行わない。"""

    def __init__(self, configuration_client: ConfigurationClient) -> None:
        """configuration_client経由でaccess_tokenを取得する。トークン自体は
        インスタンス変数として保持するのみで、ログには出力しない。"""

    def get_repository(self, repository: str) -> dict[str, Any]:
        """GET /repos/{repository} の生JSONを返す。"""

    def get_branch(self, repository: str, branch: str) -> dict[str, Any]:
        """GET /repos/{repository}/branches/{branch} の生JSONを返す。"""

    def get_commit(self, repository: str, commit_sha: str) -> dict[str, Any]:
        """GET /repos/{repository}/commits/{commit_sha} の生JSONを返す。"""

    def get_pull_request(self, repository: str, pull_request_number: int) -> dict[str, Any]:
        """GET /repos/{repository}/pulls/{pull_request_number} の生JSONを返す。"""

    def get_file_content(
        self, repository: str, file_path: str, ref: str | None = None
    ) -> dict[str, Any]:
        """GET /repos/{repository}/contents/{file_path}（refは任意のbranch/commit指定）の
        生JSONを返す。"""

    def get_commit_diff(self, repository: str, commit_sha: str) -> dict[str, Any]:
        """GET /repos/{repository}/commits/{commit_sha}（diff情報含む）の生JSONを返す。"""

    def get_pull_request_diff(self, repository: str, pull_request_number: int) -> dict[str, Any]:
        """GET /repos/{repository}/pulls/{pull_request_number}/files の生JSONを返す。"""
```

- HTTP通信・レスポンスパース中の失敗（ネットワークエラー・タイムアウト・5xx・認証失敗）は `errors.py` の `GitHubApiError` を送出する。
- 404応答は `RepositoryNotFoundError` / `BranchNotFoundError` / `PullRequestNotFoundError` / `GitHubFileNotFoundError`（いずれも `NotFoundError` を継承）を送出する。
- 使用するHTTPクライアントライブラリ・ベースURL固定値等の実装詳細は設計書に明記が無いため、本書の実装判断とする（要確認事項）。GitHub Enterprise対応（ベースURL可変化）はMVP対象外（設計書5.3節）のため、`constants.py` の `GITHUB_API_BASE_URL = "https://api.github.com"` を固定使用する。

### 4.2 `github_manager.py`（公開インターフェース）

```python
from __future__ import annotations

from foundation.base_module import BaseModule
from foundation.result import Result

from github_manager.client import GitHubClient
from github_manager.types import (
    BranchMetadata,
    Diff,
    FileContent,
    PullRequestMetadata,
    RepositoryContext,
    RepositoryMetadata,
)


class GitHubManager(BaseModule):
    def __init__(self, client: GitHubClient) -> None:
        """clientはgithub_manager.client.GitHubClientのインスタンスを受け取る
        （テスト時はフェイク実装を注入できる）。"""

    def name(self) -> str:
        """'github_manager' を返す。"""

    def health_check(self) -> Result[bool]:
        """GitHub APIへの疎通確認結果をResult[bool]として返す。"""

    def get_repository(self, repository: str) -> Result[RepositoryMetadata]:
        """設計書3.5節 get_repository()。Repository Metadataを取得する。"""

    def get_branch(self, repository: str, branch: str) -> Result[BranchMetadata]:
        """設計書3.5節 get_branch()。Branch Metadataを取得する。"""

    def get_pull_request(
        self, repository: str, pull_request_number: int
    ) -> Result[PullRequestMetadata]:
        """設計書3.5節 get_pull_request()。Pull Request Metadataを取得する。"""

    def get_file(
        self, repository: str, file_path: str, ref: str | None = None
    ) -> Result[FileContent]:
        """設計書3.5節 get_file()。File Contentを取得する。refを省略した場合は
        Default Branchの最新内容を取得する。"""

    def get_diff(
        self,
        repository: str,
        commit: str | None = None,
        pull_request_number: int | None = None,
    ) -> Result[Diff]:
        """設計書3.5節 get_diff()。commit / pull_request_number のいずれか一方のみを
        指定する。両方指定・両方未指定の場合は失敗Resultを返す（8.5節参照）。"""

    def build_repository_context(
        self, repository: str, workflow_scope: str
    ) -> Result[RepositoryContext]:
        """設計書3.5節 build_repository_context()。指定されたWorkflow Scopeに
        必要なRepository情報のみを収集する。Repository全体は取得しない
        （設計書3.3節・4.4節）。"""
```

- 引数 `repository`（例: `"owner/repo"` 形式のRepository識別子）は、設計書3.1節「入力」に列挙された `repository` を全メソッド共通の必須入力として明示化したものである。設計書3.5節の各メソッド入力欄は簡潔な記法（例: `Branch` のみ）のため、GitHub API呼び出しに不可欠な `repository` を暗黙の前提として全メソッドに追加している（要確認事項）。
- `workflow_scope` の型・具体的な値の集合は設計書に明記が無いため、呼び出し元（Context Manager / PR Creator / Weekly Reviewer）が渡すWorkflow種別を識別する文字列として扱う（要確認事項）。本モジュールはこの値を用いて取得対象を絞り込むのみで、Workflow自体の解釈・制御は行わない（設計書4.2節）。

---

## 5. エラー処理

`errors.py` にて、Foundationのエラー階層（`foundation.errors`）を継承したモジュール固有例外のみを定義する。新しい基底例外（`FoundationError` の兄弟）は追加しない（`M00 Foundation.txt` 3.6節）。

```python
from foundation.errors import ExternalServiceError, NotFoundError, ValidationError


class GitHubApiError(ExternalServiceError):
    """GitHub API呼び出し失敗（ネットワークエラー・タイムアウト・5xx・認証失敗等）。"""


class RepositoryNotFoundError(NotFoundError):
    """指定Repositoryが存在しない、またはアクセス権がない場合。"""


class BranchNotFoundError(NotFoundError):
    """指定Branchが存在しない場合。"""


class PullRequestNotFoundError(NotFoundError):
    """指定Pull Requestが存在しない場合。"""


class GitHubFileNotFoundError(NotFoundError):
    """指定File Pathが存在しない場合。"""


class InvalidDiffTargetError(ValidationError):
    """get_diff()にcommitとpull_request_numberの両方、または
    いずれも指定されなかった場合。"""
```

### 5.1 GitHub API呼び出し失敗時の扱い

- `GitHubManager` の各公開メソッドは、`GitHubClient` が送出した例外を捕捉し、`Result(success=False, error=...)` として返却する。例外を呼び出し元へ伝播させない（Foundation F00「Safety」原則: 失敗時は安全側に倒す）。
- 入力検証（例: `get_diff()` の排他指定）は `foundation.validation` の `require_*` 系、または `InvalidDiffTargetError` を直接送出したうえで `Result(success=False, error=...)` に変換する。
- レート制限・一時的な5xx等の再試行方針は設計書に明記が無いため、本書のMVP実装範囲では**再試行を行わない**（重厚壮大化回避）。1回の呼び出しで失敗した場合はそのまま失敗Resultを返す。

---

## 6. ロギング仕様

設計書4.5節に定めるログ項目を、`foundation.logger.get_logger(__name__)` で取得したLoggerを用いて記録する。

```python
from foundation.logger import get_logger

logger = get_logger("github_manager")
```

- 出力項目: `timestamp`（Foundationのログフォーマットに自動付与）、`repository`、`operation`（呼び出されたメソッド名）、`branch`（該当しない呼び出しでは `-` 等の非該当値）、`pull_request`（該当しない呼び出しでは非該当値）、`result`（`success` / `failure`）、`duration`（処理時間, 秒）。
- 各公開メソッドの開始時刻を記録し、処理完了時（成功・失敗いずれも）に1回、上記項目を1行でログ出力する。
- **Access Token・Secret・Credential・Repository内容（File Content, Diff本文, Commit本文の全文）はログへ出力しない。** `GitHubClient` はAccess Tokenをログに一切渡さない実装とし、`GitHubManager` 側もログ呼び出しの引数に識別子（repository名・branch名・PR番号・operation名・成否・所要時間）以外を含めない。
- ログ出力例（成功時）: `operation=get_pull_request repository=owner/repo branch=- pull_request=123 result=success duration=0.482`

---

## 7. Unit Testケース一覧（unittest）

設計書にモジュール固有の「テスト観点」章は存在しないため、2章（責務）・3.5節（公開インターフェース）・4章（制約）から導出したテスト観点に基づき列挙する。

### 7.1 `test_types.py`

- `test_repository_metadata_holds_expected_fields`
- `test_branch_metadata_holds_latest_commit_metadata`
- `test_commit_metadata_holds_expected_fields`
- `test_pull_request_metadata_extends_foundation_pull_request`
- `test_pull_request_metadata_inherits_common_attributes`
- `test_file_content_holds_expected_fields`
- `test_diff_holds_expected_fields`
- `test_repository_context_holds_expected_fields`

### 7.2 `test_client.py`

- `test_client_attaches_authorization_header_from_configuration_client`
- `test_client_get_repository_returns_parsed_json`
- `test_client_get_branch_returns_parsed_json`
- `test_client_get_commit_returns_parsed_json`
- `test_client_get_pull_request_returns_parsed_json`
- `test_client_get_file_content_returns_parsed_json`
- `test_client_get_commit_diff_returns_parsed_json`
- `test_client_get_pull_request_diff_returns_parsed_json`
- `test_client_raises_not_found_error_variants_on_404_response`
- `test_client_raises_github_api_error_on_5xx_response`
- `test_client_raises_github_api_error_on_network_timeout`
- `test_client_does_not_log_access_token`

### 7.3 `test_github_manager.py`

- `test_name_returns_github_manager`
- `test_health_check_returns_result_bool`
- `test_get_repository_returns_repository_metadata_on_success`
- `test_get_repository_returns_failure_result_when_repository_not_found`
- `test_get_branch_returns_branch_metadata_on_success`
- `test_get_branch_returns_failure_result_when_branch_not_found`
- `test_get_pull_request_returns_pull_request_metadata_on_success`
- `test_get_pull_request_returns_failure_result_when_pull_request_not_found`
- `test_get_file_returns_file_content_on_success`
- `test_get_file_returns_failure_result_when_file_not_found`
- `test_get_file_uses_default_branch_when_ref_omitted`
- `test_get_diff_returns_diff_when_commit_specified`
- `test_get_diff_returns_diff_when_pull_request_specified`
- `test_get_diff_returns_failure_result_when_neither_commit_nor_pull_request_given`
- `test_get_diff_returns_failure_result_when_both_commit_and_pull_request_given`
- `test_build_repository_context_returns_scoped_fields_only`
- `test_build_repository_context_does_not_include_full_repository_content`
- `test_get_repository_wraps_github_api_error_into_failure_result`
- `test_public_methods_do_not_mutate_repository_state`（Read Only制約: 書き込み系メソッドが存在しないことをAPIサーフェスで検証）

### 7.4 `test_logging.py`

- `test_get_repository_logs_operation_repository_result_duration`
- `test_get_branch_logs_branch_field`
- `test_get_pull_request_logs_pull_request_field`
- `test_logging_does_not_include_access_token_or_secret`
- `test_logging_does_not_include_file_content_or_diff_body`
- `test_logging_records_failure_result_on_error`

### 7.5 `test_errors.py`

- `test_github_api_error_is_external_service_error_subclass`
- `test_repository_not_found_error_is_not_found_error_subclass`
- `test_branch_not_found_error_is_not_found_error_subclass`
- `test_pull_request_not_found_error_is_not_found_error_subclass`
- `test_github_file_not_found_error_is_not_found_error_subclass`
- `test_invalid_diff_target_error_is_validation_error_subclass`

---

## 8. MVP範囲の明記

設計書5.3節（重厚壮大化監査）にて対象外・削除済みとされた以下の機能は、本実装仕様の対象外とし、実装しない。

- GitHub Enterprise対応
- GraphQL API
- GitHub Actions管理
- Issue管理
- Release管理
- Projects管理
- Webhook管理
- Repository同期

また、以下も設計書2.2節・4.1節・4.2節・4.3節により本モジュールの責務外であり、実装対象に含めない。

- コード生成・コード編集
- Pull Request作成（PR Creatorの責務）
- Pull Requestレビュー（Reviewerの責務）
- Repository解析（設計分析・依存関係分析・Business分析）
- Workflow制御
- Repository更新・書き込み操作（MVPではRead Onlyとし、更新はExecutor / PR Creatorが担当）
- Repository全体の取得（Workflowに必要な最小限の情報のみを取得する。設計書4.4節）

本モジュールは設計書3.5節の6つの公開インターフェース（`get_repository` / `get_branch` / `get_pull_request` / `get_file` / `get_diff` / `build_repository_context`）と、それらが返す成果物（Repository / Branch / Commit / Pull Request / File / Diff / Repository Context）の取得・整形・ロギングのみを実装範囲とする。
