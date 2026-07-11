"""Reviewer (M12) 固有Domain定義(IS12 3節)。

Foundation `types.py` の `Review` Domain(共通属性 id/created_at/updated_at/metadata)を
継承し、Reviewer固有属性を追加する。`PullRequest` / `Implementation` はFoundation定義を
そのまま参照し、再定義しない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from foundation.types import Implementation, PullRequest, Review

__all__ = [
    "ReviewDecision",
    "IssueCategory",
    "Severity",
    "ReviewIssue",
    "TechnicalDebtItem",
    "BusinessEvaluation",
    "MVPAssessment",
    "ReviewInput",
    "ReviewReport",
    "ReviewOutcome",
]


class ReviewDecision(str, Enum):
    """設計書 3.3 の判定区分。"""

    APPROVED = "APPROVED"
    APPROVED_WITH_COMMENT = "APPROVED_WITH_COMMENT"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REJECTED = "REJECTED"


class IssueCategory(str, Enum):
    """設計書 3.2 のレビュー観点に対応するIssue分類。"""

    REQUIREMENT = "requirement"
    DESIGN = "design"
    MVP = "mvp"
    BUSINESS = "business"
    TECHNICAL_DEBT = "technical_debt"
    MAINTAINABILITY = "maintainability"
    DOCUMENTATION = "documentation"


class Severity(str, Enum):
    BLOCKER = "blocker"
    MAJOR = "major"
    MINOR = "minor"


@dataclass
class ReviewIssue:
    """Review Reportの Issues 1件。"""

    category: IssueCategory
    description: str
    severity: Severity


@dataclass
class TechnicalDebtItem:
    """Review Reportの Technical Debt 1件。"""

    description: str
    location: str
    severity: Severity


@dataclass
class BusinessEvaluation:
    """evaluate_business() の出力(Business Evaluation)。"""

    aligned_with_business_goal: bool
    business_score: float
    notes: list[str] = field(default_factory=list)


@dataclass
class MVPAssessment:
    """evaluate_mvp() の出力(MVP Assessment)。設計書4.4に対応。"""

    is_mvp_compliant: bool
    unnecessary_abstractions: list[str] = field(default_factory=list)
    unnecessary_features: list[str] = field(default_factory=list)
    over_engineering_flags: list[str] = field(default_factory=list)


@dataclass
class ReviewInput:
    """review() 実行に必要な入力一式(設計書 3.1)。"""

    workflow_id: str
    execution_plan: Any
    design_document: Any
    audit_report: Any
    implementation_result: Implementation
    test_report: Any
    pull_request: PullRequest
    project_context: Any
    business_goal: Any


@dataclass
class ReviewReport(Review):
    """Foundation.Review を継承した Review Report(設計書 3.4)。"""

    workflow_id: str = ""
    pull_request_id: str = ""
    result: ReviewDecision = ReviewDecision.CHANGES_REQUESTED
    strengths: list[str] = field(default_factory=list)
    issues: list[ReviewIssue] = field(default_factory=list)
    technical_debt: list[TechnicalDebtItem] = field(default_factory=list)
    business_evaluation: BusinessEvaluation | None = None
    recommendations: list[str] = field(default_factory=list)


@dataclass
class ReviewOutcome:
    """publish_review() の出力(Review Result)。マージ実行自体は行わず、次モジュール名のみを示す。"""

    review_id: str
    decision: ReviewDecision
    next_module: str  # "merge_manager" | "executor"
    published_at: datetime
