# IS06 Planner 実装仕様書

参照設計書: `M06 Planner.txt`（確定版）, `M00 Foundation.txt`（F00〜F03定義元）
対象バージョン: Design Freeze v1.0
実装言語: Python 3.13

---

## 0. 前提・マッピング方針（設計書の解釈メモ）

設計書 M06 は Domain の具体的な属性までは規定していないため、本仕様書では Foundation F01 の Domain Model 一覧（`M00 Foundation.txt` 3.3節）に基づき、以下のマッピングを採用する。この対応関係は本仕様書のみの実装上の解釈であり、設計書に新しい機能を追加するものではない。

| 設計書上の概念 | 実装上の型 | 根拠 |
|---|---|---|
| `analyze()` の入力（Normalized Request） | `NormalizedRequest`（Planner固有dataclass） | M06 3.1 の入力項目（workflow_id, command, normalized_request, knowledge, project_context）を一つの入力構造として集約 |
| `analyze()` の出力（Requirement） | `Requirement`（Foundationの`Task` Domainを内包） | F01: `Task`=「要求単位のタスク」、利用モジュールに Planner が明記 |
| `create_tasks()` / `prioritize()` の出力（Task List / Prioritized Tasks） | `list[PlannerSubTask]`（Foundationの`SubTask` Domainを内包） | F01: `SubTask`=「Taskの分解単位」、利用モジュールに Planner が明記 |
| `create_execution_plan()` の出力（Execution Plan） | `ExecutionPlan`（Planner固有dataclass） | F01 Domain一覧に `ExecutionPlan` は存在しないため、Planner固有の成果物として定義。ただし共通属性（id/created_at/updated_at/metadata）の命名規約はF01に合わせる |

設計書 3.5 の Execution Plan 属性「Priority」は、Task単位で付与される値（3.4節）であるため、`ExecutionPlan` トップレベルには重複フィールドを設けず、`task_list` 内の各 `PlannerSubTask.priority` として表現する。同様に「Plan ID」はFoundation共通属性の `id` としてそのまま実装する。

---

## 1. モジュール概要

Planner は、ユーザーから受け取った自然言語の要求（Normalized Request）を分析し、実行可能な Execution Plan へ変換するモジュールである。要求分析（目的・背景・制約・成果物・優先度の抽出）、Task分解、優先順位付け、Execution Plan生成の4処理に責務を限定し、システム設計・コード生成・Pull Request作成・レビューは一切行わない。Knowledgeは参照のみ許可され、書き換えは禁止される。生成された Execution Plan は後続の Designer モジュールへ引き渡される。

---

## 2. ファイル構成

```
src/planner/
├── __init__.py       # 公開シンボルのエクスポート（Planner, 各dataclass, Priority）
├── types.py          # Planner固有のdataclass定義（NormalizedRequest, Requirement,
│                      # PlannerSubTask, ExecutionPlan, Priority Enum）
├── planner.py         # Planner クラス本体（BaseModule実装、公開インターフェース4関数）
└── tests/
    ├── __init__.py
    └── test_planner.py  # Unit Test（unittest）
```

役割:

- `types.py`: Foundationの`Task`/`SubTask`/`Knowledge`/`Context`型を利用してPlanner固有の成果物データ構造を定義する。業務ロジックは含まない。
- `planner.py`: `BaseModule`を継承した`Planner`クラスを定義し、`analyze()` / `create_tasks()` / `prioritize()` / `create_execution_plan()` を実装する。要求分析・分解・優先順位付け・Plan生成のロジック本体を持つ。
- `tests/test_planner.py`: 公開インターフェースと制約（設計不可・実装不可・レビュー不可・Knowledge非改変・ログ出力）の単体テスト。

Foundation側のファイル（`foundation/*`）は変更しない。他モジュールのディレクトリ・ファイルにも変更を加えない。

---

## 3. データクラス定義

```python
# src/planner/types.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from foundation.types import Task, SubTask, Knowledge, Context


class Priority(str, Enum):
    """M06 3.4節: Taskごとに付与する優先度。"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class NormalizedRequest:
    """analyze() の入力。M06 3.1節の入力項目を集約したもの。"""
    workflow_id: str
    command: str
    request_text: str
    knowledge: list[Knowledge] = field(default_factory=list)
    project_context: Context | None = None


@dataclass
class Requirement:
    """analyze() の出力。M06 3.2節で抽出される5項目を保持する。

    task: Foundationの Task Domain（id/created_at/updated_at/metadataを提供）。
          Planner固有属性は本クラスのフィールドとして追加する（F01の規約に準拠）。
    """
    task: Task
    objective: str          # 目的
    background: str         # 背景
    constraints: list[str]  # 制約
    deliverable: str        # 成果物
    priority: Priority      # 優先度


@dataclass
class PlannerSubTask:
    """create_tasks() / prioritize() が扱うTask Listの1要素。
    M06 3.3節（Task分解）・3.4節（優先順位）に対応する。

    subtask: FoundationのSubTask Domain（id/created_at/updated_at/metadataを提供）。
    """
    subtask: SubTask
    order: int                       # Task1, Task2... の並び順
    title: str                       # 例: "現状分析"
    description: str
    depends_on: list[str] = field(default_factory=list)  # 依存するSubTask.id一覧
    priority: Priority | None = None  # create_tasks()時点ではNone。prioritize()で確定する。


@dataclass
class ExecutionPlan:
    """create_execution_plan() の出力。M06 3.5節の成果物。

    id/created_at/updated_at/metadata はF01共通属性の命名規約に準拠する
    （Foundation Domain一覧には存在しない、Planner固有の成果物）。
    id が設計書上の「Plan ID」に相当する。
    """
    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    objective: str
    task_list: list[PlannerSubTask]
    dependencies: dict[str, list[str]]  # SubTask.id -> 依存するSubTask.id一覧（集約ビュー）
    expected_output: str
```

補足:
- `Requirement.task` / `PlannerSubTask.subtask` は Foundation Domain のインスタンスを直接保持するコンポジション方式を採る（dataclass継承によるフィールド順序制約を避けるため）。
- `metadata` に Secret・Token・Credential・Knowledge本文を格納しない（4.5節ログ制約と同じ理由による運用ルール）。

---

## 4. クラス・関数シグネチャ

```python
# src/planner/planner.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from foundation.base_module import BaseModule
from foundation.errors import FoundationError, ValidationError
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result
from foundation.types import Task, SubTask
from foundation.validation import require_not_none, require_non_empty

from planner.types import (
    ExecutionPlan,
    NormalizedRequest,
    PlannerSubTask,
    Priority,
    Requirement,
)

MODULE_NAME = "planner"


class Planner(BaseModule):
    """M06 Planner の公開インターフェース実装。
    設計・実装・レビューは行わない（M06 4章の制約）。
    """

    def __init__(self, config_client: ConfigurationClient) -> None: ...

    # --- F02 Common Interface ---
    def name(self) -> str: ...

    def health_check(self) -> Result[bool]: ...

    # --- M06 3.6 公開インターフェース ---
    def analyze(self, normalized_request: NormalizedRequest) -> Result[Requirement]: ...

    def create_tasks(self, requirement: Requirement) -> Result[list[PlannerSubTask]]: ...

    def prioritize(
        self, task_list: list[PlannerSubTask]
    ) -> Result[list[PlannerSubTask]]: ...

    def create_execution_plan(
        self, prioritized_tasks: list[PlannerSubTask]
    ) -> Result[ExecutionPlan]: ...
```

各メソッドの入出力対応（設計書3.6節どおり、名称・シグネチャを一致させる）:

| メソッド | 入力 | 出力（`Result[T]`のT） |
|---|---|---|
| `analyze` | `NormalizedRequest` | `Requirement` |
| `create_tasks` | `Requirement` | `list[PlannerSubTask]`（Task List） |
| `prioritize` | `list[PlannerSubTask]`（Task List） | `list[PlannerSubTask]`（Prioritized Tasks） |
| `create_execution_plan` | `list[PlannerSubTask]`（Prioritized Tasks） | `ExecutionPlan` |

- 戻り値はF02規約に従い、すべて `Result[T]` でラップする。失敗時は `Result(success=False, value=None, error=<FoundationError系>)` を返す。
- `create_tasks()` / `prioritize()` / `create_execution_plan()` は前段の出力を次段の入力にそのまま渡せる形（`list[PlannerSubTask]`）を維持し、3.7節の処理フロー（Command Router → Requirement Analysis → Task Decomposition → Priority Assignment → Execution Plan → Designer）どおりに呼び出せることを前提とする。
- Command Router からの呼び出し順序（4メソッドの直列実行）自体は M06 3.6節に定義された公開インターフェースの範囲外のため、本仕様書では新規の集約APIを追加しない。呼び出し順序の制御は呼び出し元（Command Router）または内部プライベートヘルパー（非公開）に委ねる。

---

## 5. エラー処理

Foundationのエラー階層（`foundation.errors`）をそのまま利用し、Planner独自の例外クラスは追加しない（MVP First / Simplicity）。

| 状況 | 使用する例外/エラー | 発生箇所 |
|---|---|---|
| `NormalizedRequest.request_text` が空・None | `ValidationError` | `analyze()` 冒頭、`require_non_empty()` 使用 |
| `workflow_id` が未指定 | `ValidationError` | `analyze()` 冒頭、`require_not_none()` 使用 |
| `Requirement` が不正（objective欠如等） | `ValidationError` | `create_tasks()` 冒頭 |
| Task Listが空 | `ValidationError` | `prioritize()` / `create_execution_plan()` 冒頭 |
| `Priority` に許容外の値 | `ValidationError`（`require_in()` 使用） | `prioritize()` |
| Configuration取得失敗（`ConfigurationClient.get()` がエラーを返す） | `ConfigurationError` | `__init__()` / 各メソッド内でのconfig参照時 |

処理方針:
- すべての例外は `Result[T]` の `error` フィールドに格納して返却し、メソッドの外へ生の例外として送出しない（呼び出し元への統一されたエラーインターフェース維持）。
- Foundation側から渡された `FoundationError` はそのまま `Result.error` にラップして返す（変換・握りつぶしをしない）。
- Knowledgeの書き換え禁止（M06 4.4節）はコード上、`NormalizedRequest.knowledge` を読み取り専用として扱い、Plannerは一切のミューテーションを行わないことで担保する（専用の例外クラスは設けない。Design Auditのレベルでの制約）。

---

## 6. ロギング仕様

`foundation.logger.get_logger(MODULE_NAME)` を用いて `Logger` を取得し、モジュール内で使い回す（インスタンス生成のたびに再取得しない）。

出力形式はFoundation規約（`timestamp | module_name | level | message`）に従う。M06 4.5節で定義されたログ項目（`timestamp`, `workflow_id`, `objective`, `task_count`, `execution_plan_id`, `result`）は、`message` 部分に構造化して埋め込む。

```python
logger = get_logger(MODULE_NAME)

# create_execution_plan() 成功時
logger.info(
    "execution_plan_created workflow_id=%s objective=%s task_count=%d "
    "execution_plan_id=%s result=%s",
    workflow_id, objective, task_count, execution_plan_id, "success",
)

# 失敗時（例: バリデーションエラー）
logger.error(
    "execution_plan_failed workflow_id=%s objective=%s task_count=%d "
    "execution_plan_id=%s result=%s",
    workflow_id, objective, task_count, "N/A", "failure",
)
```

- Secret・Token・Credential・Knowledge本文はログに出力しない（M06 4.5節）。`NormalizedRequest.knowledge` の内容はログに含めない。
- `analyze()` / `create_tasks()` / `prioritize()` の各段階でも、処理開始・終了を `logger.debug()` レベルで記録してよいが、必須項目は `create_execution_plan()` 完了時点の1行に集約する（Planner全体としての結果ログ、4.5節の主旨）。

---

## 7. Unit Testケース一覧（unittest, `tests/test_planner.py`）

`unittest.TestCase` を継承したテストクラス `PlannerTests` に以下のテストメソッドを定義する。

### 7.1 公開インターフェース（正常系）
- `test_analyze_returns_success_result_with_requirement`
- `test_analyze_extracts_objective_background_constraints_deliverable_priority`
- `test_create_tasks_returns_success_result_with_task_list`
- `test_create_tasks_preserves_task_order`
- `test_prioritize_assigns_priority_to_every_task`
- `test_prioritize_orders_tasks_considering_dependencies`
- `test_create_execution_plan_returns_success_result_with_execution_plan`
- `test_create_execution_plan_maps_plan_id_to_common_id_attribute`
- `test_create_execution_plan_embeds_priority_in_task_list_not_top_level`

### 7.2 公開インターフェース（異常系）
- `test_analyze_returns_failure_result_when_request_text_is_empty`
- `test_analyze_returns_failure_result_when_workflow_id_is_missing`
- `test_create_tasks_returns_failure_result_when_requirement_is_invalid`
- `test_prioritize_returns_failure_result_when_task_list_is_empty`
- `test_create_execution_plan_returns_failure_result_when_prioritized_tasks_is_empty`

### 7.3 F02 Common Interface
- `test_name_returns_module_name`
- `test_health_check_returns_success_result`

### 7.4 制約（M06 4章）に対応するテスト
- `test_planner_does_not_mutate_input_knowledge`（4.4: Knowledge書き換え禁止）
- `test_planner_has_no_design_related_public_method`（4.1: クラス/API/DB設計を行わない — 公開メソッドが3.6節の4関数+F02の2関数のみであることを確認）
- `test_planner_has_no_implementation_related_public_method`（4.2: コード生成・GitHub操作・PR作成を行わない）
- `test_execution_plan_does_not_contain_review_decision_field`（4.3: 採否判断を含まない）

### 7.5 ロギング（M06 4.5節）
- `test_create_execution_plan_logs_required_fields_on_success`
- `test_create_execution_plan_logs_result_failure_without_secrets_on_error`
- `test_logging_never_includes_knowledge_body`

---

## 8. MVP範囲の明記

設計書 M06 5.3節（重厚壮大化監査）にて対象外・削除済みとされた以下の機能は、本実装仕様書および実装対象に一切含めない。

- AI Project Manager
- 長期ロードマップ生成
- 自動スケジューリング最適化
- コスト見積りAI
- リソース配分AI
- ガントチャート生成
- マルチプロジェクト最適化

また、M06 2.2節・4章に基づき、以下もPlannerの実装範囲外とする。

- システム設計・モジュール設計・クラス設計・API設計・DB設計
- コード生成・Pull Request作成・GitHub操作
- レビュー（改善案の採否判断）
- Workflow実行制御
- Knowledgeの書き換え（参照のみ許可）

本仕様書で定義した公開インターフェースは `analyze()` / `create_tasks()` / `prioritize()` / `create_execution_plan()` と、F02由来の `name()` / `health_check()` の6メソッドに限定する。これ以外の公開APIを実装に追加してはならない。
