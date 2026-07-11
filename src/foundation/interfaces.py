"""ConfigurationClient抽象インターフェース(F03 Configuration Access Pattern)。

実装(設定値の実体管理)はConfiguration Manager(M17)が提供する。
Foundation自身は設定値をキャッシュ・保持しない。
"""

from abc import ABC, abstractmethod
from typing import Any

from foundation.result import Result


class ConfigurationClient(ABC):
    """設定取得インターフェース。インスタンスメソッドとして実装する。

    初版はF02公開インターフェース(BaseModule)との対称性から`@staticmethod`と
    宣言していたが、Configuration Manager(M17)の実装および他20モジュールの
    大多数がインスタンス経由(`config_client.get(...)`、DIで注入されたインスタンス)
    で利用する前提で実装されていたため、実態に合わせてインスタンスメソッドに
    是正した(統合レビューで判明。CHANGELOG.md参照)。
    """

    @abstractmethod
    def get(self, module_name: str, key: str) -> Result[Any]:
        """指定モジュール・キーの設定値を取得する。"""
