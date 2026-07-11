"""監査基準に関わる固定値(IS08 2. ファイル構成 / 5.3 重厚壮大化監査)。

設計書 5.3「重厚壮大化監査」でMVP対象外・削除済みと判定された機能名を保持する。
`mvp_check.py` の `check_mvp_fitness()` が、Design Document中にこれらのキーワードが
含まれるかを検出する材料としてのみ用いる。それ以外の用途では使用しない。
"""

from __future__ import annotations

MVP_EXCLUDED_FEATURES: tuple[str, ...] = (
    "AI設計生成",
    "自動修正",
    "UML生成",
    "コスト最適化",
    "パフォーマンス解析",
    "セキュリティ自動修正",
    "Enterprise Design Governance",
)
