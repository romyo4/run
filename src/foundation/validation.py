"""共通バリデーションユーティリティ(設計書3.8, 3.10節)。"""

from collections.abc import Callable, Iterable, Sized
from typing import Any

from foundation.errors import ValidationError
from foundation.result import Result


def require_not_none(value: Any, field_name: str) -> None:
    """valueがNoneの場合ValidationErrorを送出する。"""
    if value is None:
        raise ValidationError(f"{field_name} must not be None")


def require_non_empty(value: Any, field_name: str) -> None:
    """valueが空(空文字列・空コレクション等)の場合ValidationErrorを送出する。"""
    if value is None or (isinstance(value, Sized) and len(value) == 0):
        raise ValidationError(f"{field_name} must not be empty")


def require_in(value: Any, allowed_values: Iterable[Any], field_name: str) -> None:
    """valueがallowed_valuesに含まれない場合ValidationErrorを送出する。"""
    if value not in allowed_values:
        raise ValidationError(f"{field_name} must be one of {list(allowed_values)}")


def validate(value: Any, rule: Callable[[Any], bool]) -> Result[bool]:
    """rule(value)を評価し、結果をResult[bool]として返す。

    rule実行時の例外はValidationErrorにラップしてResult[bool](success=False, error=...)を返す。
    """
    try:
        passed = rule(value)
    except Exception as exc:  # noqa: BLE001 - ルール実行時の任意の例外をラップする
        return Result(success=False, error=ValidationError(str(exc)))
    if passed:
        return Result(success=True, value=True)
    return Result(success=False, error=ValidationError("validation rule failed"))
