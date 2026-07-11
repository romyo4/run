# IS14 Scheduler 実装仕様書

> 本書は `M14 Scheduler.txt`（確定済み詳細設計書）を実装レベルへ落とし込んだものであり、設計書に記載のない機能を追加しない。設計書と本書が矛盾する場合は設計書を正とする。
> Command Router(M05)との依存方向は `CHANGELOG.md` / Design Freeze監査により **Scheduler → Command Router の一方向** に確定済みであり、本仕様書もこの前提を厳守する（Command RouterからSchedulerを呼び出すコードは実装しない）。

---

## 1. モジュール概要

Scheduler は、AI Development Pipeline において Workflow の**起動管理のみ**を担当するモジュールである。手動実行（Slack/Discord/CLI/API）・定期実行（毎日/毎週/毎月/Cron）・イベント実行（Pull Request Merged / Workflow Completed / Webhook Received / Timer）の3方式からの起動要求を受け付け、Execution Request を生成して Command Router へ引き渡す。あわせて、MVPでは単一キューによる実行管理・同一Workflowの重複起動禁止・最大3回までの自動リトライ・実行履歴の記録を行う。要件分析・設計・コード生成・テスト・レビュー・Pull Request作成・GitHub操作・Workflowの内容/Execution Plan/Design Documentの変更は一切行わない。

---

## 2. ファイル構成

```text
src/scheduler/
├── __init__.py                # 公開シンボルの再エクスポート（SchedulerModule, 各dataclass）
├── models.py                  # F01 Workflow Domainを参照しつつ、Scheduler固有dataclass/Enumを定義
├── exceptions.py               # Foundationのエラー階層を継承したScheduler固有例外
├── command_router_client.py   # Command Routerへの一方向呼び出しアダプタ（Port + 実装）
├── execution_queue.py         # 単一キュー管理・同一Workflow重複起動禁止(4.4)
├── retry_manager.py           # リトライ回数管理・最大3回制御(4.3)
├── history_recorder.py        # Execution History記録・参照
├── logging_utils.py           # get_logger()連携・Secret/Token/Credentialマスキング
├── scheduler_module.py        # 公開インターフェース schedule/trigger/retry/status を実装するBaseModule継承クラス
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_execution_queue.py
    ├── test_retry_manager.py
    ├── test_history_recorder.py
    ├── test_logging_utils.py
    ├── test_command_router_client.py
    └── test_scheduler_module.py
```

役割の要点:

| ファイル | 役割 |
|---|---|
| `models.py` | ScheduleDefinition / ScheduledWorkflow / Event(ManualRequest含む) / ExecutionRequest / FailedExecution / RetryRequest / ExecutionHistory / ScheduleStatus / 各Enumを定義。Workflow実体はFoundation `types.Workflow`（`workflow_id`で参照）をそのまま利用し、再定義しない。 |
| `exceptions.py` | `FoundationError` を継承したScheduler固有例外を定義。 |
| `command_router_client.py` | Scheduler→Command Routerの一方向呼び出しのみを行うアダプタ。Command Routerの公開インターフェースのうち `receive()` のみを呼び出す（Scheduler側からclassify/route/dispatchを直接呼ぶことはしない）。 |
| `execution_queue.py` | MVPの単一キューと「実行中Workflowの重複起動禁止」を管理するインメモリ構造。 |
| `retry_manager.py` | Workflowごとのリトライ回数を追跡し、最大3回制御を行う。 |
| `history_recorder.py` | Execution Historyの記録・直近履歴/全履歴の参照を提供する。 |
| `logging_utils.py` | ロギング仕様（timestamp, workflow_id, trigger_type, execution_result, retry_count, duration）の出力とSecret系フィールドのマスキングを提供する。 |
| `scheduler_module.py` | `BaseModule` を継承し、公開インターフェース `schedule()` / `trigger()` / `retry()` / `status()` を実装する。内部で上記各コンポーネントを組み合わせる。 |

---

## 3. データクラス定義

Foundation `F01 Domain Model` の `Workflow`（`id`, `created_at`, `updated_at`, `metadata` を共通属性として持つ）をそのまま参照し、Scheduler側で `Workflow` を再定義しない。Scheduler固有の入出力は以下の通り `models.py` にdataclassとして定義する。

```python
# src/scheduler/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TriggerType(str, Enum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    EVENT = "EVENT"


class ScheduleFrequency(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    CRON = "CRON"


class EventType(str, Enum):
    PULL_REQUEST_MERGED = "PULL_REQUEST_MERGED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WEBHOOK_RECEIVED = "WEBHOOK_RECEIVED"
    TIMER = "TIMER"


class ExecutionResultStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    RETRY_LIMIT_EXCEEDED = "RETRY_LIMIT_EXCEEDED"


class WorkflowRunState(str, Enum):
    IDLE = "IDLE"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRY_LIMIT_EXCEEDED = "RETRY_LIMIT_EXCEEDED"


# --- 3.5 公開インターフェースの入力型 -----------------------------------

@dataclass(frozen=True)
class ScheduleDefinition:
    """schedule() の入力。定期実行/Cron実行の定義。"""
    workflow_id: str
    frequency: ScheduleFrequency
    cron_expression: str | None = None      # frequency == CRON の場合に必須
    time_of_day: str | None = None          # "HH:MM"。DAILY/WEEKLY/MONTHLYで使用
    day_of_week: int | None = None          # 0=Mon〜6=Sun。WEEKLYで使用
    day_of_month: int | None = None         # 1-31。MONTHLYで使用
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ManualRequest:
    """手動起動（Slack/Discord/CLI/API）の入力。trigger()呼び出し前にEventへ変換される。"""
    workflow_id: str
    source: str                              # "slack" | "discord" | "cli" | "api"
    requested_by: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    """trigger() の入力。手動/定期/イベントいずれの起動要求も本型に正規化して渡す。"""
    workflow_id: str
    trigger_type: TriggerType
    source: str                              # 例: "slack", "scheduler", "github_webhook"
    occurred_at: datetime
    event_type: EventType | None = None       # trigger_type == EVENT の場合に設定
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FailedExecution:
    """retry() の入力。"""
    request_id: str
    workflow_id: str
    failure_reason: str
    retry_count: int
    failed_at: datetime


# --- 3.4 成果物（公開インターフェースの出力型） --------------------------

@dataclass(frozen=True)
class ScheduledWorkflow:
    """schedule() の出力。"""
    schedule_id: str
    workflow_id: str
    definition: ScheduleDefinition
    created_at: datetime
    next_run_at: datetime | None
    enabled: bool = True


@dataclass(frozen=True)
class ExecutionRequest:
    """trigger() の出力。Command Routerへ渡す実行要求。"""
    request_id: str
    workflow_id: str
    trigger_type: TriggerType
    source: str
    requested_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0


@dataclass(frozen=True)
class RetryRequest:
    """retry() の出力。"""
    retry_request_id: str
    original_request_id: str
    workflow_id: str
    retry_count: int
    requested_at: datetime


@dataclass(frozen=True)
class ExecutionHistory:
    """実行履歴1件分。"""
    history_id: str
    workflow_id: str
    request_id: str
    trigger_type: TriggerType
    execution_result: ExecutionResultStatus
    retry_count: int
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None


@dataclass(frozen=True)
class ScheduleStatus:
    """status() の出力。"""
    workflow_id: str
    state: WorkflowRunState
    is_running: bool
    retry_count: int
    last_history: ExecutionHistory | None
    updated_at: datetime
```

補足:
- `ScheduleDefinition.workflow_id` / `Event.workflow_id` はFoundation `Workflow.id` を参照する外部キーであり、Workflowの内容そのものはScheduler側で保持・変更しない（4.2 制約）。
- 全dataclassは `frozen=True` とし、Schedulerが受け取った入力値を内部で書き換えないことを型レベルで担保する。

---

## 4. クラス・関数シグネチャ

### 4.1 公開インターフェース（`scheduler_module.py`）

```python
from __future__ import annotations

from foundation.base_module import BaseModule
from foundation.result import Result
from foundation.interfaces import ConfigurationClient
from scheduler.command_router_client import CommandRouterClient
from scheduler.execution_queue import ExecutionQueue
from scheduler.retry_manager import RetryManager
from scheduler.history_recorder import HistoryRecorder
from scheduler.models import (
    Event,
    ExecutionRequest,
    FailedExecution,
    RetryRequest,
    ScheduleDefinition,
    ScheduledWorkflow,
    ScheduleStatus,
)


class SchedulerModule(BaseModule):
    def __init__(
        self,
        command_router_client: CommandRouterClient,
        configuration_client: ConfigurationClient,
        execution_queue: ExecutionQueue | None = None,
        retry_manager: RetryManager | None = None,
        history_recorder: HistoryRecorder | None = None,
    ) -> None: ...

    def name(self) -> str: ...

    def health_check(self) -> Result[bool]: ...

    def schedule(self, definition: ScheduleDefinition) -> Result[ScheduledWorkflow]:
        """Schedule Definitionを登録し、Scheduled Workflowを返す。(3.5 schedule())"""

    def trigger(self, event: Event) -> Result[ExecutionRequest]:
        """手動/定期/イベントいずれかのEventを受けてExecution Requestを生成し、
        Command Routerへ引き渡す。同一Workflowが実行中の場合は起動しない(4.4)。(3.5 trigger())"""

    def retry(self, failed_execution: FailedExecution) -> Result[RetryRequest]:
        """失敗した実行のリトライ要求を生成する。最大3回を超える場合は失敗として記録する(4.3)。
        (3.5 retry())"""

    def status(self, workflow_id: str) -> Result[ScheduleStatus]:
        """Workflow IDに対応する現在のSchedule Statusを返す。(3.5 status())"""
```

### 4.2 Command Router連携（`command_router_client.py`）

```python
from __future__ import annotations

from typing import Any, Protocol

from foundation.result import Result
from scheduler.models import ExecutionRequest


class CommandRouterClient(Protocol):
    def receive(self, raw_command: dict[str, Any]) -> Result[Any]:
        """Command Router(M05)の公開インターフェース receive() をそのまま呼び出す。
        Schedulerはこれ以外(classify/route/dispatch)を直接呼び出さない。"""
        ...


class CommandRouterAdapter:
    """CommandRouterClient の具象実装。Scheduler→Command Routerの一方向依存のみを持つ。"""

    def __init__(self, command_router: CommandRouterClient) -> None: ...

    def submit(self, request: ExecutionRequest) -> Result[dict[str, Any]]:
        """ExecutionRequestをCommand Router向けRaw Command形式へ変換し、receive()へ渡す。"""
        ...
```

### 4.3 実行キュー（`execution_queue.py`）

```python
from __future__ import annotations

from foundation.result import Result
from scheduler.models import ExecutionRequest


class ExecutionQueue:
    """MVPでは単一キュー。同一Workflowの重複起動を禁止する(4.4)。"""

    def __init__(self) -> None: ...

    def try_enqueue(self, request: ExecutionRequest) -> Result[bool]:
        """workflow_idが実行中でなければキューに積みTrueを返す。
        実行中であればResult(success=False, error=DuplicateWorkflowExecutionError)を返す。"""

    def mark_running(self, workflow_id: str) -> None: ...

    def mark_finished(self, workflow_id: str) -> None: ...

    def is_running(self, workflow_id: str) -> bool: ...
```

### 4.4 リトライ管理（`retry_manager.py`）

```python
from __future__ import annotations

from typing import ClassVar

from foundation.result import Result
from scheduler.models import FailedExecution, RetryRequest


class RetryManager:
    MAX_RETRY_COUNT: ClassVar[int] = 3  # 4.3 制約

    def __init__(self) -> None: ...

    def get_retry_count(self, workflow_id: str) -> int: ...

    def next_retry(self, failed_execution: FailedExecution) -> Result[RetryRequest]:
        """failed_execution.retry_count < MAX_RETRY_COUNT の場合のみRetryRequestを生成する。
        超過時はResult(success=False, error=RetryLimitExceededError)を返す。"""

    def reset(self, workflow_id: str) -> None:
        """正常終了時にリトライカウントを初期化する。"""
```

### 4.5 履歴記録（`history_recorder.py`）

```python
from __future__ import annotations

from foundation.result import Result
from scheduler.models import ExecutionHistory


class HistoryRecorder:
    def __init__(self) -> None: ...

    def record(self, history: ExecutionHistory) -> Result[None]: ...

    def latest(self, workflow_id: str) -> ExecutionHistory | None: ...

    def all_for(self, workflow_id: str) -> list[ExecutionHistory]: ...
```

すべての公開メソッドはFoundation `Result[T]`（`success: bool`, `value: T | None`, `error: FoundationError | None`）でラップして返却し、公開インターフェース層（`schedule`/`trigger`/`retry`/`status`）では例外を送出しない。

---

## 5. エラー処理

### 5.1 エラー階層（`exceptions.py`）

Foundationの共通エラー階層（`FoundationError` / `ValidationError` / `NotFoundError` / `StateTransitionError` / `ExternalServiceError` 等）を継承し、Scheduler固有の意味を持つ例外のみを追加する。新しい基底例外は追加しない（Foundation 4.2 制約に準拠）。

```python
from __future__ import annotations

from foundation.errors import (
    ExternalServiceError,
    FoundationError,
    NotFoundError,
    StateTransitionError,
    ValidationError,
)


class SchedulerError(FoundationError):
    """Scheduler内で発生するエラーの基底クラス。"""


class InvalidScheduleDefinitionError(ValidationError, SchedulerError):
    """ScheduleDefinitionの内容が不正な場合(例: CRON指定なのにcron_expression未設定)。"""


class DuplicateWorkflowExecutionError(StateTransitionError, SchedulerError):
    """同一Workflowが実行中に再度起動要求された場合(4.4 制約)。"""


class RetryLimitExceededError(StateTransitionError, SchedulerError):
    """リトライ回数が最大3回を超過した場合(4.3 制約)。"""


class UnknownWorkflowError(NotFoundError, SchedulerError):
    """status()/retry()等で未知のworkflow_idが指定された場合。"""


class CommandRouterDispatchError(ExternalServiceError, SchedulerError):
    """Command Router呼び出し(receive())が失敗した場合。"""
```

### 5.2 処理方針

- 公開インターフェース（`schedule`/`trigger`/`retry`/`status`）は内部で例外を捕捉し、`Result(success=False, value=None, error=<該当例外インスタンス>)` に変換して返す。呼び出し元へ例外を送出しない。
- `trigger()` において対象Workflowが実行中の場合、`ExecutionQueue.try_enqueue()` が `DuplicateWorkflowExecutionError` を含む `Result` を返し、`SchedulerModule.trigger()` はそのまま失敗Resultとして返却する。新規Execution Requestは生成しない（4.4 制約）。
- `retry()` は `RetryManager.next_retry()` に処理を委譲する。`failed_execution.retry_count >= RetryManager.MAX_RETRY_COUNT`（3回）の場合、`RetryLimitExceededError` を含む失敗 `Result` を返し、`HistoryRecorder` に `execution_result=ExecutionResultStatus.RETRY_LIMIT_EXCEEDED` の `ExecutionHistory` を記録した上で**失敗として確定させる**（設計書 4.3「超過した場合は失敗として記録する」に対応）。以降、当該Workflowへの自動リトライは行わない。
- Command Router呼び出し（`CommandRouterAdapter.submit()`）が失敗した場合は `CommandRouterDispatchError` でラップし、`ExecutionHistory` に `execution_result=ExecutionResultStatus.FAILURE` を記録した上で `trigger()` の戻り値を失敗Resultとする。Schedulerはこの失敗を検知してもCommand Router側の処理内容には関与しない（責務外）。

---

## 6. ロギング仕様

### 6.1 出力方法

- `foundation.logger.get_logger("scheduler")` を通じて取得したLoggerのみを使用する（標準`logging`ライブラリ、モジュール独自のロガー生成は行わない）。
- 出力項目は設計書 4.5 の通り固定する: `timestamp`, `workflow_id`, `trigger_type`, `execution_result`, `retry_count`, `duration`。

```python
# src/scheduler/logging_utils.py
from __future__ import annotations

from datetime import datetime
from logging import Logger
from typing import Any, Mapping

_SENSITIVE_KEYS = frozenset(
    {"secret", "token", "access_token", "credential", "password", "api_key"}
)
_MASK = "***REDACTED***"


def sanitize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """payload内のSecret/Access Token/Credential系フィールドを再帰的にマスキングする。"""
    ...


def log_execution(
    logger: Logger,
    *,
    workflow_id: str,
    trigger_type: str,
    execution_result: str,
    retry_count: int,
    duration_seconds: float | None,
    timestamp: datetime | None = None,
) -> None:
    """設計書4.5の6項目のみを構造化してINFO/ERRORログとして出力する。
    payloadやconfiguration値そのものは本関数の引数に含めない。"""
    ...
```

### 6.2 Secret/Access Token/Credential非出力の実装方針

- `log_execution()` の引数は上記6項目のプリミティブ値のみに限定し、そもそも `Event.payload` / `ExecutionRequest.payload` / `ConfigurationClient.get()` の戻り値をログ引数として受け取れない設計とする（関数シグネチャレベルで混入を防止）。
- `payload` の内容をデバッグ目的で出力する必要がある場合は、必ず `sanitize_payload()` を経由し、`_SENSITIVE_KEYS` に一致するキー（大小文字・スネーク/キャメル差異を吸収するため小文字化して比較）を `_MASK` に置換してから出力する。
- Configuration経由で取得した値（例: Webhook Secret、GitHub Token）は `ExecutionRequest.payload` 等に格納しない運用とし、Command Routerへの引き渡しも識別子・参照キーのみを渡す（値そのものを保持しない）。

---

## 7. Unit Testケース一覧（unittest）

`src/scheduler/tests/` 配下、`unittest.TestCase` ベース。pytestは使用しない。

### `test_models.py`
- `test_execution_request_default_retry_count_is_zero`
- `test_schedule_definition_is_frozen_and_immutable`
- `test_event_requires_event_type_only_when_trigger_type_is_event`

### `test_execution_queue.py`
- `test_try_enqueue_succeeds_for_new_workflow`
- `test_try_enqueue_rejects_duplicate_running_workflow`
- `test_try_enqueue_allows_different_workflow_ids_concurrently`
- `test_mark_finished_allows_requeue_of_same_workflow`
- `test_is_running_reflects_current_queue_state`

### `test_retry_manager.py`
- `test_first_retry_returns_retry_request_with_count_one`
- `test_retry_count_increments_up_to_max_of_three`
- `test_retry_beyond_max_count_returns_retry_limit_exceeded_error`
- `test_reset_clears_retry_count_after_successful_execution`

### `test_history_recorder.py`
- `test_record_stores_execution_history_entry`
- `test_latest_returns_most_recent_history_for_workflow`
- `test_all_for_returns_entries_in_chronological_order`
- `test_latest_returns_none_when_no_history_exists`

### `test_logging_utils.py`
- `test_sanitize_payload_masks_secret_and_token_fields`
- `test_sanitize_payload_masks_nested_credential_fields`
- `test_sanitize_payload_preserves_non_sensitive_fields`
- `test_log_execution_emits_required_six_fields_only`

### `test_command_router_client.py`
- `test_submit_converts_execution_request_to_raw_command_format`
- `test_submit_returns_success_result_on_command_router_ack`
- `test_submit_wraps_command_router_failure_as_command_router_dispatch_error`
- `test_submit_never_forwards_command_router_call_back_to_scheduler` (一方向依存の回帰防止)

### `test_scheduler_module.py`
- `test_schedule_registers_daily_schedule_definition`
- `test_schedule_registers_cron_schedule_definition`
- `test_schedule_rejects_cron_frequency_without_cron_expression`
- `test_trigger_manual_request_creates_execution_request` （Slack/CLI等の手動起動）
- `test_trigger_scheduled_time_creates_execution_request` （定期実行起動）
- `test_trigger_event_creates_execution_request` （Pull Request Merged等のイベント起動）
- `test_trigger_rejects_duplicate_workflow_execution_when_already_running`
- `test_trigger_dispatches_execution_request_to_command_router`
- `test_trigger_records_execution_history_on_success`
- `test_trigger_records_execution_history_on_command_router_failure`
- `test_retry_creates_retry_request_within_max_count`
- `test_retry_returns_error_when_max_retry_count_exceeded`
- `test_retry_records_failure_history_when_max_retry_count_exceeded`
- `test_status_returns_current_schedule_status_for_known_workflow`
- `test_status_returns_unknown_workflow_error_for_unregistered_workflow_id`
- `test_health_check_returns_success_result`

---

## 8. MVP範囲の明記

設計書 5.3節「重厚壮大化監査」にて対象外と判定済みの以下の機能は、本実装仕様書においても**実装しない**。

- 分散ジョブスケジューラ
- 優先度ベース実行
- ワーカープール
- Kubernetes Job管理
- オートスケーリング
- DAGエンジン
- 分散キュー
- マルチノード実行

上記に対応し、本仕様書は以下をMVP実装範囲として明記する。

- 実行管理は**単一プロセス内・単一キュー**（`ExecutionQueue`）に限定する。
- リトライは最大3回の**単純カウンタ方式**（`RetryManager`）とし、優先度・バックオフ戦略の高度化は行わない。
- Workflow起動後の内部処理（Planner→Architect→...→Reviewer等のDAG的な依存関係）はCommand Router以降の責務であり、SchedulerはExecution Requestを1回引き渡す（`CommandRouterAdapter.submit()` → `receive()`）だけで完結する。
- Scheduler自身はWorkflowの内容・Execution Plan・Design Documentを一切変更しない（4.2 制約）。データクラスもすべて `frozen=True` として不変性を保証する。
