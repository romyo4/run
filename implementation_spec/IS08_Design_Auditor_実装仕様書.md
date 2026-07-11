# IS08 Design Auditor 実装仕様書

版: v1.0 (Design Freeze v1.0 準拠)
参照元設計書: `M08 Design Auditor.txt`
前提モジュール: `M00 Foundation.txt`(F00 原則カタログ / F01 共通 Domain Model / F02 共通 Interface / F03 Configuration Access Pattern)

本書は M08 Design Auditor の詳細設計書を実装可能な粒度へ具体化したものである。設計書に明記されていない機能・API・モジュールは追加しない。設計書の記述と実装上どうしても解釈が必要な箇所は、本文中に「実装解釈メモ」として明示し、断定を避ける。

---

## 1. モジュール概要

Design Auditor は、Architect(M07)が作成した Design Document を対象に、要求との整合性・Foundation(F00〜F03)とのアーキテクチャ整合性・MVP適合性・設計品質を監査し、実装(Executor)へ進めてよいかを判定する単一責務モジュールである。監査対象は Architecture Design・Module Design・API Design・Data Structure Design・Refactoring Design であり、監査観点は要件充足・責務分離・モジュール境界・Interface整合性・Domain整合性・Configuration整合性・MVP適合性・再利用可能性・過剰設計の有無の9項目に限定される。監査結果は PASS / PASS_WITH_COMMENT / REWORK_REQUIRED / REJECT の4区分で表現され、Audit Report として Audit ID・Result・Findings・Warnings・Violations・Recommendations を出力する。Design Auditor は設計の修正・コード生成・Pull Request作成・GitHub操作を一切行わず、問題がある場合は Architect へ差し戻すことのみを行う。「Design Before Code」原則を実装レイヤーで担保することが本モジュールの存在意義である。

---

## 2. ファイル構成

```text
src/design_auditor/
├── __init__.py              # パッケージ公開シンボル(DesignAuditor, 主要dataclass)のエクスポート
├── module.py                 # DesignAuditor(BaseModule) 本体。公開インターフェース4メソッドを実装
├── types.py                  # 本モジュール固有のdataclass/Enum定義(Foundation types.py の Design を利用する側)
├── constants.py               # 監査基準に関わる固定値(重厚壮大化監査5.3のMVP対象外機能リスト等)
├── requirement_check.py        # 要件充足確認(3.2「要件充足」/ 3.6「Requirement Check」)
├── architecture_check.py       # Architecture整合性確認(責務分離・モジュール境界・Interface整合性・Domain整合性・Configuration整合性)
├── mvp_check.py                # MVP適合性確認(3.6「MVP Check」/ 5.3 重厚壮大化監査の判定ロジック)
├── quality_check.py             # 品質確認(再利用可能性・過剰設計の有無 / 3.6「Quality Check」)
├── aggregation.py               # 4段階チェックの結果からAuditResultStatusとAudit Reportを合成する
├── exceptions.py                # 本モジュール固有の例外(Foundationのエラー階層をそのまま利用する方針の明記のみ。新規基底例外は追加しない)
└── tests/
    ├── __init__.py
    ├── test_types.py
    ├── test_requirement_check.py
    ├── test_architecture_check.py
    ├── test_mvp_check.py
    ├── test_quality_check.py
    ├── test_aggregation.py
    ├── test_module_audit.py
    ├── test_module_validate_architecture.py
    ├── test_module_check_mvp.py
    ├── test_module_publish_result.py
    └── test_base_module_contract.py
```

**実装解釈メモ**: 設計書 3.6 の処理フロー(Requirement Check → Architecture Check → MVP Check → Quality Check → Audit Report)を、`audit()` 内部でこの順に呼び出すオーケストレーションとして実装する方針とする。`validate_architecture()` / `check_mvp()` は同じチェックロジック(`architecture_check.py` / `mvp_check.py`)を単体公開メソッドとしても呼び出せるようにし、ロジックの重複実装を避ける(F00: Simplicity / Single Responsibility)。

---

## 3. データクラス定義

Foundation `types.py` の `Design`(F01 共通 Domain, 属性: `id, created_at, updated_at, metadata` + Architect側で定義する固有属性)をそのまま入力として利用し、`Design` 自体の定義・属性追加は行わない。

Audit Report 以下の成果物は Foundation の F01 Domain 一覧(Task/SubTask/Workflow/Design/Implementation/TestResult/PullRequest/Review/Knowledge/Context/Configuration/Notification/CommunicationMessage)に含まれないため、Design Auditor 固有のdataclassとして `design_auditor/types.py` に定義する。ただし F01 の共通属性規約(`id, created_at, updated_at, metadata`)にはならい、モジュール間の一貫性を保つ。

```python
# design_auditor/types.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AuditCategory(str, Enum):
    """3.2 監査項目(9項目)"""
    REQUIREMENT_FULFILLMENT = "requirement_fulfillment"      # 要件充足
    RESPONSIBILITY_SEPARATION = "responsibility_separation"  # 責務分離
    MODULE_BOUNDARY = "module_boundary"                      # モジュール境界
    INTERFACE_CONSISTENCY = "interface_consistency"          # Interface整合性
    DOMAIN_CONSISTENCY = "domain_consistency"                # Domain整合性
    CONFIGURATION_CONSISTENCY = "configuration_consistency"  # Configuration整合性
    MVP_FITNESS = "mvp_fitness"                               # MVP適合性
    REUSABILITY = "reusability"                               # 再利用可能性
    OVER_ENGINEERING = "over_engineering"                     # 過剰設計の有無


class AuditResultStatus(str, Enum):
    """3.3 監査結果(4区分)"""
    PASS = "PASS"
    PASS_WITH_COMMENT = "PASS_WITH_COMMENT"
    REWORK_REQUIRED = "REWORK_REQUIRED"
    REJECT = "REJECT"


@dataclass(frozen=True)
class AuditIssue:
    """Findings / Warnings / Violations の1件を表す"""
    category: AuditCategory
    message: str
    location: str | None = None  # 該当箇所(モジュール名・設計書の節等。任意)


@dataclass
class AuditReport:
    """3.4 Audit Report"""
    id: str                       # Audit ID(共通属性: id)
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    workflow_id: str
    design_id: str
    result: AuditResultStatus
    findings: list[AuditIssue] = field(default_factory=list)
    warnings: list[AuditIssue] = field(default_factory=list)
    violations: list[AuditIssue] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """validate_architecture() の出力"""
    valid: bool
    violations: list[AuditIssue] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class MVPAssessment:
    """check_mvp() の出力"""
    compliant: bool
    excluded_features_detected: list[str] = field(default_factory=list)  # 5.3 MVP対象外機能の検出結果
    notes: list[str] = field(default_factory=list)


@dataclass
class ApprovedDesign:
    """publish_result() が PASS / PASS_WITH_COMMENT の場合に返す成果物"""
    design_id: str
    audit_id: str
    approved_at: datetime
    comments: list[str] = field(default_factory=list)  # PASS_WITH_COMMENT時のコメント。PASSでは空


@dataclass
class ReworkRequest:
    """publish_result() が REWORK_REQUIRED / REJECT の場合に返す成果物"""
    design_id: str
    audit_id: str
    reasons: list[str] = field(default_factory=list)
    required_changes: list[str] = field(default_factory=list)
    returned_to: str = "architect"


PublishOutcome = ApprovedDesign | ReworkRequest
```

`constants.py` には 5.3 重厚壮大化監査で MVP対象外・削除済みとされた機能名を定数として保持する(`check_mvp()` が Design Document 本文中にこれらのキーワードが含まれるかを検出する材料として用いる。それ以外の用途では使用しない)。

```python
# design_auditor/constants.py
MVP_EXCLUDED_FEATURES: tuple[str, ...] = (
    "AI設計生成",
    "自動修正",
    "UML生成",
    "コスト最適化",
    "パフォーマンス解析",
    "セキュリティ自動修正",
    "Enterprise Design Governance",
)
```

---

## 4. クラス・関数シグネチャ

Foundation `base_module.BaseModule` を継承し、3.5 の4公開インターフェースをメソッドとして実装する。

```python
# design_auditor/module.py
from __future__ import annotations

from foundation.base_module import BaseModule
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from foundation.types import Design

from design_auditor.types import (
    AuditReport,
    MVPAssessment,
    PublishOutcome,
    ValidationResult,
)


class DesignAuditor(BaseModule):
    """Design Document を監査し、実装へ進めてよいかを判定するモジュール。"""

    def __init__(self, config_client: ConfigurationClient) -> None:
        """config_client は F03 Configuration Access Pattern に基づき注入する。"""
        ...

    def name(self) -> str:
        """F02 BaseModule契約。"""
        ...

    def health_check(self) -> Result[bool]:
        """F02 BaseModule契約。config_client疎通確認等の軽量チェックのみ行う。"""
        ...

    def audit(self, design_document: Design) -> Result[AuditReport]:
        """3.5 audit(). 3.6の4段階チェック(Requirement/Architecture/MVP/Quality)を
        この順に内部実行し、結果を集約してAudit Reportを生成する。"""
        ...

    def validate_architecture(self, design_document: Design) -> Result[ValidationResult]:
        """3.5 validate_architecture(). 責務分離・モジュール境界・Interface整合性・
        Domain整合性・Configuration整合性を確認する(architecture_check.pyに委譲)。"""
        ...

    def check_mvp(self, design_document: Design) -> Result[MVPAssessment]:
        """3.5 check_mvp(). MVP適合性(5.3 重厚壮大化監査基準)を確認する
        (mvp_check.pyに委譲)。"""
        ...

    def publish_result(
        self, audit_report: AuditReport
    ) -> Result[PublishOutcome]:
        """3.5 publish_result(). result が PASS/PASS_WITH_COMMENT の場合は
        ApprovedDesign、REWORK_REQUIRED/REJECTの場合はReworkRequestをvalueに格納する。"""
        ...
```

**実装解釈メモ(workflow_id / design_id の取得元)**: 3.5 では各メソッドの入力は主要成果物(Design Document / Audit Report)のみが記載されている。一方 4.5 ログ仕様は `workflow_id` `design_id` を要求する。設計書に新規パラメータの追加は行わないため、`design_id = design_document.id`、`workflow_id = design_document.metadata["workflow_id"]`(Architect側がDesign生成時にmetadataへ格納する前提)として取得する。この前提が成立しない場合は `NotFoundError` を返す。

内部ヘルパー(非公開・3.6処理フローの各段階に対応。公開APIではない):

```python
# design_auditor/requirement_check.py
def check_requirements(design_document: Design) -> list[AuditIssue]: ...

# design_auditor/architecture_check.py
def check_architecture(design_document: Design) -> ValidationResult: ...

# design_auditor/mvp_check.py
def check_mvp_fitness(design_document: Design) -> MVPAssessment: ...

# design_auditor/quality_check.py
def check_quality(design_document: Design) -> list[AuditIssue]: ...

# design_auditor/aggregation.py
def aggregate_result(
    findings: list[AuditIssue],
    warnings: list[AuditIssue],
    violations: list[AuditIssue],
) -> AuditResultStatus: ...
```

**実装解釈メモ(判定ロジック)**: 設計書は各チェックからAudit Report全体の`result`(4区分)を導く集約規則を明記していない。実装上は以下の優先順位を採用する: violations が1件以上 → `REJECT` または `REWORK_REQUIRED`(重大度は`category`が`MVP_FITNESS`かつ5.3対象外機能検出時は`REJECT`、それ以外は`REWORK_REQUIRED`)。violationsが0件でwarningsが1件以上 → `PASS_WITH_COMMENT`。いずれも0件 → `PASS`。この規則は設計書に存在しないため、実装時にArchitect/Design Auditor責任者のレビューを受けること。

---

## 5. エラー処理

Foundation `errors.py` のエラー階層(`FoundationError`基底)をそのまま利用し、Design Auditor 独自の新規基底例外は追加しない(4.4「監査基準固定」= 独自ルール追加禁止の趣旨に合わせ、独自例外体系も追加しない)。

| Foundationエラー | 本モジュールでの用途 |
|---|---|
| `ValidationError` | 入力の `design_document` が `None`・必須属性欠落等、`foundation.validation` の `require_not_none` / `require_non_empty` / `require_in` が失敗した場合 |
| `NotFoundError` | `design_document.metadata["workflow_id"]` が存在しない等、監査に必要な参照情報が見つからない場合 |
| `ConfigurationError` | `ConfigurationClient.get()` が失敗した場合(監査基準の閾値等をConfiguration Managerから取得できないケース) |
| `StateTransitionError` | 本モジュールでは使用しない(State管理はState Managerの責務) |
| `PermissionDeniedError` | 本モジュールでは使用しない(権限確認はPermission Managerの責務) |
| `ExternalServiceError` | 本モジュールでは使用しない(外部サービス呼び出しを行わない) |

各公開メソッドは内部で例外を捕捉し、`Result[T](success=False, value=None, error=<FoundationError>)` を返す。例外を呼び出し元へ送出しない(F02 Result[T]パターン、F00 Safety「失敗時は安全側に倒す」)。

---

## 6. ロギング仕様

`foundation.logger.get_logger("design_auditor")` により本モジュール専用のLoggerを取得する。出力形式は Foundation規約 `timestamp | module_name | level | message` に従う。

4.5 で定義されたログ項目 `timestamp, workflow_id, design_id, audit_result, finding_count, warning_count, result` を、`audit()` および `publish_result()` の処理完了時(成功・失敗いずれも)に `logger.info(...)` / `logger.error(...)` で出力する。

```python
logger.info(
    "workflow_id=%s design_id=%s audit_result=%s finding_count=%d warning_count=%d result=%s",
    workflow_id, design_id, audit_result.value, len(findings), len(warnings), result,
)
```

- `audit_result`: `AuditResultStatus`(PASS/PASS_WITH_COMMENT/REWORK_REQUIRED/REJECT)
- `result`: 監査処理自体の実行結果("success" / "error")。`audit_result`(監査の判定内容)とは意味が異なるため区別して出力する
- `validate_architecture()` / `check_mvp()` を単体呼び出しした場合、finding_count/warning_count は該当チェックで検出した件数のみを記録する
- Secret・Token・Credential・Design Document本文の機密情報はログへ出力しない(4.5)

---

## 7. Unit Test ケース一覧(unittest)

設計書に明示の「テスト観点」節はないため、3.2 監査項目・3.3 監査結果・3.5 公開インターフェース・3.6 処理フロー・4章 制約 から導出する。

### test_types.py
- `test_audit_issue_is_immutable`
- `test_audit_report_default_lists_are_independent_instances`
- `test_publish_outcome_accepts_approved_design`
- `test_publish_outcome_accepts_rework_request`

### test_requirement_check.py
- `test_check_requirements_returns_empty_when_design_covers_all_requirements`
- `test_check_requirements_returns_finding_when_requirement_missing`

### test_architecture_check.py
- `test_check_architecture_passes_when_responsibility_separated`
- `test_check_architecture_detects_responsibility_separation_violation`
- `test_check_architecture_detects_module_boundary_violation`
- `test_check_architecture_detects_interface_inconsistency`
- `test_check_architecture_detects_domain_inconsistency`
- `test_check_architecture_detects_configuration_inconsistency`

### test_mvp_check.py
- `test_check_mvp_fitness_compliant_when_no_excluded_feature_present`
- `test_check_mvp_fitness_detects_ai_design_generation_feature`
- `test_check_mvp_fitness_detects_auto_fix_feature`
- `test_check_mvp_fitness_detects_uml_generation_feature`
- `test_check_mvp_fitness_detects_cost_optimization_feature`
- `test_check_mvp_fitness_detects_performance_analysis_feature`
- `test_check_mvp_fitness_detects_security_auto_fix_feature`
- `test_check_mvp_fitness_detects_enterprise_design_governance_feature`

### test_quality_check.py
- `test_check_quality_passes_when_reusable_and_not_over_engineered`
- `test_check_quality_detects_low_reusability`
- `test_check_quality_detects_over_engineering`

### test_aggregation.py
- `test_aggregate_result_returns_pass_when_no_findings`
- `test_aggregate_result_returns_pass_with_comment_when_only_warnings`
- `test_aggregate_result_returns_rework_required_when_violation_present`
- `test_aggregate_result_returns_reject_when_mvp_excluded_feature_violation_present`

### test_module_audit.py
- `test_audit_returns_pass_for_clean_design_document`
- `test_audit_returns_rework_required_when_architecture_violation_found`
- `test_audit_returns_reject_when_mvp_excluded_feature_found`
- `test_audit_report_contains_workflow_id_and_design_id`
- `test_audit_returns_validation_error_when_design_document_is_none`
- `test_audit_returns_not_found_error_when_workflow_id_missing_in_metadata`
- `test_audit_does_not_mutate_design_document`
- `test_audit_logs_expected_fields_on_success`

### test_module_validate_architecture.py
- `test_validate_architecture_returns_valid_true_when_no_violations`
- `test_validate_architecture_returns_valid_false_when_violations_present`
- `test_validate_architecture_only_covers_architecture_categories`

### test_module_check_mvp.py
- `test_check_mvp_returns_compliant_true_when_no_excluded_feature`
- `test_check_mvp_returns_compliant_false_and_lists_detected_features`

### test_module_publish_result.py
- `test_publish_result_returns_approved_design_when_result_is_pass`
- `test_publish_result_returns_approved_design_with_comments_when_pass_with_comment`
- `test_publish_result_returns_rework_request_when_rework_required`
- `test_publish_result_returns_rework_request_when_reject`
- `test_publish_result_rework_request_returned_to_is_architect`

### test_base_module_contract.py
- `test_name_returns_design_auditor`
- `test_health_check_returns_success_result_when_config_client_reachable`
- `test_health_check_returns_failure_result_when_config_client_unreachable`

### 制約に関するテスト(横断)
- `test_audit_does_not_generate_or_modify_design_content`(4.1/4.2: 設計・修正を行わないことの確認。戻り値がAuditReportのみで、design_documentの属性を変更しないことを検証)
- `test_module_has_no_code_generation_or_github_api`(4.3: コード生成・GitHub操作用のpublicメソッドが存在しないことをクラスのメンバー列挙で確認)

---

## 8. MVP範囲の明記

以下は設計書 5.3「重厚壮大化監査」にて **MVP対象外・削除済み** と判定された機能であり、本実装仕様および実装では一切含めない。

- AI設計生成
- 自動修正
- UML生成
- コスト最適化
- パフォーマンス解析
- セキュリティ自動修正
- Enterprise Design Governance

上記のうち「自動修正」「AI設計生成」は特に注意を要する。Design Auditor は監査結果として `REWORK_REQUIRED` / `REJECT` を返しArchitectへ差し戻すのみであり、設計書の自動生成・自動修正・提案コードの自動適用は行わない(4.2「Auditorは修正しない」)。

また、設計書 2.2「担当しない」に列挙された以下も実装対象外である。

- 要件分析
- 設計書修正
- コード生成
- Pull Request作成
- コードレビュー
- Workflow実行

本モジュールが提供する公開APIは `audit()` / `validate_architecture()` / `check_mvp()` / `publish_result()` の4メソッドのみに限定し、設計書 3.5 に定義のないメソッドを追加しない。
