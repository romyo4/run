"""Architect(M07) 固有例外(IS07 5節)。

Foundation の例外階層(`foundation.errors`)を継承する。新しい基底例外は追加しない
(Foundation 3.6の制約)。
"""

from __future__ import annotations

from foundation.errors import NotFoundError, ValidationError

__all__ = [
    "PlanAnalysisError",
    "DesignCreationError",
    "DesignValidationError",
    "DesignNotFoundError",
]


class PlanAnalysisError(ValidationError):
    """Execution Planの分析に失敗した場合(必須フィールド欠落・Task List空等)。"""


class DesignCreationError(ValidationError):
    """Design Requirementから Design Document を生成できない場合。"""


class DesignValidationError(ValidationError):
    """Design Documentの自己検証(validate_design)で必須項目欠落・内部不整合が検出された場合。"""


class DesignNotFoundError(NotFoundError):
    """指定された design_id に対応する Design Document が存在しない場合。"""
