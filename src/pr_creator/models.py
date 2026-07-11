"""PR Creator (M11) 固有のdataclass定義(IS11 3章)。

Foundation `types.py` の `PullRequest` Domain(共通属性 id/created_at/updated_at/metadata)を
そのまま利用し、本モジュールでは入出力を表現する追加のdataclassのみを定義する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# `implementation_result`/`test_report`の実体は、それぞれExecutor(M09)の
# `executor.models.ImplementationResult`(`.implementation`/`.modified_files`/
# `.execution_report`を保持する)、Tester(M10)の`tester.models.TestReport`
# (`.quality_gate_result.status`等を保持する)である。いずれもFoundation
# `types.py`の`Implementation`/`TestResult`(共通属性id/created_at/updated_at/
# metadataのみ)そのものではない(2026-07 統合レビューで判明した不整合の是正)。
# PR Creatorは他モジュールの内部型に直接依存(import)せず、ダックタイピングで
# 必要な属性にのみアクセスする(`template.py`/`quality_gate.py`参照)ため、
# ここでは`Any`とし、実際に期待する形状はdocstringで示すのみとする。
ImplementationResultLike = Any
"""実際には`executor.models.ImplementationResult`を指す型エイリアス。"""

TestReportLike = Any
"""実際には`tester.models.TestReport`を指す型エイリアス。"""

__all__ = [
    "ImplementationResultLike",
    "TestReportLike",
    "PullRequestTemplate",
    "RepositoryInformation",
    "BranchInformation",
    "CreatePullRequestInput",
    "AssignmentResult",
    "CreationReport",
]


@dataclass(frozen=True)
class PullRequestTemplate:
    """IS11 3.3のPRテンプレート(Summary/Purpose/Changes/Test Result/Related Issue/Notes)"""

    summary: str
    purpose: str
    changes: list[str]
    test_result: str
    related_issue: str | None
    notes: str | None = None


@dataclass(frozen=True)
class RepositoryInformation:
    """IS11 3.1のrepository_information"""

    owner: str
    name: str
    default_branch: str


@dataclass(frozen=True)
class BranchInformation:
    """IS11 3.1のbranch_information"""

    base_branch: str
    head_branch: str


@dataclass(frozen=True)
class CreatePullRequestInput:
    """IS11 3.1の入力一式を束ねたcreate_pr()向けリクエスト。

    設計書3.5はcreate_pr()の入力を"Implementation Result"と表記しているが、
    3.1で列挙された入力(workflow_id / implementation_result / test_report /
    repository_information / branch_information / project_context)をすべて
    受け取らない限りTitle/Description生成・Quality Gate判定・GitHub登録が
    実行できないため、本仕様書では3.1の入力一式をまとめた本dataclassを
    create_pr()の実引数とする。新機能の追加ではなく、3.1を実装可能な形に
    束ねたものである。

    `project_context`は、Reviewer(M12)がレビュー実行に必要とする入力のうち
    PR Creator自身の入力契約(3.1)に含まれないもの(design_document / execution_plan /
    audit_report / business_goal)を運ぶ汎用の文脈情報として扱う(2026-07 統合レビューの
    是正: Reviewer.review()はPull Request単体を入力とし他モジュールの内部型に依存しない
    設計(IS12)であるため、これらの情報はPR CreatorがPullRequest.metadataへ転記する
    ことでReviewerへ引き継ぐ)。`create_pr()`は下記のキーが存在すれば
    `PullRequest.metadata`へそのまま転記する: `design_document` / `execution_plan` /
    `audit_report` / `business_goal` / `documentation_updated`。
    """

    workflow_id: str
    implementation_result: ImplementationResultLike
    test_report: TestReportLike
    repository_information: RepositoryInformation
    branch_information: BranchInformation
    project_context: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AssignmentResult:
    """assign_reviewers()の出力(IS11 3.5)"""

    pull_request_number: int
    requested_reviewers: list[str]
    requested_team_reviewers: list[str]
    success: bool
    message: str | None = None


@dataclass(frozen=True)
class CreationReport:
    """IS11 3.4のCreation Report。ログ出力(4.5)と同一項目を保持する"""

    timestamp: datetime
    workflow_id: str
    repository: str
    branch: str
    pull_request_number: int | None
    pull_request_url: str | None
    result: str
