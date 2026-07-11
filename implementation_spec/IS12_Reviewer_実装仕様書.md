# IS12 Reviewer 実装仕様書

対象設計書: `M12 Reviewer.txt`(確定版) / 前提: `M00 Foundation.txt`(F00-F03)
Design Version: `DESIGN_VERSION = "v1.0"`

---

## 1. モジュール概要

Reviewer は、AI Development Pipeline において PR Creator が作成した Pull Request を対象に、要件充足・Design整合性・MVP適合性・Business Goal整合性・技術的負債・保守性・ドキュメント更新の観点からレビューを行い、`APPROVED` / `APPROVED_WITH_COMMENT` / `CHANGES_REQUESTED` / `REJECTED` のいずれかを判定するモジュールである。Reviewer は**レビューおよび承認判定のみ**を担当し、コード修正・設計変更・Pull Request更新・テスト実行・GitHubマージは一切行わない。判定は Business Goal ＞ コードの美しさ ＞ 個人の好み の優先順で行い、不要な抽象化・不要な機能・過剰設計を検出した場合は差し戻す(MVP維持)。判定結果は `APPROVED` なら Merge Manager、`CHANGES_REQUESTED` なら Executor へ引き渡す想定とし、実際のルーティング実行(マージ・差し戻し実行)自体は Reviewer の責務外である。

---

## 2. ファイル構成

```text
src/reviewer/
├── __init__.py         # パッケージ公開エクスポート(ReviewerModule, domain型, 例外)
├── domain.py            # Reviewer固有dataclass定義(Foundation Domainを利用/拡張)
├── checks.py            # レビュー観点ごとの判定関数(要件/設計/MVP/Business/技術的負債/保守性/文書化)
├── reviewer.py           # ReviewerModule(BaseModule)本体、公開インターフェース実装
├── config.py             # ConfigurationClient経由のレビュー設定取得
├── exceptions.py         # Reviewer固有例外(Foundationエラー階層を継承)
└── tests/
    ├── __init__.py
    ├── test_domain.py
    ├── test_checks.py
    ├── test_reviewer.py
    └── test_config.py
```

依存方向: `reviewer.py` → `checks.py` / `config.py` / `domain.py` / `exceptions.py` → `foundation.*`。Reviewerは他業務モジュール(PR Creator, Executor等)のコードに依存しない(Domain型のみ参照)。

---

## 3. データクラス定義

Foundation `types.py` が定義する `Review` Domain(共通属性 `id` / `created_at` / `updated_at` / `metadata` を持つ、M00 3.3節)を継承し、Reviewer固有属性を追加する。`PullRequest`(PR Creator/Foundation定義)・`Implementation`(Executor/Foundation定義)は再定義せず、Foundationから参照するのみとする。

```python
# src/reviewer/domain.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from foundation.types import Review, PullRequest, Implementation


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
```

備考: Foundation `types.py` の `Review` フィールド定義(型・デフォルト有無)は M00 実装時に確定する。本仕様は M00 3.3節の共通属性(`id`, `created_at`, `updated_at`, `metadata`)を前提とし、`ReviewReport` の追加属性はすべてデフォルト値を持たせることで dataclass 継承時のフィールド順序制約(デフォルトなし→ありの順)に抵触しないようにする。

---

## 4. クラス・関数シグネチャ

### 4.1 ReviewerModule(公開インターフェース、設計書 3.5)

```python
# src/reviewer/reviewer.py
from __future__ import annotations

from foundation.base_module import BaseModule
from foundation.result import Result
from foundation.interfaces import ConfigurationClient

from reviewer.domain import (
    ReviewReport,
    ReviewOutcome,
    BusinessEvaluation,
    MVPAssessment,
)
from foundation.types import PullRequest, Implementation


class ReviewerModule(BaseModule):
    def __init__(self, configuration_client: ConfigurationClient) -> None: ...

    def name(self) -> str:
        """モジュール名 'reviewer' を返す。"""

    def health_check(self) -> Result[bool]:
        """Logger/ConfigurationClient疎通確認結果を返す。"""

    def review(self, pull_request: PullRequest) -> Result[ReviewReport]:
        """Pull Requestを入力に、要件/設計/Business/技術的負債の順でレビューし
        Review Reportを返す(設計書3.5, 3.6)。"""

    def evaluate_business(self, pull_request: PullRequest) -> Result[BusinessEvaluation]:
        """Business Goalとの整合性を評価する(設計書3.5)。"""

    def evaluate_mvp(self, implementation_result: Implementation) -> Result[MVPAssessment]:
        """MVP適合性(不要な抽象化/不要な機能/過剰設計)を評価する(設計書3.5, 4.4)。"""

    def publish_review(self, review_report: ReviewReport) -> Result[ReviewOutcome]:
        """Review Reportを最終Review Resultとして確定する。
        マージ実行・PR更新は行わず、次モジュール名のみを決定する(設計書3.5, 4.1, 4.2)。"""
```

### 4.2 レビュー観点別チェック関数(設計書 3.2, 3.6)

```python
# src/reviewer/checks.py
from __future__ import annotations
from typing import Any

from reviewer.domain import (
    ReviewIssue,
    TechnicalDebtItem,
    BusinessEvaluation,
    MVPAssessment,
    ReviewDecision,
)
from foundation.types import Implementation, PullRequest


def check_requirements(design_document: Any, implementation_result: Implementation,
                        test_report: Any) -> list[ReviewIssue]:
    """要件充足を確認する(Requirement Review)。"""

def check_design_alignment(design_document: Any, implementation_result: Implementation) -> list[ReviewIssue]:
    """Designからの逸脱を確認する(Design Review)。"""

def check_mvp_compliance(implementation_result: Implementation) -> MVPAssessment:
    """MVPに不要な実装の有無を確認する(設計書4.4)。"""

def check_business_alignment(pull_request: PullRequest, business_goal: Any) -> BusinessEvaluation:
    """Business Goalとの整合性を確認する(Business Review)。"""

def check_technical_debt(implementation_result: Implementation, audit_report: Any) -> list[TechnicalDebtItem]:
    """技術的負債の増加有無を確認する(Technical Debt Review)。"""

def check_maintainability(implementation_result: Implementation) -> list[ReviewIssue]:
    """保守性を損なっていないかを確認する。"""

def check_documentation(pull_request: PullRequest) -> list[ReviewIssue]:
    """ドキュメント更新の有無を確認する。"""

def determine_decision(
    issues: list[ReviewIssue],
    mvp_assessment: MVPAssessment,
    business_evaluation: BusinessEvaluation,
    technical_debt: list[TechnicalDebtItem],
) -> ReviewDecision:
    """Business Goal ＞ コードの美しさ ＞ 個人の好み(設計書4.3)の優先順で
    APPROVED/APPROVED_WITH_COMMENT/CHANGES_REQUESTED/REJECTEDを決定する。
    MVP不適合(is_mvp_compliant=False)またはblocker Issue存在時は
    CHANGES_REQUESTED以下に倒す(Safety原則, 設計書4.4)。"""
```

### 4.3 設定取得(設計書 F03 / 3.5)

```python
# src/reviewer/config.py
from __future__ import annotations
from dataclasses import dataclass

from foundation.result import Result
from foundation.interfaces import ConfigurationClient

MODULE_NAME = "reviewer"


@dataclass
class ReviewerConfig:
    min_business_score: float
    blocker_severity_blocks_approval: bool


def get_reviewer_config(client: ConfigurationClient) -> Result[ReviewerConfig]:
    """ConfigurationClient.get(MODULE_NAME, key) を用いてレビュー設定を取得する(F03)。
    Foundation自体は値をキャッシュしないため、Reviewer側でも呼び出しごとに取得する。"""
```

### 4.4 例外(Foundationエラー階層を継承)

```python
# src/reviewer/exceptions.py
from __future__ import annotations
from foundation.errors import ValidationError


class InvalidReviewInputError(ValidationError):
    """review()/evaluate_business()/evaluate_mvp()の必須入力が欠落・不正な場合。"""
```

### 4.5 `__init__.py` の公開エクスポート

```python
# src/reviewer/__init__.py
from reviewer.reviewer import ReviewerModule
from reviewer.domain import (
    ReviewDecision,
    IssueCategory,
    Severity,
    ReviewIssue,
    TechnicalDebtItem,
    BusinessEvaluation,
    MVPAssessment,
    ReviewInput,
    ReviewReport,
    ReviewOutcome,
)
from reviewer.exceptions import InvalidReviewInputError

__all__ = [
    "ReviewerModule",
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
    "InvalidReviewInputError",
]
```

---

## 5. エラー処理

- 公開メソッド(`review`, `evaluate_business`, `evaluate_mvp`, `publish_review`, `health_check`)は例外を送出せず、必ず `Result[T]` を返す。内部で発生した例外は各メソッドの境界で捕捉し `Result(success=False, value=None, error=...)` に変換する。
- 入力検証には Foundation `validation.py` の `require_not_none` / `require_non_empty` / `require_in` を用いる。これらが送出する `ValidationError`(または `InvalidReviewInputError`)を境界で捕捉する。例: `review()` で `pull_request` が `None` の場合、`require_not_none(pull_request, "pull_request")` が `InvalidReviewInputError` を送出 → 捕捉して `Result[ReviewReport](success=False, error=InvalidReviewInputError(...))` を返す。
- `get_reviewer_config()` が `Result[ReviewerConfig](success=False)` を返した場合(Configuration Manager未応答等)、Reviewerは即座にレビューを打ち切り `ConfigurationError` を `Result.error` に格納して返す(Safety原則: 設定取得不能時はレビュー未実施のまま安全側に倒す)。
- `determine_decision` 内部でのロジック上の不整合(例: `mvp_assessment`が`None`)は `InvalidReviewInputError` として扱い、`REJECTED` を安易に自動返却しない(不確実性を隠さない)。
- Reviewer固有の新しい基底例外(`ReviewerError`等)は追加しない。Foundation `errors.py` の `ValidationError` / `ConfigurationError` をそのまま利用する(4.4節参照)。

---

## 6. ロギング仕様

- `foundation.logger.get_logger("reviewer")` によりモジュール起動時に一度だけ Logger を取得し、`ReviewerModule` インスタンスに保持する。
- 出力形式は Foundation規約(`timestamp | module_name | level | message`)に従う。
- `review()` 完了時(成功・失敗いずれも)および `publish_review()` 完了時に、設計書4.5で定義された項目をINFOレベルで1行にまとめて記録する。

```text
timestamp
workflow_id
review_id
review_result
technical_debt_count
business_score
result
```

- 上記のうち `technical_debt_count` は `len(review_report.technical_debt)`、`business_score` は `review_report.business_evaluation.business_score` から取得する。
- 入力検証エラー・Configuration取得エラーはERRORレベルで `workflow_id` と例外種別のみを記録する。
- Pull Requestの本文・diff内容、Secret・Access Token・Credentialはいかなるログレベルでも出力しない(設計書4.5)。

---

## 7. Unit Testケース一覧(unittest)

### tests/test_domain.py
- `test_review_decision_enum_has_four_values`
- `test_review_report_default_result_is_changes_requested`
- `test_review_report_inherits_review_common_attributes`
- `test_review_issue_creation_with_category_and_severity`
- `test_technical_debt_item_creation`
- `test_business_evaluation_creation`
- `test_mvp_assessment_default_lists_are_independent_instances`

### tests/test_checks.py
- `test_check_requirements_returns_issue_when_requirement_unmet`
- `test_check_requirements_returns_empty_list_when_satisfied`
- `test_check_design_alignment_returns_issue_when_design_deviation_detected`
- `test_check_mvp_compliance_flags_unnecessary_abstraction`
- `test_check_mvp_compliance_flags_unnecessary_feature`
- `test_check_mvp_compliance_flags_over_engineering`
- `test_check_mvp_compliance_is_compliant_when_no_violation`
- `test_check_business_alignment_computes_business_score`
- `test_check_business_alignment_marks_not_aligned_when_goal_mismatch`
- `test_check_technical_debt_returns_items_with_severity`
- `test_check_maintainability_returns_issue_when_maintainability_reduced`
- `test_check_documentation_returns_issue_when_docs_not_updated`
- `test_determine_decision_returns_approved_when_no_issues_and_mvp_compliant`
- `test_determine_decision_returns_approved_with_comment_for_minor_issue_only`
- `test_determine_decision_returns_changes_requested_when_mvp_not_compliant`
- `test_determine_decision_returns_rejected_when_blocker_issue_present`
- `test_determine_decision_prioritizes_business_goal_over_style_preference`

### tests/test_reviewer.py
- `test_name_returns_reviewer`
- `test_health_check_returns_success_result_when_dependencies_ok`
- `test_review_returns_success_result_with_review_report`
- `test_review_returns_failure_result_when_pull_request_is_none`
- `test_review_report_contains_review_id_result_strengths_issues_technical_debt_business_evaluation_recommendations`
- `test_review_does_not_call_any_code_modification_api`
- `test_review_does_not_call_any_pull_request_update_api`
- `test_evaluate_business_returns_success_result_with_business_evaluation`
- `test_evaluate_mvp_returns_success_result_with_mvp_assessment`
- `test_evaluate_mvp_returns_failure_result_when_implementation_result_is_none`
- `test_publish_review_returns_success_result_with_review_outcome`
- `test_publish_review_routes_approved_decision_to_merge_manager`
- `test_publish_review_routes_changes_requested_decision_to_executor`
- `test_publish_review_does_not_execute_merge`
- `test_review_returns_failure_result_when_configuration_unavailable`

### tests/test_config.py
- `test_get_reviewer_config_returns_success_result`
- `test_get_reviewer_config_uses_module_name_reviewer`
- `test_get_reviewer_config_returns_failure_result_when_client_fails`

---

## 8. MVP範囲の明記

本実装は `M12 Reviewer.txt` 5.3節「重厚壮大化監査」により**対象外・削除済み**とされた以下の機能を実装しない。

- AIコード自動修正
- 自動マージ
- Release判定
- リスクスコアAI
- 開発者評価
- コスト分析
- 長期ロードマップ評価

また、設計書2.2節・4章の制約により、以下もReviewerの責務外として実装しない。

- 要件変更・設計変更・コード修正
- テスト実行・Build実行
- Pull Request作成・更新
- GitHubマージ・デプロイ

`publish_review()` はレビュー結果(Review Result)を確定し次モジュール名を示すのみであり、実際のマージ実行・Pull Request更新・差し戻し実行は Merge Manager / Executor 側の責務とする。
