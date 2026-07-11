"""処理フロー『Validate』段階(IS19 4.4節)。

`AI Context` の不足情報を確認し `ValidationResult` を返す。
"""

from typing import Any

from context_manager.selector import WORKFLOW_FIELD_MAP
from context_manager.types import AIContext, ValidationResult


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, str)) and len(value) == 0:
        return True
    return False


def validate(context: AIContext) -> ValidationResult:
    """WORKFLOW_FIELD_MAP[context.workflow_type] に列挙された必須項目が
    SelectedContext上でNone/空でないかを確認し、不足があれば missing_fields に記録する。
    Context本文はここでのみ参照し、戻り値(ValidationResult)には含めない。
    """
    required_fields = WORKFLOW_FIELD_MAP[context.workflow_type]
    selected = context.selected_context

    missing_fields: list[str] = []
    for field_name in sorted(required_fields):
        value = getattr(selected, field_name, None) if selected is not None else None
        if _is_missing(value):
            missing_fields.append(field_name)

    return ValidationResult(is_valid=len(missing_fields) == 0, missing_fields=missing_fields)
