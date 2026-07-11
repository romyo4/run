"""所定5項目のログ整形、Secret/Token/Credentialのマスク処理(IS13 6節)。"""

from __future__ import annotations

import re

from weekly_reviewer.models import ReviewPeriod

__all__ = ["build_log_message", "sanitize_for_log"]

_SECRET_KEY_VALUE_PATTERN = re.compile(r"(?i)\b(token|password|secret|api[_-]?key|credential)\b\s*[:=]\s*\S+")
_LONG_TOKEN_PATTERN = re.compile(r"\b[A-Za-z0-9_\-]{20,}\b")
_REDACTED = "***REDACTED***"


def build_log_message(
    review_period: ReviewPeriod,
    merged_pr_count: int,
    technical_debt_count: int,
    recommendation_count: int,
    result: str,
) -> str:
    """設計書4.5節・IS13 6節の5項目(timestampはlogging側で付与)をkey=value形式の
    1行に整形する。"""
    period_str = f"{review_period.start_date.isoformat()}/{review_period.end_date.isoformat()}"
    return (
        f"review_period={period_str} "
        f"merged_pr_count={merged_pr_count} "
        f"technical_debt_count={technical_debt_count} "
        f"recommendation_count={recommendation_count} "
        f"result={result}"
    )


def sanitize_for_log(text: str) -> str:
    """ログ・レポート本文へ出力する文字列(PR本文抜粋・Fable応答文字列等)から、
    Secret/Token/Credentialに該当しうる文字列(キー名に'token'/'password'/'secret'/
    'api_key'/'credential'等を含むkey=value表現、長い英数字トークン様文字列)を
    正規表現でマスク('***REDACTED***')してから返す。"""
    if not text:
        return text
    sanitized = _SECRET_KEY_VALUE_PATTERN.sub(lambda m: f"{m.group(1)}={_REDACTED}", text)
    sanitized = _LONG_TOKEN_PATTERN.sub(_REDACTED, sanitized)
    return sanitized
