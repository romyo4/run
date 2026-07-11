"""要件充足確認(IS08 3.2「要件充足」/ 3.6「Requirement Check」)。

実装解釈メモ(metadataスキーマ): Foundation `Design` dataclassは
`id/created_at/updated_at/metadata` のみを持ち、Architect固有の設計内容フィールドを
追加しない方針(IS08 3.)のため、本チェックは `design_document.metadata` に格納された
以下2キーを入力源として扱う。

- `requirements`: list[str] — 監査対象の要件一覧(要件ID・要件内容いずれの文字列表現でも可)
- `requirements_covered`: list[str] — Design Documentが実際にカバーしている要件一覧

いずれのキーも欠落時は「情報なし」として扱い、Findingは発生させない
(要件情報が与えられない場合にAuditorが独自に要件を推測・追加することはしない。
design/M08 Design Auditor.txt 4.4「監査基準固定」)。
"""

from __future__ import annotations

from foundation.types import Design

from .types import AuditCategory, AuditIssue


def check_requirements(design_document: Design) -> list[AuditIssue]:
    """Design Documentが要件一覧を充足しているかを確認し、未充足のFinding一覧を返す。"""
    metadata = design_document.metadata or {}
    requirements = metadata.get("requirements") or []
    covered = set(metadata.get("requirements_covered") or [])

    findings: list[AuditIssue] = []
    for requirement in requirements:
        if requirement not in covered:
            findings.append(
                AuditIssue(
                    category=AuditCategory.REQUIREMENT_FULFILLMENT,
                    message=f"要件 '{requirement}' がDesign Documentでカバーされていない",
                    location=None,
                )
            )
    return findings
