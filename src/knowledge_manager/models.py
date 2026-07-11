"""Knowledge Manager(M03)のドメイン型定義(IS03 3節)。

KnowledgeCategory / KnowledgeStatus の2つのEnumと KnowledgeDocument dataclass を定義する。
Foundation(F01)の `Knowledge` Domain(id/created_at/updated_at/metadata)を土台に、
M03固有の属性(設計書3.2 / 4.3)を追加する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from foundation.utils import generate_id, utc_now


class KnowledgeCategory(str, Enum):
    """設計書3.1の管理対象文書カテゴリ。新規カテゴリの追加はしない。"""

    BUSINESS_GOAL = "business_goal"
    MVP_POLICY = "mvp_policy"
    ARCHITECTURE_PRINCIPLES = "architecture_principles"
    DEVELOPMENT_RULES = "development_rules"
    CODING_RULES = "coding_rules"


class KnowledgeStatus(str, Enum):
    """設計書3.4 バージョン管理(最新版を既定利用/過去版参照可能)を表現する最小限のステータス。"""

    CURRENT = "current"
    ARCHIVED = "archived"


@dataclass
class KnowledgeDocument:
    """Knowledge文書1版分を表す(設計書3.2 / 4.3構造化必須要件)。

    Foundation Knowledge Domain(F01)共通属性(id/created_at/updated_at/metadata)に、
    M03固有属性(document_id/category/title/content/version/status/tags/updated_by/
    content_hash)を追加する。
    """

    # --- Foundation Knowledge Domain 共通属性 (F01) ---
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    # --- M03 固有属性 (設計書 3.2 / 4.3) ---
    document_id: str = ""
    category: KnowledgeCategory = KnowledgeCategory.DEVELOPMENT_RULES
    title: str = ""
    content: str = ""
    version: int = 1
    status: KnowledgeStatus = KnowledgeStatus.CURRENT
    tags: list[str] = field(default_factory=list)
    updated_by: str = ""
    content_hash: str = ""
