"""Result[T](F02 共通Interface)。モジュール間API戻り値の共通ラッパー。"""

from dataclasses import dataclass
from typing import Generic, TypeVar

from foundation.errors import FoundationError

T = TypeVar("T")


@dataclass
class Result(Generic[T]):
    success: bool
    value: T | None = None
    error: FoundationError | None = None
