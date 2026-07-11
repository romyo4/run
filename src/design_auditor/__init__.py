"""Design Auditor (M08) パッケージ公開エクスポート。

Architect(M07)が作成したDesign Documentを監査し、実装(Executor)へ進めてよいかを
判定するモジュール。公開シンボルはDesignAuditor本体と、公開インターフェースの
入出力に用いるdataclass/Enumに限定する(design_auditor.types 参照)。
"""

from __future__ import annotations

from design_auditor.module import DesignAuditor
from design_auditor.types import (
    ApprovedDesign,
    AuditCategory,
    AuditIssue,
    AuditReport,
    AuditResultStatus,
    MVPAssessment,
    PublishOutcome,
    ReworkRequest,
    ValidationResult,
)

__all__ = [
    "DesignAuditor",
    "AuditCategory",
    "AuditResultStatus",
    "AuditIssue",
    "AuditReport",
    "ValidationResult",
    "MVPAssessment",
    "ApprovedDesign",
    "ReworkRequest",
    "PublishOutcome",
]
