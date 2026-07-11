"""Design Auditor (M08) 固有のdataclass/Enum定義(IS08 3章)。

Foundation `types.py` の `Design`(F01 共通Domain Model)をそのまま入力として利用し、
`Design` 自体の定義・属性追加はここでは行わない。Audit Report以下の成果物は F01 の
Domain一覧に含まれないため、本モジュール固有のdataclassとしてここに定義する。
ただし F01 の共通属性規約(`id, created_at, updated_at, metadata`)にはならい、
モジュール間の一貫性を保つ。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AuditCategory(str, Enum):
    """3.2 監査項目(9項目)"""

    REQUIREMENT_FULFILLMENT = "requirement_fulfillment"  # 要件充足
    RESPONSIBILITY_SEPARATION = "responsibility_separation"  # 責務分離
    MODULE_BOUNDARY = "module_boundary"  # モジュール境界
    INTERFACE_CONSISTENCY = "interface_consistency"  # Interface整合性
    DOMAIN_CONSISTENCY = "domain_consistency"  # Domain整合性
    CONFIGURATION_CONSISTENCY = "configuration_consistency"  # Configuration整合性
    MVP_FITNESS = "mvp_fitness"  # MVP適合性
    REUSABILITY = "reusability"  # 再利用可能性
    OVER_ENGINEERING = "over_engineering"  # 過剰設計の有無


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

    id: str  # Audit ID(共通属性: id)
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
