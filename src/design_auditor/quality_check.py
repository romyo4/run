"""品質確認(再利用可能性・過剰設計の有無 / IS08 3.6「Quality Check」)。

実装解釈メモ(metadataスキーマ): `design_document.metadata["quality_notes"]` を入力源とし、
以下2キーそれぞれに検出済み問題点の説明文字列リストを保持する前提とする(architecture_check.py
と同様の理由による。IS08 3.本文参照)。

quality_notes = {
    "reusability": list[str],       # 再利用可能性に関する指摘
    "over_engineering": list[str],  # 過剰設計に関する指摘
}
"""

from __future__ import annotations

from foundation.types import Design

from .types import AuditCategory, AuditIssue


def check_quality(design_document: Design) -> list[AuditIssue]:
    """Design Documentの再利用可能性・過剰設計の有無を確認する。"""
    notes = (design_document.metadata or {}).get("quality_notes") or {}

    issues: list[AuditIssue] = []
    for message in notes.get("reusability") or []:
        issues.append(AuditIssue(category=AuditCategory.REUSABILITY, message=message, location=None))
    for message in notes.get("over_engineering") or []:
        issues.append(AuditIssue(category=AuditCategory.OVER_ENGINEERING, message=message, location=None))
    return issues
