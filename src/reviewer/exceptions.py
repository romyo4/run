"""Reviewer固有例外(Foundationエラー階層を継承、IS12 4.4)。"""

from __future__ import annotations

from foundation.errors import ValidationError

__all__ = ["InvalidReviewInputError"]


class InvalidReviewInputError(ValidationError):
    """review()/evaluate_business()/evaluate_mvp()の必須入力が欠落・不正な場合。"""
