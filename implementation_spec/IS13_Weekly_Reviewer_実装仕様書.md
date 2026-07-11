# IS13 Weekly Reviewer (Fable) 実装仕様書

- 対象設計書: `M13 Weekly Reviewer (Fable).txt`(確定済み詳細設計書、Design Freeze v1.0)
- 参照仕様: `M00 Foundation.txt`(F00〜F03、共通Result/Error/Logging規約)
- 対象バージョン: `DESIGN_VERSION = "v1.0"`
- 実装言語: Python 3.13
- 配置先: `src/weekly_reviewer/`

本書は M13 Weekly Reviewer (Fable) の詳細設計書を実装可能な粒度に具体化したものであり、設計書に記載のない機能・APIを追加しない。設計書の記述と本書が矛盾する場合は設計書を正とする。

---

## 1. モジュール概要

Weekly Reviewer (Fable) は、AI Development Pipeline において一定期間(通常1週間)にマージされた Pull Request 群を俯瞰し、個々のPRの品質ではなく**プロジェクト全体が事業目的(Business Goal)へ向かって進んでいるか**を、Business Goal > MVP > Architecture > Coding Style の優先順位で評価するモジュールである。Fable をレビューエンジンとして利用し、Business Goalとの整合性・MVP適合性(不要機能/過剰設計/優先順位逆転)・技術的負債(重複コード/保守性/責務分離/命名/ドキュメント不足)・開発の方向性(今週の進捗/次の優先事項)を評価したうえで、来週最優先で取り組むべき改善提案を含む Weekly Report を作成し Project Owner へ引き渡す。要件分析・設計・コード生成・Pull Requestレビュー・マージ・リリース・コード修正・Design修正は一切行わず、実施判断は行わない(提案のみ)。

---

## 2. ファイル構成

```text
src/weekly_reviewer/
├── __init__.py            # 公開インターフェース(WeeklyReviewer, 主要dataclass)のエクスポート
├── weekly_reviewer.py      # WeeklyReviewerクラス本体(BaseModule継承)。collect/analyze/evaluate/publishの実装
├── models.py               # Project/ReviewPeriod/WeeklyReviewContext/WeeklyAnalysis/BusinessEvaluation/
│                           #   MvpEvaluation/TechnicalDebtFinding/WeeklyReview/WeeklyReport/
│                           #   WeeklyReviewerConfig 等のdataclass定義
├── collector.py            # collect()の実処理: 対象期間のMerge済みPull Request収集
├── analyzer.py             # analyze()の実処理: PR群の要約 → WeeklyAnalysis構築
├── fable_client.py         # Fableレビューエンジン呼び出しの抽象化層(Adapter Pattern、F00)
├── evaluator.py            # evaluate()の実処理: Business/MVP/技術的負債/優先順位評価 → WeeklyReview構築
├── reporter.py             # publish()の実処理: WeeklyReview → WeeklyReport整形
├── errors.py               # Weekly Reviewer固有例外(Foundationのエラー階層を継承)
├── logging_utils.py        # 所定5項目のログ整形、Secret/Token/Credentialのマスク処理
└── tests/
    ├── __init__.py
    ├── test_weekly_reviewer.py
    ├── test_models.py
    ├── test_collector.py
    ├── test_analyzer.py
    ├── test_fable_client.py
    ├── test_evaluator.py
    └── test_reporter.py
```

`fable_client.py` は Fable という外部レビューエンジンとの差異を吸収する層とし、F00「Adapter Pattern」原則に従う。評価基準(何を不要機能とみなすか等)の解釈自体はFable側の責務とし、`evaluator.py` はFableの評価結果を`WeeklyReview`へ組み立てる役割に限定する。

---

## 3. データクラス定義

### 3.1 Foundationの共通Domain Modelの利用(F01)

設計書 5.2節(F01)の通り、Weekly Reviewer は Foundationの `Review` Domain(共通属性 `id / created_at / updated_at / metadata` のみを持つ)を利用する。ただし `Review` はFoundationのF01対応表上 **Reviewer(M12)とWeekly Reviewer(M13)の双方が利用する**Domainであり、両モジュールは異なるモジュール固有属性を必要とする(M12は`Result/Strengths/Issues`等、M13は`Review Period/Business Evaluation`等)。そのため、Tester(IS10)がFoundation本体の`TestResult`へ直接属性追加した方式とは異なり、本書では `foundation.types.Review` 本体は共通属性のみのまま変更せず、`src/weekly_reviewer/models.py` 側で `Review` を継承したサブクラス `WeeklyReview` としてモジュール固有属性を追加する。これはFoundation 3.3節「モジュール固有の属性はモジュール側の詳細設計書で追加定義する」を、複数モジュールが同一Domainを共有する場合における実装上の補完判断として解釈したものであり、設計書の明文規定ではない点に留意する(要確認事項)。

`collect()` の入力型として設計書3.5節に明記された「Project」は、Foundation F01のDomain Model一覧(13種)に含まれない。設計書3.1節の入力項目(`project_id` / `business_goal` / `project_context`)から、Weekly Reviewerローカルの入力値オブジェクトとして最小限に定義する(Foundation Domainとしては追加しない)。

```python
# src/weekly_reviewer/models.py
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any

from foundation.types import Knowledge, PullRequest, Review
from foundation.utils import generate_id, utc_now


@dataclass(frozen=True)
class Project:
    """collect()の入力(設計書3.5節)。Foundationの共通Domain Model(F01)には
    含まれないため、設計書3.1節の入力項目からWeekly Reviewerローカルの
    値オブジェクトとして定義する。"""
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
    公開インターフェースの主入力・出力は変更せず、analyze()/evaluate()の追加引数として渡す。"""
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
    Weekly Reviewer固有属性を追加したサブクラス(3.1節参照)。"""
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
    Project Ownerへ渡す成果物として、Tester(IS10)のTestReportに倣い
    summary_text(整形済み本文)を実装上の補足として追加する。"""
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
```

補足(要確認事項): `WeeklyReview` は dataclass継承の制約上、親クラス`Review`の全フィールドが`default_factory`を持つため、`WeeklyReview`側の追加フィールドも全てデフォルト値を持たせている。`project_id`等の必須値は、後述`evaluator.py`側のビルダー関数(`build_weekly_review`)経由でのみ生成し、フィールドのデフォルト値のまま利用しないことを実装規約とする。

---

## 4. クラス・関数シグネチャ

### 4.1 `weekly_reviewer.py`(公開インターフェース、設計書3.5節)

```python
import logging

from foundation.base_module import BaseModule
from foundation.result import Result
from foundation.types import PullRequest

from weekly_reviewer.fable_client import FableClient
from weekly_reviewer.models import (
    Project,
    WeeklyAnalysis,
    WeeklyReport,
    WeeklyReview,
    WeeklyReviewContext,
    WeeklyReviewerConfig,
)


class WeeklyReviewer(BaseModule):
    def __init__(
        self,
        config: WeeklyReviewerConfig,
        logger: logging.Logger,
        fable_client: FableClient,
    ) -> None: ...

    def name(self) -> str: ...

    def health_check(self) -> Result[bool]: ...

    def collect(self, project: Project) -> Result[list[PullRequest]]:
        """設計書3.5節。対象期間(review_period)のMerge済みPull Requestを収集する。
        review_period は ConfigurationClient.get("weekly_reviewer", "review_period_days")
        (F03、既定値7日)から算出する。"""

    def analyze(
        self,
        merged_pull_requests: list[PullRequest],
        context: WeeklyReviewContext | None = None,
    ) -> Result[WeeklyAnalysis]:
        """設計書3.5節。Merged Pull Requestsを要約しWeekly Analysisを構築する。
        contextは設計書3.1節の入力(review_reports等)を後続evaluate()へ引き継ぐための
        補助引数であり、公開インターフェースの主入出力は変更しない。"""

    def evaluate(
        self,
        weekly_analysis: WeeklyAnalysis,
        context: WeeklyReviewContext | None = None,
    ) -> Result[WeeklyReview]:
        """設計書3.5節。Business Goal > MVP > Technical Debt > Development Directionの順(4.3節)で
        Fableへ評価を委譲し、Weekly Reviewを構築する。business_goalが引数で得られない場合は
        ConfigurationClient.get("weekly_reviewer", "business_goal")から取得する。"""

    def publish(self, weekly_review: WeeklyReview) -> Result[WeeklyReport]:
        """設計書3.5節。Weekly ReviewからWeekly Reportを生成する。Project Ownerへの
        引き渡し(通知送信等)自体はWeekly Reviewerの責務外であり、戻り値のWeeklyReportを
        呼び出し元(Scheduler/Notification等)へ返すのみとする(2.2節・4.4節)。"""
```

Weekly Reviewer は 3.6節の処理フロー(Collect → Business Review → MVP Review → Technical Debt Review → Priority Analysis → Weekly Report)のうち、Collect〜Weekly Report生成までを担当し、Project Ownerへの配信自体(通知等)は呼び出し元が行う。これは Weekly Reviewer の責務(4.1節: 修正しない、4.4節: 提案のみ行う)と整合する。

### 4.2 `collector.py`

```python
from foundation.result import Result
from foundation.types import PullRequest

from weekly_reviewer.models import Project, ReviewPeriod


def collect_merged_pull_requests(
    project: Project,
    review_period: ReviewPeriod,
) -> Result[list[PullRequest]]:
    """設計書3.2節。対象期間内にMergeされたPull Requestのみを収集する。
    Review Report/Test Report/Design Audit/Technical Debtの収集(3.2節)は
    本関数の責務外とし、WeeklyReviewContext経由で別途受け渡す(3.1節参照)。"""


def resolve_review_period(review_period_days: int, today: "date") -> ReviewPeriod:
    """review_period_days(既定7日)から対象期間(start_date/end_date)を算出する。"""
```

### 4.3 `analyzer.py`

```python
from foundation.result import Result
from foundation.types import PullRequest

from weekly_reviewer.models import Project, ReviewPeriod, WeeklyAnalysis


def build_weekly_analysis(
    project: Project,
    review_period: ReviewPeriod,
    merged_pull_requests: list[PullRequest],
) -> Result[WeeklyAnalysis]:
    """merged_pull_requestsそれぞれの実装内容を要約し(2.1節)、WeeklyAnalysisを構築する。"""


def summarize_pull_request(pull_request: PullRequest) -> str:
    """単一Pull Requestの実装内容を1行程度の要約文字列に変換する。"""
```

### 4.4 `fable_client.py`(Adapter Pattern、F00)

```python
from abc import ABC, abstractmethod

from foundation.result import Result
from foundation.types import Review

from weekly_reviewer.models import (
    BusinessEvaluation,
    MvpEvaluation,
    TechnicalDebtFinding,
    WeeklyAnalysis,
)


class FableClient(ABC):
    """Fableレビューエンジンとの差異を吸収するAdapter層(F00: Adapter Pattern)。
    評価基準そのものはFable側の実装/プロンプトに委ね、本インターフェースは
    呼び出し規約のみを定義する。"""

    @abstractmethod
    def review_business_alignment(
        self, business_goal: str, weekly_analysis: WeeklyAnalysis
    ) -> Result[BusinessEvaluation]:
        """設計書3.3節Business Goal評価。"""

    @abstractmethod
    def review_mvp_fitness(
        self, weekly_analysis: WeeklyAnalysis
    ) -> Result[MvpEvaluation]:
        """設計書3.3節MVP評価。"""

    @abstractmethod
    def review_technical_debt(
        self,
        weekly_analysis: WeeklyAnalysis,
        review_reports: list[Review],
        technical_debt_reports: list[dict],
    ) -> Result[TechnicalDebtFinding]:
        """設計書3.3節Technical Debt評価。"""

    @abstractmethod
    def recommend_priorities(
        self,
        weekly_analysis: WeeklyAnalysis,
        business_evaluation: BusinessEvaluation,
        mvp_evaluation: MvpEvaluation,
        technical_debt: TechnicalDebtFinding,
    ) -> Result[tuple[list[str], list[str], list[str], list[str]]]:
        """設計書3.3節Development Direction評価。戻り値は
        (achievements, risks, recommendations, top_priority_next_week)の順のタプル。"""
```

### 4.5 `evaluator.py`

```python
from foundation.result import Result

from weekly_reviewer.fable_client import FableClient
from weekly_reviewer.models import WeeklyAnalysis, WeeklyReview, WeeklyReviewContext


def evaluate_weekly_analysis(
    weekly_analysis: WeeklyAnalysis,
    business_goal: str,
    context: WeeklyReviewContext,
    fable_client: FableClient,
) -> Result[WeeklyReview]:
    """設計書4.3節の優先順位(Business Goal > MVP > Architecture > Coding Style)に従い、
    Business Goal評価 → MVP評価 → Technical Debt評価 → 優先順位提案の順でfable_clientへ
    委譲し、WeeklyReviewを構築する。いずれかの評価呼び出しが失敗した場合は
    Result[WeeklyReview](success=False)を返し、後続評価は実行しない。"""


def build_weekly_review(
    weekly_analysis: WeeklyAnalysis,
    business_evaluation: "BusinessEvaluation",
    mvp_evaluation: "MvpEvaluation",
    technical_debt: "TechnicalDebtFinding",
    achievements: list[str],
    risks: list[str],
    recommendations: list[str],
    top_priority_next_week: list[str],
) -> WeeklyReview:
    """各評価結果からWeeklyReviewインスタンスを組み立てる(id/created_at/updated_atは
    foundation.utilsの既定生成を利用)。"""
```

### 4.6 `reporter.py`

```python
from foundation.result import Result

from weekly_reviewer.models import WeeklyReport, WeeklyReview


def render_weekly_report(weekly_review: WeeklyReview) -> Result[WeeklyReport]:
    """設計書3.4節の9項目(Review Period/Merged Pull Requests/Business Evaluation/
    MVP Evaluation/Technical Debt/Achievements/Risks/Recommendations/
    Top Priority Next Week)をWeeklyReviewから転記し、Project Owner向けの
    summary_textを整形して付与する。"""


def render_summary_text(weekly_review: WeeklyReview) -> str:
    """WeeklyReviewの内容を人間可読なテキスト(Markdown想定)に整形する。"""
```

---

## 5. エラー処理

`src/weekly_reviewer/errors.py` にて、Foundationのエラー階層(`FoundationError`)を継承したWeekly Reviewer固有例外を定義する。新しい基底例外は追加せず、既存の `ValidationError` / `ConfigurationError` / `ExternalServiceError` を継承する。

```python
from foundation.errors import ConfigurationError, ExternalServiceError, ValidationError


class WeeklyReviewerValidationError(ValidationError):
    """collect/analyze/evaluate/publishへの入力(Project/PullRequestリスト/
    WeeklyAnalysis/WeeklyReview)がNoneまたは不正な場合に送出。"""


class WeeklyReviewerConfigurationError(ConfigurationError):
    """ConfigurationClient.get("weekly_reviewer", key)によるreview_period_days/
    business_goal取得の失敗、または必須設定値欠落時に送出。"""


class PullRequestCollectionError(ExternalServiceError):
    """Merge済みPull Requestの収集元(GitHub Manager等)への問い合わせが
    失敗した場合に送出。"""


class FableEvaluationError(ExternalServiceError):
    """Fableレビューエンジン呼び出し(business/mvp/technical debt/priority評価)が
    失敗した場合に送出。"""
```

- 各公開インターフェース(`collect` / `analyze` / `evaluate` / `publish`)は、内部で例外を捕捉し `Result[T](success=False, value=None, error=<FoundationError>)` として返却する。例外を呼び出し元へ送出しない。
- Foundation原則「Safety: 失敗時は安全側(Deny/Fail)に倒す」に従い、Fable評価(`evaluate()`)のいずれかの項目呼び出しが失敗した場合、部分的な評価結果で`WeeklyReview`を構築せず、失敗として`Result`を返す(達成度の不確かなレビューを提案しない)。
- Weekly Reviewer は 4.1節・4.2節の制約により、コード修正・Design修正・Pull Request修正・マージ・リリースを一切実行しない。これらを誤って実行してしまう例外系(例: 誤って書き込みAPIを呼び出した場合)は本仕様の設計対象外であり、そもそも該当する関数・APIを実装しないことで担保する。

---

## 6. ロギング仕様

`foundation.logger.get_logger("weekly_reviewer")` により取得した Logger を `WeeklyReviewer.__init__` で保持し、全ログ出力に使用する。標準ライブラリ `logging` のみを使用する。

出力項目(設計書4.5節、固定6項目):

```text
timestamp | review_period | merged_pr_count | technical_debt_count | recommendation_count | result
```

- `timestamp`: ログ出力時刻(Foundationのログフォーマット`timestamp | module_name | level | message`のtimestampをそのまま利用)
- `review_period`: `ReviewPeriod.start_date`〜`ReviewPeriod.end_date`(ISO 8601形式の文字列、例`"2026-07-05/2026-07-11"`)
- `merged_pr_count`: `len(merged_pull_requests)`
- `technical_debt_count`: `TechnicalDebtFinding.count`
- `recommendation_count`: `len(WeeklyReview.recommendations)`
- `result`: 当該ログイベント自体の成否(`"success"` / `"failure"`)

実装方針(`logging_utils.py`):

```python
def build_log_message(
    review_period: "ReviewPeriod",
    merged_pr_count: int,
    technical_debt_count: int,
    recommendation_count: int,
    result: str,
) -> str:
    """上記5項目(timestampはlogging側で付与)をkey=value形式の1行に整形する。"""


def sanitize_for_log(text: str) -> str:
    """ログへ出力する文字列(PR本文抜粋・Fable応答文字列等)から、
    Secret/Token/Credentialに該当しうる文字列(例: 'token', 'password', 'secret',
    'api_key', 'credential'等をキー名に含む語句、長い英数字トークン様文字列)を
    正規表現でマスク('***REDACTED***')してから返す。"""
```

- `collect()` 完了時・`evaluate()` 完了時・`publish()` 完了時にそれぞれ1回、上記5項目(+result)をINFOレベルで出力する。エラー時はERRORレベルで`result="failure"`として出力し、例外メッセージそのもの(PRタイトル・本文・Fable応答の生文字列等)は`sanitize_for_log()`を通した要約のみをログに含める。
- Pull Requestの本文・差分・Secret・Access Token・Credentialは生の形でログへ出力しない(設計書4.5節)。詳細情報は`WeeklyReport`(成果物)側にのみ保持する。

---

## 7. Unit Testケース一覧(unittest)

### `test_weekly_reviewer.py`
- `test_name_returns_weekly_reviewer`
- `test_health_check_returns_success_result`
- `test_collect_returns_pull_request_list_for_review_period`
- `test_collect_returns_empty_list_when_no_merged_pull_requests_in_period`
- `test_collect_returns_failure_result_when_project_is_none`
- `test_collect_resolves_review_period_from_configuration`
- `test_collect_returns_failure_result_when_pull_request_collection_fails`
- `test_analyze_returns_weekly_analysis_with_pull_request_summaries`
- `test_analyze_returns_failure_result_when_merged_pull_requests_is_none`
- `test_analyze_handles_empty_pull_request_list`
- `test_evaluate_returns_weekly_review_with_all_evaluation_sections`
- `test_evaluate_uses_business_goal_from_configuration_when_not_supplied`
- `test_evaluate_returns_failure_result_when_business_goal_unavailable`
- `test_evaluate_evaluates_business_before_mvp_before_technical_debt`
- `test_evaluate_returns_failure_result_when_fable_evaluation_fails`
- `test_publish_returns_weekly_report_matching_nine_designated_fields`
- `test_publish_returns_failure_result_when_weekly_review_is_none`
- `test_pipeline_end_to_end_from_collect_to_publish`

### `test_models.py`
- `test_project_is_frozen_value_object`
- `test_review_period_is_frozen_value_object`
- `test_mvp_evaluation_has_issue_true_when_any_list_non_empty`
- `test_mvp_evaluation_has_issue_false_when_all_lists_empty`
- `test_technical_debt_finding_count_sums_all_categories`
- `test_weekly_review_inherits_review_common_fields`
- `test_weekly_review_default_fields_are_generated`
- `test_weekly_report_fields_match_designated_nine_items`

### `test_collector.py`
- `test_collect_merged_pull_requests_filters_by_review_period`
- `test_collect_merged_pull_requests_excludes_unmerged_pull_requests`
- `test_collect_merged_pull_requests_returns_failure_result_on_source_unavailable`
- `test_resolve_review_period_returns_seven_day_window_by_default`
- `test_resolve_review_period_uses_configured_review_period_days`

### `test_analyzer.py`
- `test_build_weekly_analysis_summarizes_each_pull_request`
- `test_build_weekly_analysis_preserves_review_period`
- `test_build_weekly_analysis_handles_empty_pull_request_list`
- `test_summarize_pull_request_returns_non_empty_summary`

### `test_fable_client.py`
- `test_fable_client_cannot_be_instantiated_directly`
- `test_review_business_alignment_returns_business_evaluation_result`
- `test_review_mvp_fitness_returns_mvp_evaluation_result`
- `test_review_technical_debt_returns_technical_debt_finding_result`
- `test_recommend_priorities_returns_four_element_tuple_result`

### `test_evaluator.py`
- `test_evaluate_weekly_analysis_returns_weekly_review_when_all_stages_succeed`
- `test_evaluate_weekly_analysis_stops_on_business_alignment_failure`
- `test_evaluate_weekly_analysis_stops_on_mvp_evaluation_failure`
- `test_evaluate_weekly_analysis_stops_on_technical_debt_evaluation_failure`
- `test_evaluate_weekly_analysis_stops_on_priority_recommendation_failure`
- `test_build_weekly_review_sets_all_designated_sections`

### `test_reporter.py`
- `test_render_weekly_report_includes_all_nine_designated_sections`
- `test_render_weekly_report_preserves_top_priority_next_week_order`
- `test_render_weekly_report_returns_failure_result_when_weekly_review_missing_business_evaluation`
- `test_render_summary_text_excludes_secrets_and_credentials`
- `test_render_summary_text_is_non_empty_string`

---

## 8. MVP範囲の明記

設計書5.3節(重厚壮大化監査)にて対象外・削除済みとされた以下の機能は、本実装仕様書においても一切実装しない。

- KPI予測AI
- 売上予測
- Sprint Planning
- 人員配置最適化
- ベロシティ予測
- OKR自動生成
- 経営レポート自動作成

また、以下は設計書1章(対象外)・2.2節・4章の制約により明示的に実装対象外とする。

- 要件分析・システム設計・コード生成(責務外、Planner/Architect/Executorが担当)
- Pull Requestレビュー・GitHubマージ・リリース(責務外、Reviewer(M12)/GitHub Managerが担当)
- コード修正・Design修正・Pull Request修正(4.1節で禁止)
- 優先順位・改善案・技術的負債の実施判断(4.4節: 提案のみ行い、実施判断はProject Ownerが行う)

Weekly Reviewer が実装するのは、設計書3.2節の収集対象のうちMerge済みPull Requestの収集、3.3節の4評価項目(Business Goal/MVP/Technical Debt/Development Direction)、3.4節のWeekly Report(9項目)、および3.5節の公開インターフェース(`collect` / `analyze` / `evaluate` / `publish`)のみである。
