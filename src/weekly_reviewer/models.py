"""Weekly Reviewer (M13) のデータクラス定義(IS13 3節)。

`Review` はFoundation F01共通Domain(id/created_at/updated_at/metadataのみ)であり、
Reviewer(M12)とWeekly Reviewer(M13)の双方が利用する。両モジュールが異なる
モジュール固有属性を必要とするため、Foundation本体の`Review`は変更せず、
本モジュール側で継承したサブクラス`WeeklyReview`としてモジュール固有属性を追加する
(IS13 3.1節)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any

from foundation.types import Knowledge, PullRequest, Review
from foundation.utils import utc_now

__all__ = [
    "Project",
    "ReviewPeriod",
    "WeeklyReviewContext",
    "WeeklyAnalysis",
    "BusinessAlignmentStatus",
    "BusinessEvaluation",
    "MvpEvaluation",
    "TechnicalDebtFinding",
    "WeeklyReview",
    "WeeklyReport",
    "WeeklyReviewerConfig",
]


@dataclass(frozen=True)
class Project:
    """collect()の入力(設計書3.5節)。Foundationの共通Domain Model(F01)には
    含まれないため、設計書3.1節の入力項目からWeekly Reviewerローカルの
    値オブジェクトとして定義する(IS13 3.1節)。"""

    project_id: str
    business_goal: str | None = None
    project_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReviewPeriod:
    """設計書3.2節の「対象期間: 今週」を表す値オブジェクト。"""

    start_date: date
    end_date: date


@dataclass
class WeeklyReviewContext:
    """設計書3.1節の入力のうち、collect/analyze/evaluateの主入力(Project/
    Merged Pull Requests/Weekly Analysis)以外(review_reports, technical_debt_reports,
    knowledge, project_context)をまとめて受け渡すための補助データ。設計書3.5節の
    公開インターフェースの主入力・出力は変更せず、analyze()/evaluate()の追加引数として渡す。

    project_id・business_goal等、Projectに由来する値はproject_context経由で
    引き継ぐ(IS13 3.1節の入力項目をanalyze/evaluateへ橋渡しするための実装上の規約)。
    """

    review_reports: list[Review] = field(default_factory=list)
    technical_debt_reports: list[dict[str, Any]] = field(default_factory=list)
    knowledge: list[Knowledge] = field(default_factory=list)
    project_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class WeeklyAnalysis:
    """analyze()の出力(設計書3.5節)。実装内容の要約(2.1節)を保持する。"""

    project_id: str
    review_period: ReviewPeriod
    merged_pull_requests: list[PullRequest]
    pull_request_summaries: list[str]
    created_at: datetime = field(default_factory=utc_now)


class BusinessAlignmentStatus(str, Enum):
    ALIGNED = "aligned"
    PARTIALLY_ALIGNED = "partially_aligned"
    MISALIGNED = "misaligned"


@dataclass
class BusinessEvaluation:
    """設計書3.3節「Business Goal」評価。"""

    business_goal: str
    alignment_status: BusinessAlignmentStatus
    findings: list[str] = field(default_factory=list)


@dataclass
class MvpEvaluation:
    """設計書3.3節「MVP」評価(不要機能/過剰設計/優先順位の逆転)。"""

    unnecessary_features: list[str] = field(default_factory=list)
    over_engineering: list[str] = field(default_factory=list)
    priority_inversions: list[str] = field(default_factory=list)

    @property
    def has_issue(self) -> bool:
        return bool(self.unnecessary_features or self.over_engineering or self.priority_inversions)


@dataclass
class TechnicalDebtFinding:
    """設計書3.3節「Technical Debt」評価(重複コード/保守性/責務分離/命名/ドキュメント不足)。"""

    duplicated_code: list[str] = field(default_factory=list)
    maintainability_concerns: list[str] = field(default_factory=list)
    responsibility_violations: list[str] = field(default_factory=list)
    naming_issues: list[str] = field(default_factory=list)
    documentation_gaps: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return (
            len(self.duplicated_code)
            + len(self.maintainability_concerns)
            + len(self.responsibility_violations)
            + len(self.naming_issues)
            + len(self.documentation_gaps)
        )


@dataclass
class WeeklyReview(Review):
    """evaluate()の出力(設計書3.5節)。Foundation Review Domain(共通属性)に
    Weekly Reviewer固有属性を追加したサブクラス(3.1節参照)。

    dataclass継承の制約上、親クラス`Review`の全フィールドがdefault_factoryを
    持つため、本クラスの追加フィールドも全てデフォルト値を持たせている。
    project_id等の必須値は`evaluator.build_weekly_review()`経由でのみ生成し、
    フィールドのデフォルト値のまま利用しないことを実装規約とする(IS13 3.1節補足)。
    """

    project_id: str = ""
    review_period: ReviewPeriod | None = None
    merged_pull_requests: list[PullRequest] = field(default_factory=list)
    business_evaluation: BusinessEvaluation | None = None
    mvp_evaluation: MvpEvaluation | None = None
    technical_debt: TechnicalDebtFinding | None = None
    achievements: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    top_priority_next_week: list[str] = field(default_factory=list)


@dataclass
class WeeklyReport:
    """publish()の出力(設計書3.4節)。設計書3.4節の9項目に一致させる。
    Project Ownerへ渡す成果物として、summary_text(整形済み本文)を
    実装上の補足として追加する。"""

    id: str
    project_id: str
    review_period: ReviewPeriod
    merged_pull_requests: list[PullRequest]
    business_evaluation: BusinessEvaluation
    mvp_evaluation: MvpEvaluation
    technical_debt: TechnicalDebtFinding
    achievements: list[str]
    risks: list[str]
    recommendations: list[str]
    top_priority_next_week: list[str]
    summary_text: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WeeklyReviewerConfig:
    """F03: ConfigurationClient.get("weekly_reviewer", key) 経由で取得する設定値の型。
    設計書5.2節(F03)「Configurationからレビュー対象期間・Business Goalを取得する」に対応する。"""

    review_period_days: int = 7
    business_goal: str | None = None
