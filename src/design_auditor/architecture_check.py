"""Architecture整合性確認(責務分離・モジュール境界・Interface整合性・Domain整合性・
Configuration整合性 / IS08 3.6「Architecture Check」)。

実装解釈メモ(metadataスキーマ): 要件充足確認と同様の理由(IS08 3.本文参照)により、
本チェックは `design_document.metadata["architecture_notes"]` を唯一の入力源として扱う。
`architecture_notes` はArchitect側が設計時点で自己申告するdictであり、Architecture整合性
の5監査観点それぞれに対応するキーで、検出済み違反の説明文字列リストを保持する前提とする。

architecture_notes = {
    "responsibility_separation": list[str],
    "module_boundary": list[str],
    "interface_consistency": list[str],
    "domain_consistency": list[str],
    "configuration_consistency": list[str],
}

キーが存在しない場合は「違反なし(空リスト)」として扱う。これは新規監査ルールの
追加ではなく、入力欠如時の安全側デフォルトである(design/M08 Design Auditor.txt 4.4)。
"""

from __future__ import annotations

from foundation.types import Design

from .types import AuditCategory, AuditIssue, ValidationResult

_CATEGORY_BY_NOTE_KEY: dict[str, AuditCategory] = {
    "responsibility_separation": AuditCategory.RESPONSIBILITY_SEPARATION,
    "module_boundary": AuditCategory.MODULE_BOUNDARY,
    "interface_consistency": AuditCategory.INTERFACE_CONSISTENCY,
    "domain_consistency": AuditCategory.DOMAIN_CONSISTENCY,
    "configuration_consistency": AuditCategory.CONFIGURATION_CONSISTENCY,
}


def check_architecture(design_document: Design) -> ValidationResult:
    """Design DocumentのArchitecture整合性(5観点)を確認する。"""
    notes = (design_document.metadata or {}).get("architecture_notes") or {}

    violations: list[AuditIssue] = []
    for note_key, category in _CATEGORY_BY_NOTE_KEY.items():
        for message in notes.get(note_key) or []:
            violations.append(AuditIssue(category=category, message=message, location=None))

    return ValidationResult(valid=not violations, violations=violations, notes=[])
