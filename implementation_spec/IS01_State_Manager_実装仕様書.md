# IS01 State Manager 実装仕様書

本書は `M01_State_Manager_詳細設計.md`(Design Freeze v1.0 確定版)を唯一の正とし、実装のための具体仕様に落とし込むものである。設計書に記載のない機能は追加しない。Foundation(M00)が提供する `Result[T]` / `BaseModule` / エラー階層 / `get_logger()` / `ConfigurationClient` を前提として利用する。

---

## 1. モジュール概要

State Manager は、AI Development Pipeline 全体で共通利用する Task・SubTask・Workflow・Pull Request・Review の状態を一元管理するモジュールである。責務は「状態遷移の妥当性検証」「状態変更履歴の保存」「実行中タスクの管理」「他モジュールへの状態提供」に限定され、要件分析・設計・実装・レビューといった業務処理そのものは一切行わない。設計書で定義された13状態(Created〜Cancelled)の直線的な正常遷移と、任意状態からFailed/Cancelledへの異常遷移のみを許可し、遷移表にない状態変更は拒否する(F00: Safety)。同一 `task_id` への同時更新は排他制御し、全ての状態変更はタイムスタンプ付きで履歴保存される。

---

## 2. ファイル構成

```text
src/state_manager/
├── __init__.py       # 公開APIの再エクスポート(StateManager, TaskState, TaskStateEnum)
├── models.py         # TaskStateEnum, TaskState dataclass の定義
├── transitions.py    # 許可遷移表(ALLOWED_TRANSITIONS)と validate_transition() の定義
├── exceptions.py     # State Manager固有例外(Foundationのエラー階層を継承)
├── store.py          # 状態の保持・履歴保存・排他制御(ロック管理)を担当するストア
├── manager.py         # StateManager(BaseModule) 本体。公開インターフェース5関数を実装
└── tests/
    └── test_state_manager.py   # unittest によるテストケース一式
```

役割の要約:

| ファイル | 役割 |
|---|---|
| `models.py` | 設計書3.1(状態一覧)・3.3(データモデル)に対応するデータ構造の定義のみを行う |
| `transitions.py` | 設計書3.2(状態遷移)・3.5(バリデーション)に対応する遷移表と検証ロジック |
| `exceptions.py` | 設計書4.5(エラー処理)のうち、Foundationのエラー階層に存在しない「排他エラー」「タイムアウト」を表す例外を追加定義 |
| `store.py` | 設計書4.3(排他制御)・2.1(状態変更履歴保存・実行中タスク管理)の実データ保持層。F03経由で永続化先設定を取得する |
| `manager.py` | 設計書3.4(公開インターフェース)を実装する本体クラス。`BaseModule`を継承する(F02) |

---

## 3. データクラス定義

### 3.1 TaskStateEnum

設計書3.1の状態一覧をそのままEnum化する。順序・名称の追加/削除は行わない。

```python
from enum import Enum


class TaskStateEnum(str, Enum):
    """タスク状態(設計書3.1に定義された13状態)。"""

    CREATED = "Created"
    PLANNING = "Planning"
    DESIGNING = "Designing"
    DESIGN_REVIEW = "DesignReview"
    WAITING_APPROVAL = "WaitingApproval"
    EXECUTING = "Executing"
    TESTING = "Testing"
    REVIEWING = "Reviewing"
    PR_CREATED = "PRCreated"
    MERGED = "Merged"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


# 終端状態(これ以上の遷移を許可しない)
TERMINAL_STATES: frozenset[TaskStateEnum] = frozenset(
    {TaskStateEnum.COMPLETED, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}
)
```

### 3.2 TaskState

設計書3.3のデータモデルをそのままフィールド化する。`task_id` はFoundation(F01) `Task` Domain の `id` を参照する値であり、State ManagerはTask自体の生成・内容管理は行わない(Foundationの`Task`をそのまま再定義しない)。

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TaskState:
    """State Managerが管理する状態レコード(設計書3.3)。

    task_id は Foundation(F01) Task Domain の id と対応する。
    """

    task_id: str
    workflow_id: str | None
    current_state: TaskStateEnum
    previous_state: TaskStateEnum | None
    updated_at: datetime
    updated_by: str
    retry_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

フィールドの追加・削除は行わない(設計書3.3に忠実)。バリデーションは Foundation の `validation.py`(`require_not_none` 等)を利用する。

---

## 4. クラス・関数シグネチャ

### 4.1 許可遷移表と検証ロジック(transitions.py)

設計書3.2(正常遷移)・3.5(禁止例: Completed→Executing, Failed→Testing, Merged→Planning)に基づく遷移表。正常遷移の直線経路のみを許可し、任意の非終端状態からFailed/Cancelledへの遷移を許可する。Completed/Failed/Cancelledは終端状態とし、そこからの遷移は一切許可しない(禁止例3件はいずれもこの終端状態ルールで拒否される)。

```python
from foundation.result import Result

ALLOWED_TRANSITIONS: dict[TaskStateEnum, frozenset[TaskStateEnum]] = {
    TaskStateEnum.CREATED: frozenset({TaskStateEnum.PLANNING, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.PLANNING: frozenset({TaskStateEnum.DESIGNING, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.DESIGNING: frozenset({TaskStateEnum.DESIGN_REVIEW, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.DESIGN_REVIEW: frozenset({TaskStateEnum.WAITING_APPROVAL, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.WAITING_APPROVAL: frozenset({TaskStateEnum.EXECUTING, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.EXECUTING: frozenset({TaskStateEnum.TESTING, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.TESTING: frozenset({TaskStateEnum.REVIEWING, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.REVIEWING: frozenset({TaskStateEnum.PR_CREATED, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.PR_CREATED: frozenset({TaskStateEnum.MERGED, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.MERGED: frozenset({TaskStateEnum.COMPLETED, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.COMPLETED: frozenset(),
    TaskStateEnum.FAILED: frozenset(),
    TaskStateEnum.CANCELLED: frozenset(),
}


def validate_transition(current: TaskStateEnum, new_state: TaskStateEnum) -> Result[bool]:
    """current から new_state への遷移が許可されているか検証する。

    許可されている場合 Result(success=True, value=True) を返す。
    許可されていない場合 Result(success=False, value=False, error=StateTransitionError(...)) を返す。
    """
    ...
```

### 4.2 公開インターフェース(manager.py)

設計書3.4の5関数の名称・入出力を厳守する。`transition()` の必須入力は設計書3.4の通り `task_id` / `new_state` のみである。ただし設計書4.4は全ての状態変更ログに「実行者」「理由」を記録することを要求しており、この情報はメソッドの外部から与えられる必要がある。この矛盾を、`updated_by` / `reason` をキーワード専用の**任意引数**(デフォルト値あり)として追加することで解消する。これは新規APIの追加ではなく、設計書3.4が定めた必須入力(`task_id`, `new_state`)とシグネチャの型(`Result[TaskState]`戻り値)を変えずに、設計書4.4のログ要件を満たすための最小限の拡張である。

```python
from foundation.base_module import BaseModule
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from foundation.types import Task  # F01: Task Domain(参照のみ、再定義しない)


class StateManager(BaseModule):
    """タスク状態を一元管理するモジュール(設計書全体)。"""

    def __init__(self, config_client: ConfigurationClient) -> None: ...

    # --- F02: BaseModule ---
    def name(self) -> str: ...

    def health_check(self) -> Result[bool]: ...

    # --- 設計書3.4: 公開インターフェース ---
    def get_state(self, task_id: str) -> Result[TaskState]: ...

    def transition(
        self,
        task_id: str,
        new_state: TaskStateEnum,
        *,
        updated_by: str = "system",
        reason: str | None = None,
    ) -> Result[TaskState]: ...

    def history(self, task_id: str) -> Result[list[TaskState]]: ...

    def rollback(self, task_id: str) -> Result[TaskState]: ...

    def list_running(self) -> Result[list[TaskState]]: ...
```

各関数の仕様:

- **`get_state(task_id)`**: `task_id` に対応する最新の `TaskState` を返す。存在しない場合は `NotFoundError`。
- **`transition(task_id, new_state, ...)`**: `validate_transition()` で遷移可否を検証した上で状態を更新し、履歴に追記する。不正遷移は `StateTransitionError`。更新中は `store.py` の排他ロックを介する。
- **`history(task_id)`**: `task_id` に対応する状態変更履歴を時系列(古い→新しい)で返す。
- **`rollback(task_id)`**: 現在の `TaskState.previous_state` へ状態を戻す。`previous_state` が存在しない(履歴がCreatedのみ等)場合は `StateTransitionError`。rollbackも履歴に追記される(通常の禁止遷移検証はバイパスするが、対象が存在しない場合の`NotFoundError`は同様に発生しうる)。
- **`list_running()`**: `TERMINAL_STATES`(Completed/Failed/Cancelled)以外の状態にある全 `TaskState` を返す。入力なし。

### 4.3 ストア層(store.py)

排他制御(設計書4.3)と履歴保存(設計書2.1)を担当する。永続化先の接続設定はF03経由で取得する。

```python
from foundation.interfaces import ConfigurationClient
from foundation.result import Result


class StateStore:
    """TaskStateの保持・履歴保存・排他制御を担当する。"""

    def __init__(self, config_client: ConfigurationClient) -> None:
        # ConfigurationClient.get("state_manager", "backend_path") 等で
        # 永続化先(DB/ファイル)の接続設定を取得する(F03)。
        ...

    def get_latest(self, task_id: str) -> Result[TaskState]: ...

    def get_history(self, task_id: str) -> Result[list[TaskState]]: ...

    def append(self, state: TaskState) -> Result[TaskState]: ...

    def list_running(self, terminal_states: frozenset[TaskStateEnum]) -> Result[list[TaskState]]: ...

    def acquire_lock(self, task_id: str, timeout_seconds: float) -> Result[bool]:
        """task_id単位の排他ロックを取得する。取得できない場合はStateLockTimeoutError。"""
        ...

    def release_lock(self, task_id: str) -> None: ...
```

排他制御は `task_id` ごとに `threading.Lock` を割り当てる方式とし、ロック辞書自体へのアクセスは別途1本のロックで保護する(MVP範囲。分散ロックは対象外、8節参照)。

---

## 5. エラー処理

Foundation(M00 3.6)のエラー階層を継承して利用する。

```text
FoundationError (Foundation定義の基底)
├── NotFoundError        … get_state/history/rollback/transitionで指定task_idが存在しない場合
├── StateTransitionError … validate_transition()が拒否した不正遷移(禁止遷移・存在しない状態指定)
├── ValidationError       … 入力値(task_id空文字等)の検証エラー(Foundationのvalidation.pyのrequire_*系から送出)
└── ConfigurationError    … F03経由の永続化先設定取得に失敗した場合
```

設計書4.5が挙げる「排他エラー」「タイムアウト」はFoundationのエラー階層に該当するものが存在しないため、`exceptions.py` にて `FoundationError` を継承したState Manager固有例外を追加する(Foundation3.6「各モジュールは必要に応じてこれらを継承し、モジュール固有の例外を定義できる」に従う)。

```python
from foundation.errors import FoundationError


class StateLockError(FoundationError):
    """同一task_idに対する同時更新が競合した場合に送出する。"""


class StateLockTimeoutError(StateLockError):
    """排他ロック取得がタイムアウトした場合に送出する。"""
```

すべての公開インターフェース(`get_state`/`transition`/`history`/`rollback`/`list_running`)は、内部で例外を捕捉し `Result[T](success=False, value=None, error=<該当例外インスタンス>)` として返す。例外を呼び出し元に直接送出しない(F02: `Result[T]`パターン)。

---

## 6. ロギング仕様

`foundation.logger.get_logger("state_manager")` で取得したLoggerを`manager.py`のモジュールレベルで1つ生成し、インスタンス間で共有する。

```python
from foundation.logger import get_logger

logger = get_logger("state_manager")
```

設計書4.4に定めるログ項目を、状態変更が発生する都度(`transition()` / `rollback()` 実行時)構造化して出力する。出力形式はFoundation3.7の規約(`timestamp | module_name | level | message`)に従い、message部に以下の項目をkey=value形式で含める。

```text
timestamp    : 変更発生時刻(TaskState.updated_at)
task_id      : 対象タスクID
before       : 更新前の状態(previous_state)
after        : 更新後の状態(current_state)
updated_by   : 実行者
reason       : 理由(未指定時はNone)
```

失敗時(不正遷移・NotFound・ロックタイムアウト等)は同項目に加えてエラー種別・メッセージを`logger.warning`または`logger.error`で出力する。Secret・Token等の機密情報はTaskStateに含まれない想定のため、`metadata`フィールドをログにそのまま出力する場合は内容に留意する(Foundation3.7)。

---

## 7. Unit Testケース一覧

`tests/test_state_manager.py` に `unittest.TestCase` を用いて実装する。設計書の「テスト観点」(全状態遷移/不正遷移拒否/並列更新/ロールバック/履歴保存)に対応する。

### 7.1 全状態遷移(正常系)

- `test_transition_created_to_planning_succeeds`
- `test_transition_planning_to_designing_succeeds`
- `test_transition_designing_to_design_review_succeeds`
- `test_transition_design_review_to_waiting_approval_succeeds`
- `test_transition_waiting_approval_to_executing_succeeds`
- `test_transition_executing_to_testing_succeeds`
- `test_transition_testing_to_reviewing_succeeds`
- `test_transition_reviewing_to_pr_created_succeeds`
- `test_transition_pr_created_to_merged_succeeds`
- `test_transition_merged_to_completed_succeeds`
- `test_transition_any_non_terminal_state_to_failed_succeeds`
- `test_transition_any_non_terminal_state_to_cancelled_succeeds`

### 7.2 不正遷移拒否

- `test_transition_completed_to_executing_rejected`
- `test_transition_failed_to_testing_rejected`
- `test_transition_merged_to_planning_rejected`
- `test_transition_from_completed_to_any_state_rejected`
- `test_transition_from_failed_to_any_state_rejected`
- `test_transition_from_cancelled_to_any_state_rejected`
- `test_transition_skipping_intermediate_state_rejected`
- `test_transition_unknown_task_id_returns_not_found_error`
- `test_transition_returns_state_transition_error_on_invalid_move`

### 7.3 並列更新(排他制御)

- `test_concurrent_transition_same_task_id_is_serialized`
- `test_concurrent_transition_different_task_ids_do_not_block_each_other`
- `test_transition_raises_lock_timeout_when_lock_held_too_long`

### 7.4 ロールバック

- `test_rollback_reverts_to_previous_state`
- `test_rollback_without_previous_state_returns_error`
- `test_rollback_unknown_task_id_returns_not_found_error`
- `test_rollback_is_recorded_in_history`

### 7.5 履歴保存

- `test_history_returns_all_recorded_states_in_chronological_order`
- `test_history_unknown_task_id_returns_not_found_error`
- `test_history_reflects_multiple_transitions`

### 7.6 その他公開インターフェース

- `test_get_state_returns_latest_state`
- `test_get_state_unknown_task_id_returns_not_found_error`
- `test_list_running_excludes_terminal_states`
- `test_list_running_returns_empty_list_when_no_tasks`
- `test_health_check_returns_success`

---

## 8. MVP範囲の明記

設計書5.3節(重厚壮大化監査)にて対象外・削除済みとされた以下の機能は、本実装仕様に含めない。

- SLA監視
- 優先度管理
- 分散ワーカー対応
- イベントストリーム連携
- 分散State Store
- CQRS基盤

また、設計書2.2(担当しない)に基づき、以下も本モジュールの実装範囲外とする。

- Task生成・分解(Plannerが担当)
- Queue順序管理(Task Queueが担当)
- Workflow起動判断(Schedulerが担当)
- Configuration値の実体管理(Configuration Managerが担当。本モジュールはF03経由での取得のみ行う)

排他制御は単一プロセス内の `threading.Lock` によるMVP実装とし、複数プロセス・複数ホストにまたがる分散ロックは実装しない(上記「分散ワーカー対応」対象外に含まれる)。
