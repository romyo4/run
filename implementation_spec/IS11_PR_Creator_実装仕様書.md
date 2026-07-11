# IS11 PR Creator 実装仕様書

> 本書は `M11 PR Creator.txt`(確定済み詳細設計書)を唯一の正とし、`M00 Foundation.txt` が定義する F00〜F03 を前提として、実装可能な粒度まで具体化したものである。設計書に記載のない機能(自動マージ、Draft PR管理、Release Note生成、GitHub Project更新、GitHub Issue自動生成、Multi Repository PR、GitHub App管理)は実装しない。

---

## 1. モジュール概要

PR Creator(M11)は、Tester(M10)が Quality Gate を PASS させた実装成果物を GitHub Pull Request として登録する単一責務のモジュールである。Title・Description(Summary/Purpose/Changes/Test Result/Related Issue/Notes の固定テンプレート)を一貫した形式で生成し、GitHub 上に Pull Request を作成・更新し、Reviewer を割り当てたうえで Pull Request URL を確定・報告する。コード生成・コード修正・テスト実行・レビュー・マージ・Release 作成は一切行わず、Quality Gate が PASS していない実装成果物に対しては Pull Request を作成してはならない(設計書 4.1, 4.2)。MVP では GitHub の Pull Request のみを対象とし、GitLab・Bitbucket は対象外とする(設計書 4.4)。

---

## 2. ファイル構成

```text
src/pr_creator/
├── __init__.py            # 公開エクスポート(PRCreator, 例外, dataclass)の再輸出のみ
├── pr_creator.py           # PRCreator クラス本体(BaseModule継承、公開I/F 4関数を実装)
├── models.py               # 本モジュール固有 dataclass 定義(3章参照)
├── template.py             # PRテンプレート(Summary/Purpose/Changes/Test Result/Related Issue/Notes)生成ロジック
├── quality_gate.py         # Quality Gate PASS判定ロジック(test_report/QualityGateResultの検査)
├── github_client.py        # GitHub Pull Request作成・更新・Reviewer割当を行うAdapter層(F00 Adapter Pattern)
├── errors.py                # 本モジュール固有例外(Foundation例外階層を継承)
├── logging_utils.py         # get_logger()経由のログ出力ヘルパー(Secret除外を一元化)
└── tests/
    ├── __init__.py
    ├── test_pr_creator.py
    ├── test_template.py
    ├── test_quality_gate.py
    └── test_github_client.py
```

各ファイルの役割:

| ファイル | 役割 |
|---|---|
| `pr_creator.py` | `create_pr` / `update_pr` / `assign_reviewers` / `publish` の実装。`BaseModule` を継承し `name()` / `health_check()` を実装する。Quality Gate 未PASS時の作成拒否(4.2)、指定Branch以外を対象にしない制約(4.3)を担保する。 |
| `models.py` | Foundation `types.py` の `PullRequest` Domain を利用しつつ、本モジュール固有の入出力型(`PullRequestTemplate`, `CreatePullRequestInput`, `RepositoryInformation`, `BranchInformation`, `AssignmentResult`, `CreationReport`)を定義する。 |
| `template.py` | `PullRequestTemplate` から Markdown 本文(Summary/Purpose/Changes/Test Result/Related Issue/Notes 固定順)を組み立てる純関数群。Title生成ロジックも含む。 |
| `quality_gate.py` | `test_report`(Tester成果物)から Quality Gate PASS/FAIL を判定する。PASSしていない場合は `QualityGateNotPassedError` を送出する。 |
| `github_client.py` | GitHub REST API 呼び出しの唯一の窓口。Access Token は `ConfigurationClient`(F03)経由で取得し、呼び出し以外の目的で保持・ログ出力しない。 |
| `errors.py` | Foundation `errors.py` / `exceptions.py` の階層を継承したモジュール固有例外を定義する。 |
| `logging_utils.py` | `get_logger("pr_creator")` を用い、設計書 4.5 で定めた出力項目のみを許可するログ出力関数を提供する。Secret/Access Token/Credential を含む値は呼び出し元で渡しても出力しない。 |

---

## 3. データクラス定義

Foundation `types.py` の `PullRequest` Domain(共通属性 `id / created_at / updated_at / metadata` を含む)をそのまま利用し、本モジュールでは以下を追加定義する。

```python
# src/pr_creator/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class PullRequestTemplate:
    """設計書 3.3 のPRテンプレート(Summary/Purpose/Changes/Test Result/Related Issue/Notes)"""

    summary: str
    purpose: str
    changes: list[str]
    test_result: str
    related_issue: str | None
    notes: str | None = None


@dataclass(frozen=True)
class RepositoryInformation:
    """設計書 3.1 の repository_information"""

    owner: str
    name: str
    default_branch: str


@dataclass(frozen=True)
class BranchInformation:
    """設計書 3.1 の branch_information"""

    base_branch: str
    head_branch: str


@dataclass(frozen=True)
class CreatePullRequestInput:
    """設計書 3.1 の入力一式を束ねたcreate_pr()向けリクエスト

    設計書 3.5 では create_pr() の入力を "Implementation Result" と
    表記しているが、3.1 で列挙された入力(workflow_id / implementation_result /
    test_report / repository_information / branch_information / project_context)
    をすべて受け取らない限り Title/Description生成・Quality Gate判定・GitHub登録が
    実行できないため、本仕様書では3.1の入力一式をまとめた本dataclassを
    create_pr()の実引数とする。新機能の追加ではなく、3.1を実装可能な形に
    束ねたものである。
    """

    workflow_id: str
    implementation_result: "ImplementationResultLike"
    test_report: "TestReportLike"
    repository_information: RepositoryInformation
    branch_information: BranchInformation
    project_context: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AssignmentResult:
    """assign_reviewers() の出力(設計書 3.5)"""

    pull_request_number: int
    requested_reviewers: list[str]
    requested_team_reviewers: list[str]
    success: bool
    message: str | None = None


@dataclass(frozen=True)
class CreationReport:
    """設計書 3.4 の Creation Report。ログ出力(4.5)と同一項目を保持する"""

    timestamp: datetime
    workflow_id: str
    repository: str
    branch: str
    pull_request_number: int | None
    pull_request_url: str | None
    result: str
```

`ImplementationResultLike` / `TestReportLike` は Foundation `types.py` 側で定義される Executor(`Implementation`)/ Tester(`TestResult`)の Domain 型を指す型エイリアスであり、本モジュールが独自に再定義することはしない(`from foundation.types import Implementation as ImplementationResultLike` 等でインポートする想定)。

---

## 4. クラス・関数シグネチャ

Foundation `Result[T]` / `BaseModule` / エラー階層 / `get_logger` / `ConfigurationClient` を前提とする。

```python
# src/pr_creator/pr_creator.py
from __future__ import annotations

from pathlib import Path

from foundation.base_module import BaseModule
from foundation.result import Result
from foundation.types import PullRequest
from foundation.logger import get_logger

from pr_creator.models import (
    AssignmentResult,
    CreatePullRequestInput,
)


class PRCreator(BaseModule):
    """AI Development Pipeline の Pull Request 作成モジュール(M11)"""

    def __init__(self) -> None:
        self._logger = get_logger("pr_creator")

    # --- BaseModule (F02) ---
    def name(self) -> str:
        ...

    def health_check(self) -> Result[bool]:
        ...

    # --- 公開インターフェース(設計書 3.5) ---
    def create_pr(self, request: CreatePullRequestInput) -> Result[PullRequest]:
        """Quality Gate PASS を確認したうえで Title/Description を生成し、
        GitHub Pull Request を作成する。Quality Gate 未PASS時は作成せず
        Result[PullRequest](success=False)を返す(設計書 4.2)。"""
        ...

    def update_pr(
        self,
        pull_request: PullRequest,
        template: "PullRequestTemplate | None" = None,
        labels: list[str] | None = None,
    ) -> Result[PullRequest]:
        """既存のPull Request(Title/Description/Label)を更新する。
        Branchの切り替え・統合は行わない(設計書 4.3)。"""
        ...

    def assign_reviewers(
        self,
        pull_request: PullRequest,
        reviewers: list[str],
        team_reviewers: list[str] | None = None,
    ) -> Result[AssignmentResult]:
        """既存のPull RequestにReviewerを設定する。"""
        ...

    def publish(self, pull_request: PullRequest) -> Result[str]:
        """作成・更新・Reviewer設定が完了したPull Requestを最終確認し、
        Pull Request URLを確定・報告する(Creation Reportの記録を含む)。"""
        ...
```

補足(設計解釈): 設計書 3.4 は成果物として `Pull Request` / `Pull Request URL` / `Pull Request Number` / `Creation Report` を列挙し、3.6 の処理フローは「Title生成 → Description生成 → GitHub Pull Request → Reviewer」の順で進む。本仕様書では、GitHub への実際の Pull Request 作成は `create_pr()` 内で行い(Title/Description生成の直後に GitHub API を呼び出す)、`update_pr()` / `assign_reviewers()` は作成済みPull Requestに対する更新操作、`publish()` は Reviewer 設定まで完了した「Completed Pull Request」を最終確認し Pull Request URL を確定して Creation Report を記録する仕上げ処理と位置づける。GitHub側の新規作成呼び出しは `create_pr()` の一箇所に限定し、`publish()` はGitHubへの新規書き込みを行わない。この解釈は設計書に明記された入出力契約(3.5)を満たすための実装上の役割分担であり、新機能の追加ではない。

`github_client.py` 側のシグネチャ:

```python
# src/pr_creator/github_client.py
from __future__ import annotations

from foundation.result import Result
from pr_creator.models import RepositoryInformation, BranchInformation


class GitHubPullRequestClient:
    """GitHub Pull Request操作の唯一の窓口(F00 Adapter Pattern)"""

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token  # ログ出力・例外メッセージに含めない

    def create_pull_request(
        self,
        repository: RepositoryInformation,
        branch: BranchInformation,
        title: str,
        body: str,
    ) -> Result[dict[str, object]]:
        ...

    def update_pull_request(
        self,
        repository: RepositoryInformation,
        pull_request_number: int,
        title: str | None = None,
        body: str | None = None,
        labels: list[str] | None = None,
    ) -> Result[dict[str, object]]:
        ...

    def request_reviewers(
        self,
        repository: RepositoryInformation,
        pull_request_number: int,
        reviewers: list[str],
        team_reviewers: list[str] | None = None,
    ) -> Result[dict[str, object]]:
        ...

    def get_pull_request(
        self,
        repository: RepositoryInformation,
        pull_request_number: int,
    ) -> Result[dict[str, object]]:
        ...
```

---

## 5. エラー処理

Foundation の例外階層(`FoundationError` 基底、`ValidationError` / `NotFoundError` / `PermissionDeniedError` / `StateTransitionError` / `ConfigurationError` / `ExternalServiceError`)をそのまま利用し、本モジュール固有の例外は以下のみ追加する。

```python
# src/pr_creator/errors.py
from __future__ import annotations

from foundation.errors import ValidationError, ExternalServiceError, NotFoundError


class QualityGateNotPassedError(ValidationError):
    """Quality Gate が PASS していない実装成果物に対して
    create_pr() が呼び出された場合に送出する(設計書 4.2)。
    入力(test_report)が作成前提条件を満たさないという意味で
    ValidationError を継承する。"""


class GitHubPullRequestError(ExternalServiceError):
    """GitHub API呼び出し(作成・更新・Reviewer設定)が失敗した場合に送出する。"""


class PullRequestNotFoundError(NotFoundError):
    """update_pr() / assign_reviewers() / publish() の対象Pull Requestが
    GitHub上に存在しない場合に送出する。"""
```

- `create_pr()` は処理の最初に `quality_gate.py` の判定関数で `test_report` を検査し、PASS していなければ `Result(success=False, value=None, error=QualityGateNotPassedError(...))` を返し、GitHub API へは一切書き込みを行わない(4.1「実装しない」・4.2「Quality Gate必須」の担保)。
- GitHub API 呼び出し(`github_client.py`)が失敗した場合は `GitHubPullRequestError` を `Result.error` に設定して返す。例外を送出したまま呼び出し元に伝播させず、`Result[T]` パターン(F02)に統一する。
- `update_pr()` / `assign_reviewers()` / `publish()` が存在しない Pull Request 番号を指定された場合は `PullRequestNotFoundError` を返す。
- Configuration(GitHub接続情報)取得に失敗した場合は Foundation `ConfigurationError` をそのまま `Result.error` に設定する(本モジュールでは再定義しない)。
- いずれの例外も `str(exception)` に Access Token・Secret・Credential の値を含めてはならない(6章のログ仕様と同一方針)。

---

## 6. ロギング仕様

`foundation.logger.get_logger("pr_creator")` を `PRCreator.__init__` で取得し、`logging_utils.py` に定義する `log_operation()` 経由でのみログを出力する。出力形式は Foundation 規約(`timestamp | module_name | level | message`)に従う。

```python
# src/pr_creator/logging_utils.py
from __future__ import annotations

import logging


_ALLOWED_FIELDS = (
    "workflow_id",
    "repository",
    "branch",
    "pull_request_number",
    "pull_request_url",
    "result",
)


def log_operation(logger: logging.Logger, level: int, **fields: object) -> None:
    """設計書4.5で定めた項目のみを許可してログ出力する。
    許可リストにない引数(access_token, credential, secret等)を
    渡してもKeyErrorとして拒否し、誤って機密情報を出力できないようにする。"""
    unknown = set(fields) - set(_ALLOWED_FIELDS)
    if unknown:
        raise ValueError(f"許可されていないログ項目: {sorted(unknown)}")
    message = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.log(level, message)
```

- `timestamp` は `logging` の `Formatter` が自動付与するため、`log_operation()` の呼び出し引数には含めない(Foundation出力形式が既にtimestampを含む)。
- `create_pr` / `update_pr` / `assign_reviewers` / `publish` はいずれも処理開始時(`result="STARTED"`)と終了時(`result="SUCCESS"` または `"FAILURE"`)の最低2回、`workflow_id / repository / branch / pull_request_number / pull_request_url / result` を `log_operation()` 経由で記録する。
- `github_client.py` は Access Token を HTTP ヘッダー構築にのみ使用し、リクエスト内容・レスポンス内容をそのままログへ渡さない。エラー時もステータスコードとメッセージ要約のみを `GitHubPullRequestError` に格納する。
- `log_operation()` が許可リスト外のキーを受け取った場合は `ValueError` を送出して即座に失敗させ、Secret/Access Token/Credential が誤って渡された場合でも出力前に検知できるようにする(ホワイトリスト方式)。

---

## 7. Unit Test ケース一覧

`unittest`(`pytest` は使用しない)。テストファイルは `src/pr_creator/tests/` 配下。

### `test_pr_creator.py`(`PRCreatorTestCase`)

- `test_name_returns_pr_creator`
- `test_health_check_returns_success_result`
- `test_create_pr_returns_success_when_quality_gate_passed`
- `test_create_pr_returns_failure_when_quality_gate_not_passed`
- `test_create_pr_does_not_call_github_client_when_quality_gate_not_passed`
- `test_create_pr_generates_title_from_implementation_result`
- `test_create_pr_generates_description_with_fixed_template_sections`
- `test_create_pr_includes_changed_files_in_description`
- `test_create_pr_only_targets_specified_branch`
- `test_create_pr_returns_external_service_error_on_github_failure`
- `test_create_pr_does_not_log_access_token`
- `test_update_pr_returns_updated_pull_request_on_success`
- `test_update_pr_returns_not_found_error_when_pull_request_missing`
- `test_update_pr_does_not_change_branch_information`
- `test_assign_reviewers_returns_assignment_result_on_success`
- `test_assign_reviewers_returns_success_with_empty_list_when_no_reviewers_specified`
- `test_assign_reviewers_returns_external_service_error_on_github_failure`
- `test_publish_returns_pull_request_url_on_success`
- `test_publish_returns_not_found_error_when_pull_request_number_missing`
- `test_publish_records_creation_report_with_required_fields`
- `test_publish_does_not_create_new_github_pull_request`

### `test_template.py`(`PullRequestTemplateTestCase`)

- `test_render_contains_all_sections_in_fixed_order`
- `test_render_includes_summary_purpose_changes_test_result_related_issue_notes_headings`
- `test_render_handles_empty_changes_list`
- `test_render_handles_missing_related_issue`
- `test_render_handles_missing_notes`
- `test_build_title_from_implementation_result_and_workflow_id`

### `test_quality_gate.py`(`QualityGateTestCase`)

- `test_is_passed_returns_true_when_all_checks_pass`
- `test_is_passed_returns_false_when_build_failed`
- `test_is_passed_returns_false_when_lint_has_error`
- `test_is_passed_returns_false_when_unit_test_failed`
- `test_is_passed_returns_false_when_integration_test_failed`
- `test_is_passed_returns_false_when_regression_test_failed`
- `test_is_passed_returns_false_when_static_analysis_has_critical_error`
- `test_ensure_passed_raises_quality_gate_not_passed_error_when_failed`
- `test_ensure_passed_does_not_raise_when_all_checks_pass`

### `test_github_client.py`(`GitHubPullRequestClientTestCase`)

- `test_create_pull_request_returns_number_and_url_on_success`
- `test_create_pull_request_returns_external_service_error_on_http_failure`
- `test_update_pull_request_returns_updated_payload_on_success`
- `test_request_reviewers_returns_success_result`
- `test_get_pull_request_returns_not_found_when_missing`
- `test_access_token_is_not_present_in_error_message`

---

## 8. MVP範囲の明記

設計書 5.3(重厚壮大化監査)にて対象外・削除済みとされた以下の機能は、本実装仕様書においても実装しない。

- 自動マージ
- Draft PR管理
- Release Note生成
- GitHub Project更新
- GitHub Issue自動生成
- Multi Repository PR
- GitHub App管理

また、設計書 2.2 / 4.4 に基づき以下も対象外とする。

- コード生成・コード修正・テスト実行・コードレビュー・Pull Requestマージ・Release作成(2.2 担当しない)
- GitLab・Bitbucket 対応(4.4 GitHub制約、GitHubのPull Requestのみ対応)

上記に該当する機能要望が生じた場合、本モジュールのスコープでは実装せず、設計書の次バージョン改訂を待つこと。
