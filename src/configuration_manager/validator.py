"""必須設定の検証ロジック(IS17仕様書4.4節/設計書4.4)。"""

from __future__ import annotations

from configuration_manager.constants import (
    REQUIRED_CONFIGURATION_KEY_LABELS,
    REQUIRED_CONFIGURATION_KEYS,
)
from configuration_manager.domain import Configuration, ValidationResult
from foundation.errors import ValidationError
from foundation.result import Result


def validate_configuration(configuration: Configuration) -> Result[ValidationResult]:
    """設計書4.4の必須設定(GitHub Repository/Slack Channel/Codex Model等)を検証する。

    必須設定が空文字・未設定の場合でも例外は送出せず、`ValidationResult.is_valid=False`
    という正常な検証結果として返す(検証処理自体は正常に完了しているため)。
    検証処理自体が実行できない場合(想定外の型混入等)のみ `Result.error` に
    `ValidationError` を格納する。
    """
    try:
        errors: list[str] = []
        for category, field_name in REQUIRED_CONFIGURATION_KEYS:
            category_config = getattr(configuration, category)
            value = getattr(category_config, field_name)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                label = REQUIRED_CONFIGURATION_KEY_LABELS.get((category, field_name), f"{category}.{field_name}")
                errors.append(f"{label} is not set")
        result = ValidationResult(is_valid=not errors, errors=tuple(errors))
    except AttributeError as exc:
        return Result(
            success=False,
            error=ValidationError(f"failed to validate configuration: {exc}"),
        )
    return Result(success=True, value=result)
