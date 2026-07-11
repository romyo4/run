"""4段階チェック(Requirement/Architecture/MVP/Quality)の結果からAuditResultStatusを
合成する(IS08 3.6 処理フロー / 4.クラス・関数シグネチャ 実装解釈メモ)。

実装解釈メモ(判定ロジック): 設計書は各チェックからAudit Report全体のresult(4区分)を
導く集約規則を明記していない。IS08本文の実装解釈メモに従い、以下の優先順位を採用する。

- violations が1件以上 →
    - violations に `AuditCategory.MVP_FITNESS` が含まれる場合は `REJECT`
      (5.3 重厚壮大化監査でMVP対象外と判定された機能の検出は最も重大な違反として扱う)
    - それ以外は `REWORK_REQUIRED`
- violations が0件で warnings が1件以上 → `PASS_WITH_COMMENT`
- いずれも0件 → `PASS`

この規則は設計書に明記がないための実装上の解釈であり、Architect/Design Auditor
責任者のレビューを要する(IS08 4章 実装解釈メモ)。
"""

from __future__ import annotations

from .types import AuditCategory, AuditIssue, AuditResultStatus


def aggregate_result(
    findings: list[AuditIssue],
    warnings: list[AuditIssue],
    violations: list[AuditIssue],
) -> AuditResultStatus:
    """findings/warnings/violationsからAudit Report全体のresultを合成する。"""
    del findings  # findingsは監査結果の判定には用いない(参考情報としてAudit Reportへ記録するのみ)

    if violations:
        if any(issue.category is AuditCategory.MVP_FITNESS for issue in violations):
            return AuditResultStatus.REJECT
        return AuditResultStatus.REWORK_REQUIRED

    if warnings:
        return AuditResultStatus.PASS_WITH_COMMENT

    return AuditResultStatus.PASS
