"""`get()` 実装のための最小限のインメモリストア(IS19 3.5節)。

Workflow ID をキーに直近ビルド済みの `AIContext` のみを保持し、Knowledge本文・
Repository情報そのものをキャッシュする責務は持たない。
"""

from dataclasses import dataclass, field

from context_manager.types import AIContext


@dataclass
class ContextStore:
    """Context Manager自身が生成したAIContextの『最新版のみ』をworkflow_id単位で保持する
    (Knowledge本文・Repository情報を複製・保持するものではない)。"""

    _latest: dict[str, AIContext] = field(default_factory=dict)
    _version_counters: dict[str, int] = field(default_factory=dict)

    def next_version(self, workflow_id: str) -> str:
        """workflow_idごとに単調増加する版番号を`f"v{n}"`形式で採番する(IS19 3.4節注記)。"""
        current = self._version_counters.get(workflow_id, 0) + 1
        self._version_counters[workflow_id] = current
        return f"v{current}"

    def save(self, context: AIContext) -> None:
        """workflow_id単位で最新のAIContextのみを保持する(旧版は破棄する)。"""
        self._latest[context.workflow_id] = context

    def get(self, workflow_id: str) -> AIContext | None:
        """直近ビルド済みのAIContextを返す。存在しない場合はNoneを返す。"""
        return self._latest.get(workflow_id)
