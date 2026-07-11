"""Command Router のデータクラス・Enum定義(IS05仕様書3節)。

設計書3.1節・3.5節で明示された入出力(Raw Command / Normalized Command /
Command Type / Destination Module / Routed Command / Dispatch Result)を
dataclass/Enumとして具体化する。Foundation F01のDomain Model共通属性
(id/created_at/updated_at/metadata)はCommand Router固有のデータには
直接適用しない(Command RouterはTask/Workflow等の永続Domainを保持しないため)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class CommandType(str, Enum):
    """設計書3.3節 Command Type。MVPで対象とする種別のみ。"""

    PLAN = "PLAN"
    DESIGN = "DESIGN"
    IMPLEMENT = "IMPLEMENT"
    REVIEW = "REVIEW"
    STATUS = "STATUS"
    HELP = "HELP"
    UNKNOWN = "UNKNOWN"


class DestinationModule(str, Enum):
    """設計書3.4節 Routingテーブルの転送先。Schedulerは含まない
    (Command Router→Schedulerの転送は行わない: Design Freeze是正事項)。
    """

    PLANNER = "Planner"
    DESIGNER = "Designer"
    EXECUTOR = "Executor"
    REVIEWER = "Reviewer"
    STATE_MANAGER = "State Manager"
    SYSTEM = "System"


@runtime_checkable
class RawCommandLike(Protocol):
    """設計書3.1節 入力の構造的契約(Structural typing / PEP 544)。

    `receive()`/`normalize()`が実際に要求するのはこの7属性への読み取りアクセスのみ
    であり、具象クラス`RawCommand`のimportを必須としない。Scheduler(M14)等、他モジュール
    はこの形状(command_id/source/user_id/timestamp/command/attachments/metadata)さえ
    満たせば、`command_router.models.RawCommand`をimportせずに`receive()`へ入力を渡せる
    (Design Freeze監査: Scheduler→Command Routerの一方向依存を維持するための整合)。
    """

    command_id: str
    source: str
    user_id: str
    timestamp: datetime
    command: str
    attachments: list[str]
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RawCommand:
    """設計書3.1節 入力。`RawCommandLike`を満たす具象実装(Command Router内部・テスト用)。"""

    command_id: str
    source: str
    user_id: str
    timestamp: datetime
    command: str
    attachments: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedCommand:
    """receive()の出力。入力元差異(プレフィックス等)を吸収した共通形式。"""

    command_id: str
    source: str
    user_id: str
    timestamp: datetime
    raw_text: str  # 例: "plan LP改善"(先頭のcommand_type語+payload)
    attachments: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RoutedCommand:
    """classify()・route()の結果を束ね、dispatch()へ渡すための構造体。
    Command Router自身はこの内容を解釈・判断しない(4.1節: Routerは判断しない)。
    """

    normalized: NormalizedCommand
    command_type: CommandType
    payload: str
    destination: DestinationModule


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """dispatch()の出力。"""

    command_id: str
    destination: DestinationModule
    accepted: bool
    detail: str = ""
