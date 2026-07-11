"""Codex外部呼び出しの唯一の窓口を表すインターフェース(Adapter Pattern, F00)。

`executor.py`はここで定義される`CodexAdapter`インターフェースにのみ依存し、
Codexの実際の呼び出し方法(CLI/API等)を知らない。実際のCodex CLI/API呼び出しの
実装は本モジュールの対象外(Design Freeze注記のとおり、外部呼び出しはインターフェース
として定義するに留め、実呼び出しは行わない)。テストではこのインターフェースを満たす
フェイク実装(`tests/executor`配下)を用いる。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from executor.models import GeneratedTest, ImplementationContext, ModifiedFile
from foundation.result import Result


@dataclass(frozen=True)
class CodexConfig:
    """Codex呼び出し設定(モデル名・タイムアウト・リトライ回数)。

    Secret/Token/Credentialはここに含めない。
    """

    model: str
    timeout: int
    max_retry: int


@runtime_checkable
class CodexAdapter(Protocol):
    """Codex外部呼び出しの唯一の窓口(Adapter Pattern, F00)。"""

    def generate_implementation(self, context: ImplementationContext) -> Result[tuple[ModifiedFile, ...]]:
        """設計内容に基づき実装コードを生成し、変更ファイル一覧を返す。"""
        ...

    def generate_tests(
        self, context: ImplementationContext, modified_files: tuple[ModifiedFile, ...]
    ) -> Result[tuple[GeneratedTest, ...]]:
        """生成済み実装に対応するテストコードを生成する。テストの実行は行わない。"""
        ...
