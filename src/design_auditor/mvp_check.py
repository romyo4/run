"""MVP適合性確認(IS08 3.6「MVP Check」/ 5.3 重厚壮大化監査の判定ロジック)。

実装解釈メモ(検出対象): `design_document.metadata` のうち `features`(list[str])と
`content`(str、任意の自由記述テキスト)を検出対象とする。`constants.MVP_EXCLUDED_FEATURES`
に列挙されたキーワードが、featuresの各要素またはcontent中に部分文字列として出現するかを
判定する。新たな除外機能の判定基準をここで追加することはしない(design/M08 Design
Auditor.txt 4.4「監査基準固定」)。
"""

from __future__ import annotations

from foundation.types import Design

from .constants import MVP_EXCLUDED_FEATURES
from .types import MVPAssessment


def check_mvp_fitness(design_document: Design) -> MVPAssessment:
    """Design Document中にMVP対象外機能(5.3)が含まれていないかを確認する。"""
    metadata = design_document.metadata or {}
    features = metadata.get("features") or []
    content = metadata.get("content") or ""

    detected: list[str] = [
        excluded
        for excluded in MVP_EXCLUDED_FEATURES
        if excluded in content or any(excluded in feature for feature in features)
    ]

    return MVPAssessment(compliant=not detected, excluded_features_detected=detected, notes=[])
