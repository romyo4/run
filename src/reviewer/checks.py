"""レビュー観点ごとの判定関数(IS12 4.2 / 設計書 3.2, 3.6)。

`design_document` / `audit_report` / `test_report` / `business_goal` / `project_context` は
Any型(モジュール横断の共通スキーマがまだ確定していない入力)であるため、dict風アクセス
(`.get`)とオブジェクト属性アクセス(`getattr`)の双方を許容する `_field` ヘルパーを介して
値を読み取る。ここに新しい抽象化フレームワークは導入しない(MVP維持, 設計書4.4)。
"""

from __future__ import annotations

from typing import Any

from foundation.types import Implementation, PullRequest
from reviewer.domain import (
    BusinessEvaluation,
    IssueCategory,
    MVPAssessment,
    ReviewDecision,
    ReviewIssue,
    Severity,
    TechnicalDebtItem,
)
from reviewer.exceptions import InvalidReviewInputError

__all__ = [
    "check_requirements",
    "check_design_alignment",
    "check_mvp_compliance",
    "check_business_alignment",
    "check_technical_debt",
    "check_maintainability",
    "check_documentation",
    "determine_decision",
]


def _field(source: Any, key: str, default: Any = None) -> Any:
    """dict風・属性風いずれの `source` からも `key` の値を読み取る。"""
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def check_requirements(design_document: Any, implementation_result: Implementation, test_report: Any) -> list[ReviewIssue]:
    """要件充足を確認する(Requirement Review)。

    `test_report` の `unmet_requirements`(未充足の要件一覧)を基準に判定する。
    """
    unmet_requirements = _field(test_report, "unmet_requirements", []) or []
    return [
        ReviewIssue(
            category=IssueCategory.REQUIREMENT,
            description=f"Requirement not met: {requirement}",
            severity=Severity.BLOCKER,
        )
        for requirement in unmet_requirements
    ]


def check_design_alignment(design_document: Any, implementation_result: Implementation) -> list[ReviewIssue]:
    """Designからの逸脱を確認する(Design Review)。

    `implementation_result.metadata` の `design_deviations`(検出済みのDesign逸脱一覧)を
    基準に判定する。
    """
    deviations = (implementation_result.metadata or {}).get("design_deviations", []) or []
    return [
        ReviewIssue(
            category=IssueCategory.DESIGN,
            description=f"Design deviation: {deviation}",
            severity=Severity.MAJOR,
        )
        for deviation in deviations
    ]


def check_mvp_compliance(implementation_result: Implementation) -> MVPAssessment:
    """MVPに不要な実装の有無を確認する(設計書4.4)。"""
    metadata = implementation_result.metadata or {}
    unnecessary_abstractions = list(metadata.get("unnecessary_abstractions", []) or [])
    unnecessary_features = list(metadata.get("unnecessary_features", []) or [])
    over_engineering_flags = list(metadata.get("over_engineering_flags", []) or [])
    is_mvp_compliant = not (unnecessary_abstractions or unnecessary_features or over_engineering_flags)
    return MVPAssessment(
        is_mvp_compliant=is_mvp_compliant,
        unnecessary_abstractions=unnecessary_abstractions,
        unnecessary_features=unnecessary_features,
        over_engineering_flags=over_engineering_flags,
    )


def check_business_alignment(pull_request: PullRequest, business_goal: Any) -> BusinessEvaluation:
    """Business Goalとの整合性を確認する(Business Review)。

    `business_goal` の `required_keywords` が `pull_request.metadata["summary"]` に
    含まれる割合を business_score とする。閾値判定(config.min_business_score)は
    呼び出し側(ReviewerModule)の責務とし、ここでは0.5を暫定既定値として扱う。
    """
    required_keywords = _field(business_goal, "required_keywords", []) or []
    summary = (pull_request.metadata or {}).get("summary", "") or ""
    summary_lower = summary.lower()

    if not required_keywords:
        return BusinessEvaluation(
            aligned_with_business_goal=True,
            business_score=1.0,
            notes=["business_goal に required_keywords の指定なし"],
        )

    matched = [kw for kw in required_keywords if kw.lower() in summary_lower]
    missing = [kw for kw in required_keywords if kw not in matched]
    business_score = len(matched) / len(required_keywords)
    notes = []
    if matched:
        notes.append(f"matched keywords: {', '.join(matched)}")
    if missing:
        notes.append(f"missing keywords: {', '.join(missing)}")

    return BusinessEvaluation(
        aligned_with_business_goal=business_score >= 0.5,
        business_score=business_score,
        notes=notes,
    )


def check_technical_debt(implementation_result: Implementation, audit_report: Any) -> list[TechnicalDebtItem]:
    """技術的負債の増加有無を確認する(Technical Debt Review)。"""
    items = _field(audit_report, "technical_debt_items", []) or []
    result: list[TechnicalDebtItem] = []
    for item in items:
        result.append(
            TechnicalDebtItem(
                description=_field(item, "description", ""),
                location=_field(item, "location", ""),
                severity=Severity(_field(item, "severity", Severity.MINOR)),
            )
        )
    return result


def check_maintainability(implementation_result: Implementation) -> list[ReviewIssue]:
    """保守性を損なっていないかを確認する。"""
    metadata = implementation_result.metadata or {}
    if not metadata.get("maintainability_reduced", False):
        return []
    reason = metadata.get("maintainability_notes", "maintainability reduced")
    return [
        ReviewIssue(
            category=IssueCategory.MAINTAINABILITY,
            description=str(reason),
            severity=Severity.MAJOR,
        )
    ]


def check_documentation(pull_request: PullRequest) -> list[ReviewIssue]:
    """ドキュメント更新の有無を確認する。"""
    metadata = pull_request.metadata or {}
    if metadata.get("documentation_updated", True):
        return []
    return [
        ReviewIssue(
            category=IssueCategory.DOCUMENTATION,
            description="Documentation was not updated for this change",
            severity=Severity.MINOR,
        )
    ]


def determine_decision(
    issues: list[ReviewIssue],
    mvp_assessment: MVPAssessment,
    business_evaluation: BusinessEvaluation,
    technical_debt: list[TechnicalDebtItem],
) -> ReviewDecision:
    """Business Goal ＞ コードの美しさ ＞ 個人の好み(設計書4.3)の優先順で
    APPROVED/APPROVED_WITH_COMMENT/CHANGES_REQUESTED/REJECTEDを決定する。

    優先順位:
    1. blocker Issue が存在する場合は REJECTED(Safety原則)。
    2. MVP不適合(is_mvp_compliant=False)の場合は CHANGES_REQUESTED(設計書4.4)。
    3. Business Goalと不整合の場合は CHANGES_REQUESTED(設計書4.3、個人の好みより優先)。
    4. major相当のIssue/技術的負債が残る場合は CHANGES_REQUESTED。
    5. minorのIssueのみの場合は APPROVED_WITH_COMMENT。
    6. 上記いずれにも該当しない場合は APPROVED。
    """
    if mvp_assessment is None:
        raise InvalidReviewInputError("mvp_assessment must not be None")
    if business_evaluation is None:
        raise InvalidReviewInputError("business_evaluation must not be None")

    if any(issue.severity == Severity.BLOCKER for issue in issues):
        return ReviewDecision.REJECTED

    if not mvp_assessment.is_mvp_compliant:
        return ReviewDecision.CHANGES_REQUESTED

    if not business_evaluation.aligned_with_business_goal:
        return ReviewDecision.CHANGES_REQUESTED

    has_major = any(issue.severity == Severity.MAJOR for issue in issues) or any(
        item.severity in (Severity.MAJOR, Severity.BLOCKER) for item in technical_debt
    )
    if has_major:
        return ReviewDecision.CHANGES_REQUESTED

    has_minor = any(issue.severity == Severity.MINOR for issue in issues)
    if has_minor:
        return ReviewDecision.APPROVED_WITH_COMMENT

    return ReviewDecision.APPROVED
