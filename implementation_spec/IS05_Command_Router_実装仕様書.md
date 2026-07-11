# IS05 Command Router 実装仕様書

> 本仕様書は `M05 Command Router.txt`（Design Freeze v1.0、STATUS転送先をState Managerへ是正済み）を唯一の正とする。設計書に明記のない機能（AI Intent Classification、NLP解析、LLM Routing、Policy Engine等）は実装しない。

---

## 1. モジュール概要

Command Router は、Slack・Discord・CLI・Web UI・API・Scheduler（内部コマンド）から受信したコマンドを、入力形式の正規化・種別判定を経て、Planner／Designer／Executor／Reviewer／State Managerへ転送するための**受信・正規化・振り分け・転送専用**モジュールである。要件分析・設計・実装・レビュー等の業務処理は一切行わず、Command Type と Routing Table のみに基づく同期処理でMVPを構成する。Design Freeze監査により、STATUSコマンドはScheduler(M14)を経由せずState Manager(M01)へ直接転送するよう修正されており、依存方向はScheduler→Command Routerの一方向のみに確定している。本モジュールはFoundation(M00)の`BaseModule`を継承し、戻り値は原則`Result[T]`でラップする。

---

## 2. ファイル構成

```text
src/command_router/
├── __init__.py          # パッケージ公開API（CommandRouter, models, errorsの再エクスポート）
├── models.py             # RawCommand / NormalizedCommand / CommandType / DestinationModule /
│                         # RoutedCommand / DispatchResult のdataclass・Enum定義
├── errors.py             # UnknownCommandError等、Foundationのエラー階層を継承する本モジュール固有例外
├── normalizer.py         # 入力元（Slack/Discord/CLI/WebUI/API/Scheduler）ごとの正規化ロジック
├── routing_table.py      # Command Type → Destination Module の静的テーブルとF03連携ロジック
├── router.py             # CommandRouter(BaseModule) 本体。receive/classify/route/dispatchを実装
└── tests/
    ├── __init__.py
    ├── test_normalizer.py
    ├── test_routing_table.py
    └── test_router.py
```

各ファイルの役割は単一責務に限定する（F00: Single Responsibility）。`normalizer.py`は入力差異の吸収のみ、`routing_table.py`はCommand TypeとDestination Moduleの対応関係のみ、`router.py`は公開インターフェース（receive/classify/route/dispatch）の実装と各モジュールへのオーケストレーションのみを担う。GitHub API呼び出し・Slack返信生成・PR作成・Workflow/Task/Knowledge状態の保持は、いずれのファイルにも実装しない（4.2, 4.4節の制約）。

---

## 3. データクラス定義

`models.py` に定義する。Foundation `F01`のDomain Model共通属性（id/created_at/updated_at/metadata）はCommand Router固有のデータには直接適用しない（Command RouterはTask/Workflow等の永続Domainを保持しないため）。ただし設計書3.1節・3.5節で明示された入出力（Raw Command / Normalized Command / Command Type / Destination Module / Dispatch Result）はすべてdataclass/Enumとして具体化する。

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


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
    （Command Router→Schedulerの転送は行わない: Design Freeze是正事項）。
    """

    PLANNER = "Planner"
    DESIGNER = "Designer"
    EXECUTOR = "Executor"
    REVIEWER = "Reviewer"
    STATE_MANAGER = "State Manager"
    SYSTEM = "System"


@dataclass(frozen=True, slots=True)
class RawCommand:
    """設計書3.1節 入力。"""

    command_id: str
    source: str
    user_id: str
    timestamp: datetime
    command: str
    attachments: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedCommand:
    """receive()の出力。入力元差異（プレフィックス等）を吸収した共通形式。"""

    command_id: str
    source: str
    user_id: str
    timestamp: datetime
    raw_text: str  # 例: "plan LP改善"（先頭のcommand_type語＋payload）
    attachments: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RoutedCommand:
    """classify()・route()の結果を束ね、dispatch()へ渡すための構造体。
    Command Router自身はこの内容を解釈・判断しない（4.1節: Routerは判断しない）。
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
```

---

## 4. クラス・関数シグネチャ

`router.py` にて `CommandRouter` クラスを `foundation.base_module.BaseModule` の具象クラスとして実装する。公開インターフェースは設計書3.5節の receive/classify/route/dispatch の4メソッドに限定し、名称・入出力を一致させる。

```python
from __future__ import annotations

from typing import Callable

from foundation.base_module import BaseModule
from foundation.result import Result
from foundation.logger import get_logger

from command_router.models import (
    CommandType,
    DestinationModule,
    DispatchResult,
    NormalizedCommand,
    RawCommand,
    RoutedCommand,
)
from command_router.errors import UnknownCommandError, DispatchTargetNotRegisteredError

# 転送先モジュールを呼び出すための最小限のAdapterインターフェース（F00: Adapter Pattern）。
# Command Router自身は各モジュールの処理内容を理解しない（4.1節）。
CommandHandler = Callable[[RoutedCommand], "Result[object]"]


class CommandRouter(BaseModule):
    def __init__(
        self,
        handlers: dict[DestinationModule, CommandHandler],
        config_client: "ConfigurationClient | None" = None,
    ) -> None:
        """handlers: Destination ModuleごとのCommandHandler。
        Planner/Designer/Executor/Reviewer/State Managerの実処理には関与せず、
        登録済みのCallableへ転送するのみ（4.4節: Routerは転送専用）。
        config_client: F03のConfigurationClient。Routing Table上書き取得に使用（任意）。
        """
        self._handlers = handlers
        self._config_client = config_client
        self._logger = get_logger("command_router")

    def name(self) -> str:
        return "command_router"

    def health_check(self) -> Result[bool]:
        return Result(success=True, value=True, error=None)

    def receive(self, raw_command: RawCommand) -> Result[NormalizedCommand]:
        """入力元（Slack/Discord/CLI/WebUI/API/Scheduler）ごとの差異を吸収し、
        共通フォーマット（NormalizedCommand）へ変換する。（設計書3.2節）
        """
        ...

    def classify(self, normalized: NormalizedCommand) -> Result[CommandType]:
        """NormalizedCommand.raw_textの先頭語を CommandType に解決する。
        NLP/AI推論は行わず、単純な文字列一致（大文字小文字を無視）のみ。
        一致しない場合は Result(success=True, value=CommandType.UNKNOWN, error=None) を返す
        （UNKNOWNは「不正コマンド」であり「処理失敗」ではないため success=True で表現する）。
        """
        ...

    def route(self, command_type: CommandType) -> Result[DestinationModule]:
        """Routing Table（routing_table.py）を用いて Destination Module を決定する。
        CommandType.UNKNOWNは転送先を持たないため Result(success=False, value=None,
        error=UnknownCommandError(...)) を返す。
        """
        ...

    def dispatch(
        self, destination: DestinationModule, command: RoutedCommand
    ) -> Result[DispatchResult]:
        """destinationに登録されたCommandHandlerへcommandを転送する。
        Router自身がGitHub API呼び出し・Slack返信生成・PR作成を行うことはない（4.4節）。
        未登録のdestinationは Result(success=False, error=DispatchTargetNotRegisteredError(...))。
        """
        ...
```

### Routing Tableの実装方法（`routing_table.py`）

```python
from __future__ import annotations

from command_router.models import CommandType, DestinationModule

# 設計書3.4節のRoutingテーブル。STATUSはState Managerへ直接転送し、Schedulerは含めない。
ROUTING_TABLE: dict[CommandType, DestinationModule] = {
    CommandType.PLAN: DestinationModule.PLANNER,
    CommandType.DESIGN: DestinationModule.DESIGNER,
    CommandType.IMPLEMENT: DestinationModule.EXECUTOR,
    CommandType.REVIEW: DestinationModule.REVIEWER,
    CommandType.STATUS: DestinationModule.STATE_MANAGER,
    CommandType.HELP: DestinationModule.SYSTEM,
}


def resolve_destination(
    command_type: CommandType,
    config_client: "ConfigurationClient | None" = None,
) -> "Result[DestinationModule]":
    """F03: ConfigurationClient.get("command_router", "routing_table") が
    Result[dict]で上書き値を返す場合はそれを優先し、取得不可・未設定の場合は
    ROUTING_TABLE（静的定義）にフォールバックする。CommandType.UNKNOWNは
    どちらのテーブルにも存在しないため必ずエラーResultとなる。
    """
    ...
```

Command追加時は `ROUTING_TABLE` （または `ConfigurationClient` 側のRouting設定）のみを更新すればよく、`router.py` 本体の変更を必要としない（設計書3.3節「Command追加時はRouterのみ更新する」に対応）。

---

## 5. エラー処理

`errors.py` にて、Foundationの `FoundationError` 階層を継承した本モジュール固有例外を定義する。新しい基底例外は追加せず、既存階層のサブクラスとしてのみ定義する（M00 3.6節）。

```python
from __future__ import annotations

from foundation.errors import ValidationError, NotFoundError


class UnknownCommandError(ValidationError):
    """classify()がCommandType.UNKNOWNと判定したコマンドをroute()する際に送出。
    実行しない・ログ出力・ユーザーへの通知（Result経由で呼び出し元へ伝播）を行う。
    """


class DispatchTargetNotRegisteredError(NotFoundError):
    """dispatch()時にdestinationに対応するCommandHandlerが未登録の場合に送出。"""
```

### UNKNOWNコマンドの扱い（設計書3.6節）

- `classify()` はUNKNOWNを**正常な判定結果**として `Result(success=True, value=CommandType.UNKNOWN)` で返す（解析自体は失敗していないため）。
- `route(CommandType.UNKNOWN)` は転送先が存在しないため `Result(success=False, value=None, error=UnknownCommandError(...))` を返す。
- UNKNOWNは**実行しない**（`dispatch()`を呼び出さない。呼び出し元がroute()のResultを見て後続処理を止める）。
- **ログ出力**は5章のロギング仕様に従い、`result=UNKNOWN` として記録する。
- **ユーザーへの通知**はCommand Router自身が行わない（4.4節: Slack返信生成禁止）。呼び出し元（Slack/Discord/CLI/API Connector）がResultのerrorを受け取り、各Connectorの責務としてユーザーへ通知する。

`dispatch()`が呼び出すCommandHandler自体が失敗した場合（Planner等の内部エラー）は、Handlerが返す`Result`の`error`をそのまま`DispatchResult`には含めず、`Result(success=False, error=...)`として`dispatch()`の戻り値にそのまま伝播する（Command Routerはエラー内容を変換・解釈しない）。

---

## 6. ロギング仕様

`foundation.logger.get_logger("command_router")` を各モジュールファイル（`router.py`等）で1回だけ取得し、モジュールレベルのロガーとして使い回す。

出力項目は設計書4.5節の6項目に固定する。

| 項目 | 内容 | 出力例 |
|---|---|---|
| timestamp | ログ出力時刻（loggingのデフォルトフォーマッタに委譲） | `2026-07-11 10:00:00` |
| source | RawCommand.source | `slack` |
| command | 正規化後のraw_text（先頭トークンのみ。ペイロード本文は出力しない） | `plan` |
| command_type | classify()の結果 | `PLAN` / `UNKNOWN` |
| destination | route()の結果（UNKNOWN時は`-`） | `Planner` |
| result | 各段階の成否（`OK` / `UNKNOWN` / `ERROR:<例外クラス名>`） | `OK` |

### Secretを出力しない実装方法

- `RawCommand.metadata` / `NormalizedCommand.metadata` の**値は一切ログに出力しない**。ログには `metadata.keys()` のみを記録する（キー名のみで値は伏せる）。
- `attachments` は件数のみ記録し、URL・ファイル内容は出力しない。
- `command`（コマンド全文）はログに出さず、`raw_text`の先頭トークン（command_type相当語）のみを出力する。ペイロード本文（自然言語部分）はSecretを含みうるため出力対象外とする。
- 例外オブジェクトを文字列化する際は例外クラス名のみを記録し、例外メッセージに機密情報が含まれる可能性がある場合はメッセージ本文を出力しない（`str(type(exc).__name__)` を使用）。
- ログ出力は `logger.info(...)` （正常系・UNKNOWN含む）と `logger.error(...)` （dispatch失敗等）の2レベルのみを使用し、DEBUGレベルでの詳細ダンプは行わない。

---

## 7. Unit Testケース一覧（unittest）

`tests/test_normalizer.py`

- `test_receive_slack_command_strips_slash_prefix`
- `test_receive_discord_command_strips_at_bot_prefix`
- `test_receive_cli_command_passthrough_without_prefix`
- `test_receive_preserves_command_id_user_id_timestamp`
- `test_receive_preserves_attachments_and_metadata`
- `test_receive_empty_command_returns_validation_error`
- `test_receive_unrecognized_source_does_not_raise`

`tests/test_routing_table.py`

- `test_resolve_destination_plan_maps_to_planner`
- `test_resolve_destination_design_maps_to_designer`
- `test_resolve_destination_implement_maps_to_executor`
- `test_resolve_destination_review_maps_to_reviewer`
- `test_resolve_destination_status_maps_to_state_manager`
- `test_resolve_destination_help_maps_to_system`
- `test_resolve_destination_unknown_returns_error_result`
- `test_routing_table_does_not_contain_scheduler_destination`
- `test_resolve_destination_uses_configuration_client_override_when_present`
- `test_resolve_destination_falls_back_to_static_table_when_config_client_unavailable`

`tests/test_router.py`

- `test_name_returns_command_router`
- `test_health_check_returns_success_true`
- `test_classify_plan_command_returns_command_type_plan`
- `test_classify_design_command_returns_command_type_design`
- `test_classify_implement_command_returns_command_type_implement`
- `test_classify_review_command_returns_command_type_review`
- `test_classify_status_command_returns_command_type_status`
- `test_classify_help_command_returns_command_type_help`
- `test_classify_is_case_insensitive`
- `test_classify_unrecognized_keyword_returns_command_type_unknown`
- `test_route_status_returns_state_manager_not_scheduler`
- `test_route_unknown_command_type_returns_error_result`
- `test_dispatch_calls_registered_handler_for_destination`
- `test_dispatch_returns_error_when_handler_not_registered`
- `test_dispatch_propagates_handler_result_without_modification`
- `test_dispatch_does_not_invoke_github_or_slack_side_effects`
- `test_full_pipeline_plan_command_reaches_planner_handler`
- `test_full_pipeline_unknown_command_is_not_dispatched`
- `test_full_pipeline_status_command_never_calls_scheduler_handler`
- `test_logging_does_not_output_metadata_values`
- `test_logging_records_required_six_fields`

---

## 8. MVP範囲の明記

設計書5.3節「重厚壮大化監査」により以下は**対象外**であり、本モジュールでは実装しない。

- AI Intent Classification（自然言語意図解析によるコマンド判定）
- NLP解析
- LLM Routing
- Policy Engine
- Event Bus
- Message Broker
- Plugin Framework
- Workflow Engine

加えて、設計書4章の制約に基づき以下を明記する。

- **同期処理のみ**（4.3節）。非同期Queue・`asyncio`・メッセージブローカーは採用しない。
- **状態を持たない**（4.2節）。Workflow・Task・Knowledgeの状態はCommand Router内で保持・キャッシュしない。
- **転送専用**（4.4節）。GitHub API呼び出し、Slack/Discord返信生成、PR作成は行わない。
- **判断しない**（4.1節）。要件分析・優先順位判断・設計判断・コード生成は行わない。`classify()`はCommand Type文字列の一致判定のみを行う。
- **Scheduler非依存**（Design Freeze是正事項）。STATUSはState Managerへ直接転送し、Command Router→Schedulerの転送経路は実装・テストのいずれにも存在させない。
