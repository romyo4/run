"""BaseModule抽象基底クラス(F02 共通Interface)。全モジュールが継承する。"""

from abc import ABC, abstractmethod

from foundation.result import Result


class BaseModule(ABC):
    @abstractmethod
    def name(self) -> str:
        """モジュール名を返す。"""

    @abstractmethod
    def health_check(self) -> Result[bool]:
        """モジュールの健全性を判定する。"""
