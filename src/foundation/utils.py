"""Domain Model共通属性(id/created_at/updated_at)を生成する最小限のヘルパー。"""

import uuid
from datetime import UTC, datetime


def generate_id() -> str:
    """UUID4文字列を生成する。"""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """UTC現在時刻を返す。"""
    return datetime.now(UTC)
