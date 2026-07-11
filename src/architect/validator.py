"""Architect(M07) validate_design() の内部処理(IS07 4.4節)。

Design Documentの構造的完全性・内部整合性(必須項目充足・Interfaceの参照先Moduleが
Module Designに存在するか等)のみを検証する。要求充足度・MVP適合性・過剰設計判定は
Design Auditor(M08)の責務であり本関数の対象外(設計書4.3)。
"""

from __future__ import annotations

from architect.models import DesignDocument, ValidationIssue, ValidationResult, ValidationStatus
from foundation.result import Result
from foundation.utils import generate_id

__all__ = ["validate_design"]


def validate_design(design_document: DesignDocument) -> Result[ValidationResult]:
    """Design Documentの必須項目充足・内部整合性のみを検証する。

    要求充足度・MVP適合性・過剰設計判定はDesign Auditorの責務であり本関数の対象外(4.3)。
    """
    issues: list[ValidationIssue] = []

    if not design_document.objective:
        issues.append(ValidationIssue(field_name="objective", message="objective must not be empty"))

    if not design_document.module_design:
        issues.append(ValidationIssue(field_name="module_design", message="module_design must not be empty"))

    module_names = {module.module_name for module in design_document.module_design}
    for interface in design_document.interface_design:
        if interface.owning_module not in module_names:
            issues.append(
                ValidationIssue(
                    field_name="interface_design",
                    message=(
                        f"interface '{interface.interface_name}' references unknown module " f"'{interface.owning_module}'"
                    ),
                )
            )

    status = ValidationStatus.INVALID if issues else ValidationStatus.VALID

    result = ValidationResult(
        validation_id=generate_id(),
        design_id=design_document.id,
        status=status,
        issues=issues,
    )
    return Result(success=True, value=result)
