"""Fableレビューエンジン呼び出しの抽象化層(Adapter Pattern、F00、IS13 4.4節)。

評価基準(何を不要機能とみなすか等)の解釈自体はFable側の責務とし、本モジュールは
呼び出し規約(インターフェース)のみを定義する。実際のFable呼び出し(HTTP/SDK等)は
本モジュールの実装対象外であり、具体実装(アダプタ)は別途本インターフェースを
継承して提供する。テストではフェイク実装を用いる。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from foundation.result import Result
from foundation.types import Review
from weekly_reviewer.models import (
    BusinessEvaluation,
    MvpEvaluation,
    TechnicalDebtFinding,
    WeeklyAnalysis,
)

__all__ = ["FableClient"]


class FableClient(ABC):
    """Fableレビューエンジンとの差異を吸収するAdapter層(F00: Adapter Pattern)。
    評価基準そのものはFable側の実装/プロンプトに委ね、本インターフェースは
    呼び出し規約のみを定義する。"""

    @abstractmethod
    def review_business_alignment(self, business_goal: str, weekly_analysis: WeeklyAnalysis) -> Result[BusinessEvaluation]:
        """設計書3.3節Business Goal評価。"""

    @abstractmethod
    def review_mvp_fitness(self, weekly_analysis: WeeklyAnalysis) -> Result[MvpEvaluation]:
        """設計書3.3節MVP評価。"""

    @abstractmethod
    def review_technical_debt(
        self,
        weekly_analysis: WeeklyAnalysis,
        review_reports: list[Review],
        technical_debt_reports: list[dict],
    ) -> Result[TechnicalDebtFinding]:
        """設計書3.3節Technical Debt評価。"""

    @abstractmethod
    def recommend_priorities(
        self,
        weekly_analysis: WeeklyAnalysis,
        business_evaluation: BusinessEvaluation,
        mvp_evaluation: MvpEvaluation,
        technical_debt: TechnicalDebtFinding,
    ) -> Result[tuple[list[str], list[str], list[str], list[str]]]:
        """設計書3.3節Development Direction評価。戻り値は
        (achievements, risks, recommendations, top_priority_next_week)の順のタプル。"""
