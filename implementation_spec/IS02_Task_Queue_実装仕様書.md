# IS02 Task Queue 実装仕様書

- 参照設計書: `M02_Task_Queue_詳細設計.md`（確定済み・Design Freeze v1.0）
- 前提Foundation: `M00 Foundation.txt`（F00原則カタログ / F01 Domain Model / F02 Common Interface / F03 Configuration Access Pattern）
- 対象パッケージ: `src/task_queue/`
- 言語/規約: Python 3.13、型ヒント必須、dataclass、pathlib（本モジュールはファイルI/Oを行わないため該当箇所なし）、標準`logging`（`get_logger()`経由）、`unittest`、UTF-8、Ruff/Black準拠

---

## 1. モジュール概要

Task Queue は、AI Development Pipeline に投入されたタスクを優先順位・依存関係・並列実行数に基づいて管理し、実行可能になったタスクをWorkerへ配信するモジュールである。担当するのはタスク受付・キュー管理・優先順位付け・並列実行制御・依存関係管理・リトライ管理・キャンセル処理の7点のみであり、タスク内容の生成（Plannerの責務）や状態の正本管理（State Managerの責務）、Workflow起動判断（Schedulerの責務）は行わない。キュー内部で保持する`status`はあくまで実行制御用であり、正式な状態遷移の正本はState Managerとし、両者は同期する前提とする。

---

## 2. ファイル構成

```text
src/task_queue/
├── __init__.py           # 公開APIの再エクスポート
├── models.py              # QueueStatus / TaskPriority Enum、TaskQueue dataclass
├── errors.py               # Task Queue固有の例外（Foundationのエラー階層を継承）
├── queue_manager.py        # TaskQueueManager（BaseModule継承）。公開インターフェース7関数の実装本体
└── tests/
    ├── __init__.py
    └── test_queue_manager.py  # unittestによるテストケース
```

各ファイルの役割:

| ファイル | 役割 |
|---|---|
| `__init__.py` | `TaskQueueManager` / `TaskQueue` / `QueueStatus` / `TaskPriority` / 例外クラスを外部モジュールへ再エクスポートする |
| `models.py` | 設計書3.1（キュー状態）・3.2（データモデル）・3.3（優先順位）に対応するデータ構造のみを定義する。業務ロジックは持たない |
| `errors.py` | 設計書4.4（エラー処理）に対応するTask Queue固有の例外を、Foundationの`FoundationError`階層のサブクラスとして定義する |
| `queue_manager.py` | 公開インターフェース（enqueue/dequeue/peek/cancel/retry/reprioritize/list）と、排他制御・依存解決・デッドロック検知などの内部処理を実装する |
| `tests/test_queue_manager.py` | 設計書の「テスト観点」（FIFO/優先順位/並列実行/リトライ/キャンセル/依存関係/障害復旧）を網羅する |

---

## 3. データクラス定義（`models.py`）

### 3.1 キュー状態 Enum

設計書3.1の8状態をそのまま定義する。

```python
from enum import Enum


class QueueStatus(Enum):
    QUEUED = "Queued"
    WAITING_DEPENDENCY = "WaitingDependency"
    READY = "Ready"
    RUNNING = "Running"
    RETRY_WAITING = "RetryWaiting"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
```

### 3.2 優先順位 Enum

設計書3.3の5段階を、数値が小さいほど優先度が高い順に定義する（同一優先度内はFIFO＝`created_at`昇順）。

```python
from enum import IntEnum


class TaskPriority(IntEnum):
    EMERGENCY = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5
```

### 3.3 `TaskQueue` dataclass

設計書3.2のデータモデルをそのままフィールド化する。`task_id`はFoundation(F01)の`Task`/`SubTask` Domainの`id`を参照する値であり、Task Queueは`Task`/`SubTask`本体の内容を保持・解釈しない。

```python
from dataclasses import dataclass, field
from datetime import datetime

from task_queue.models import QueueStatus, TaskPriority


@dataclass
class TaskQueue:
    task_id: str
    priority: TaskPriority
    queue_name: str
    status: QueueStatus
    created_at: datetime
    depends_on: list[str] = field(default_factory=list)
    worker_id: str | None = None
    retry_count: int = 0
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
```

備考:
- フィールド名・型は設計書3.2の項目（task_id, priority, queue_name, status, depends_on[], worker_id, retry_count, created_at, scheduled_at, started_at, finished_at）と一致させている。dataclassの制約上、デフォルト値なしのフィールド（`created_at`まで）を先に、デフォルト値ありのフィールドを後に並べ替えているが、フィールド集合・型は設計書と同一である。
- `Task` / `SubTask` 本体（Foundation F01定義）は`foundation.types`からインポートして`enqueue()`の入力型として利用する。Task Queueはこれらの共通属性（`id`, `created_at`, `updated_at`, `metadata`）のうち`id`のみを`task_id`として参照し、他の内容には関与しない。

---

## 4. クラス・関数シグネチャ（`queue_manager.py`）

### 4.1 前提インポート

```python
from foundation.base_module import BaseModule
from foundation.result import Result
from foundation.interfaces import ConfigurationClient
from foundation.types import Task, SubTask
from foundation.logger import get_logger
from foundation.errors import FoundationError

from task_queue.models import QueueStatus, TaskPriority
from task_queue.models import TaskQueue
from task_queue.errors import (
    TaskNotFoundError,
    QueueNotFoundError,
    InvalidQueueTransitionError,
    MaxRetryExceededError,
    WorkerFailureError,
    QueueCorruptionError,
    DeadlockDetectedError,
    TaskTimeoutError,
)
```

### 4.2 `TaskQueueManager`

```python
class TaskQueueManager(BaseModule):
    """Task Queue の公開インターフェースを提供する。BaseModule(F02)を継承する。"""

    def __init__(self, config_client: ConfigurationClient) -> None: ...

    # --- BaseModule(F02) ---
    def name(self) -> str: ...
    def health_check(self) -> Result[bool]: ...

    # --- 公開インターフェース（設計書3.5、名称・シグネチャ一致） ---
    def enqueue(self, task: Task | SubTask) -> Result[TaskQueue]: ...
    def dequeue(self, queue_name: str) -> Result[TaskQueue]: ...
    def peek(self, queue_name: str) -> Result[TaskQueue]: ...
    def cancel(self, task_id: str) -> Result[bool]: ...
    def retry(self, task_id: str) -> Result[TaskQueue]: ...
    def reprioritize(self, task_id: str, priority: TaskPriority) -> Result[TaskQueue]: ...
    def list(self, queue_name: str) -> Result[list[TaskQueue]]: ...
```

公開7関数の挙動:

| 関数 | 挙動 |
|---|---|
| `enqueue(task)` | `task`から`TaskQueue`レコードを生成しキューへ投入する。`depends_on`が空でない場合は`WaitingDependency`、空であれば`Ready`とする。循環依存が検出された場合は`DeadlockDetectedError`を`Result.error`に格納して失敗を返す（キューへは投入しない） |
| `dequeue(queue_name)` | 指定キューから`Ready`状態のうち優先度最高・同一優先度ではFIFO最古のタスクを1件取り出し、`Running`へ遷移させ`worker_id`・`started_at`を設定して返す。並列実行数上限（後述4.3）に達している場合は取り出さずエラーを返す。対象がなければ`TaskNotFoundError`相当のエラーを返す |
| `peek(queue_name)` | `dequeue`と同じ選出ロジックで対象タスクを特定するが、状態変更は行わず参照のみ返す |
| `cancel(task_id)` | 対象タスクを`Cancelled`へ遷移する。既に`Completed`/`Cancelled`の場合は`Result[bool]`に`False`を格納して返す（エラーにはしない） |
| `retry(task_id)` | `Failed`または`RetryWaiting`のタスクの`retry_count`を+1し、設定上限未満なら`Queued`（依存未解消なら`WaitingDependency`）へ戻す。上限到達時は`MaxRetryExceededError`を伴い`Failed`のまま返す |
| `reprioritize(task_id, priority)` | `Running`/`Completed`/`Failed`/`Cancelled`以外の状態のタスクの`priority`を変更する。実行中・終了済みタスクへの変更は`InvalidQueueTransitionError`として拒否する |
| `list(queue_name)` | 指定キュー内の全`TaskQueue`を状態を問わず返す |

### 4.3 内部処理（非公開・設計書3.6/3.4/4.4に対応）

以下は公開APIではなく、設計書3.6（排他制御）・3.4（実行ルール）・4.4（エラー処理）を満たすための内部実装であり、新規の公開APIを追加するものではない。

```python
    def _resolve_dependencies(self, completed_task_id: str) -> None: ...
    def _has_dependency_cycle(self, task_id: str, depends_on: list[str]) -> bool: ...
    def _acquire_task_lock(self, task_id: str) -> bool: ...
    def _release_task_lock(self, task_id: str) -> None: ...
    def _select_next_ready(self, queue_name: str) -> TaskQueue | None: ...
    def _running_count(self, queue_name: str) -> int: ...
    def _detect_stale_workers(self) -> list[str]: ...
```

- `_acquire_task_lock` / `_release_task_lock`: `task_id`単位のロック（3.6「task_id単位ロック」「同一Task二重実行禁止」）。`dequeue`実行時に対象タスクのロックを取得し、`Running`遷移が完了するまで他の`dequeue`/`cancel`/`retry`呼び出しから当該`task_id`を保護する。
- `_detect_stale_workers`: Workerハートビート監視（3.6）に対応する。**設計書にはハートビート送信プロトコル自体の定義がないため**、本仕様ではdequeue時に記録した`started_at`と、Configuration経由で取得する`worker_timeout_seconds`（4.4参照）の比較により「一定時間内に完了/失敗報告のないWorker」を異常とみなす代替実装とする。この解釈は設計書に明記がない部分の実装上の補完であることを明記する。

### 4.4 並列実行制御に関する解釈

設計書5.2(F03)は「並列実行数・リトライ上限をConfiguration経由で取得する」とある一方、5.3（重厚壮大化監査）は「複数Executor同時実行」をMVP対象外としている。本仕様では両者を以下のように整理する。

- 対象：`max_parallel_executions`（Configuration Manager経由、`ConfigurationClient.get("task_queue", "max_parallel_executions")`）は、**単一プロセス内で同時に`Running`状態にできるタスク数の上限値**として扱う（`_running_count`で判定）。
- 対象外：複数のExecutorプロセス/インスタンスを分散させて同時稼働させる仕組み（水平スケーリング）はMVP対象外とし、実装しない。

---

## 5. エラー処理（`errors.py`）

Foundationのエラー階層（`FoundationError`基底、`ValidationError` / `NotFoundError` / `PermissionDeniedError` / `StateTransitionError` / `ConfigurationError` / `ExternalServiceError`）を継承し、Task Queue固有の例外を以下のとおり定義する。新しい基底例外は追加しない（Foundation側の制約4.3に準拠）。

```python
from foundation.errors import FoundationError, NotFoundError, StateTransitionError


class TaskNotFoundError(NotFoundError):
    """指定task_idがキュー内に存在しない"""


class QueueNotFoundError(NotFoundError):
    """指定queue_nameのキューが存在しない"""


class InvalidQueueTransitionError(StateTransitionError):
    """禁止されたキュー内状態遷移（例: Completed/Cancelledへのretry呼び出し）"""


class MaxRetryExceededError(FoundationError):
    """リトライ上限超過。3.4「最大リトライ回数超過でFailed」に対応"""


class WorkerFailureError(FoundationError):
    """Worker異常終了検知。4.4対応"""


class QueueCorruptionError(FoundationError):
    """キュー内部データ不整合検知。4.4対応"""


class DeadlockDetectedError(FoundationError):
    """依存関係の循環等によるデッドロック検知。4.4対応"""


class TaskTimeoutError(FoundationError):
    """実行タイムアウト検知。4.4対応"""
```

運用方針:
- 公開インターフェースの各関数は例外を送出せず、`Result[T]`の`error`フィールドに上記例外インスタンスを格納して返す（呼び出し側でのtry/except運用を強制しない設計とする）。
- `WorkerFailureError`検知時は対象タスクを`RetryWaiting`へ遷移させたうえで`Result.error`に格納する。
- `QueueCorruptionError`検知時（内部データ構造の整合性チェック失敗、例：`status`と実データの不一致）は当該タスクの自動修復を行わず、エラーとして返却し人手判断に委ねる（F00: Safety＝失敗時は安全側に倒す）。
- `DeadlockDetectedError`は`enqueue()`時点の循環依存チェックで検出する。

---

## 6. ロギング仕様

Foundationの`get_logger(module_name)`を`get_logger("task_queue")`として呼び出し、標準`logging`のみを使用する（3.7準拠）。出力フォーマットはFoundationが定める`timestamp | module_name | level | message`に従うため、Task Queue側は`message`部にキー・バリュー形式で構造化項目を含める。

出力する項目（設計書4.3に基づく）:

```text
timestamp        # Foundation側フォーマットで自動付与
task_id
event            # enqueue / dispatch(dequeue) / complete / retry / cancel / error
queue_name
from_status
to_status
priority
retry_count
worker_id
error_code       # エラー発生時のみ
```

ログ出力例（`logger.info`）:

```text
event=enqueue task_id=T-001 queue_name=default priority=HIGH status=Ready
event=dispatch task_id=T-001 queue_name=default worker_id=W-abc123 from_status=Ready to_status=Running
event=retry task_id=T-001 retry_count=2 from_status=Failed to_status=Queued
event=cancel task_id=T-001 from_status=Running to_status=Cancelled
event=error task_id=T-001 error_code=WorkerFailureError detail="worker timeout exceeded"
```

- ログレベル: 正常系（enqueue/dispatch/complete/retry/cancel）は`INFO`、`WorkerFailureError`/`QueueCorruptionError`/`DeadlockDetectedError`/`TaskTimeoutError`は`ERROR`とする。
- 機密情報（Task内容、Secret等）はログに出力しない（M00 3.7準拠、Task Queueは`task_id`等の識別子のみ扱う）。

---

## 7. Unit Testケース一覧（`tests/test_queue_manager.py`）

`unittest.TestCase`を継承した`TestTaskQueueManager`にて、設計書の「テスト観点」（FIFO確認/優先順位/並列実行/リトライ/キャンセル/依存関係/障害復旧）ごとに以下のテストメソッドを実装する。

### 基本（BaseModule）
- `test_name_returns_module_name`
- `test_health_check_returns_success_when_queue_intact`

### FIFO確認
- `test_enqueue_same_priority_dequeues_in_fifo_order`
- `test_peek_returns_same_task_without_changing_order`

### 優先順位
- `test_dequeue_returns_higher_priority_before_lower`
- `test_reprioritize_changes_dequeue_order`
- `test_reprioritize_rejects_running_task`
- `test_reprioritize_rejects_completed_task`

### 並列実行制御
- `test_dequeue_respects_max_parallel_executions_limit`
- `test_dequeue_returns_error_when_no_ready_task_available`

### リトライ
- `test_retry_increments_retry_count_and_returns_to_queued`
- `test_retry_exceeds_max_retry_count_transitions_to_failed`
- `test_retry_rejects_task_not_in_failed_or_retrywaiting_state`

### キャンセル
- `test_cancel_queued_task_transitions_to_cancelled`
- `test_cancel_running_task_transitions_to_cancelled`
- `test_cancel_already_completed_task_returns_false_without_error`

### 依存関係
- `test_enqueue_with_unresolved_dependency_sets_waiting_dependency`
- `test_dependency_completion_transitions_dependent_task_to_ready`
- `test_enqueue_rejects_circular_dependency`

### 障害復旧
- `test_worker_failure_transitions_task_to_retry_waiting`
- `test_stale_worker_detected_by_timeout_and_task_requeued`
- `test_queue_corruption_detected_returns_error_without_auto_repair`
- `test_task_timeout_transitions_to_retry_waiting`

---

## 8. MVP範囲の明記

設計書5.3（重厚壮大化監査）にて「削除済み（MVP対象外）」と判定された以下の機能は、本実装仕様の対象外とし実装しない。

| 対象外機能 | 備考 |
|---|---|
| 分散キュー | 単一プロセス内・単一インメモリストアでの実装に限定する |
| 複数Executor同時実行 | 複数Executorプロセス/インスタンスによる水平スケーリング構成は実装しない（4.4参照。プロセス内`max_parallel_executions`による同時実行数制御とは区別する） |
| 自動スケーリング | Worker数の自動増減は実装しない |
| SLAベース優先順位 | 優先順位は設計書3.3の5段階固定のみとし、SLA指標に基づく動的優先度変更は実装しない |
| コスト最適化 | コストに基づくスケジューリング・配信判断は実装しない |

上記に加え、Foundation側5.3で対象外とされた「プラグインアーキテクチャ」「動的Domain Model生成」「スキーマレジストリ」「分散トレーシング基盤」「イベントソーシング基盤」「汎用DIコンテナ」も、Task Queueが依存するFoundationの機能として利用しない前提とする。
