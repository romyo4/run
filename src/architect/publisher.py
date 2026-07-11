"""Architect(M07) publish_design() の内部処理(IS07 4.5節)。

ValidatedDesign.validation_result.status が VALID の場合のみ、design_document.status を
PUBLISHED に更新して返す。INVALID の場合は publish せず Result(success=False)を返す(F00 Safety)。
"""

from __future__ import annotations

from architect.errors import DesignValidationError
from architect.models import DesignDocument, DesignStatus, ValidatedDesign, ValidationStatus
from foundation.result import Result
from foundation.utils import utc_now

__all__ = ["publish_design"]


def publish_design(validated_design: ValidatedDesign) -> Result[DesignDocument]:
    """ValidatedDesignを検証結果に基づき確定する。

    validation_result.status != VALID の場合は publish せず
    Result[DesignDocument](success=False, error=DesignValidationError)を返す(F00 Safety)。
    """
    if validated_design.validation_result.status != ValidationStatus.VALID:
        return Result(
            success=False,
            value=None,
            error=DesignValidationError("validation_result.status is not VALID; publish is rejected"),
        )

    design_document = validated_design.design_document
    design_document.status = DesignStatus.PUBLISHED
    design_document.updated_at = utc_now()
    return Result(success=True, value=design_document)
