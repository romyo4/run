# M02 Task Queue

## 1. Overview

Task Queue は、AI開発パイプラインに投入されたタスクを安全・効率的に管理し、優先順位・依存関係・並列実行数を制御するモジュールである。

本モジュールの目的は、実行可能になったタスクをWorkerへ配信し、依存関係とリトライを管理することである。

Task Queue は**キュー管理のみ**を担当し、Taskの内容生成や状態の永続的な正本管理(State Managerが担当)は行わない。

### 適用対象

- Task
- Workflow
- Job
- Worker

### 対象外

- Task内容の生成(Plannerが担当)
- 状態の正本管理(State Managerが担当)
- Workflow起動判断(Schedulerが担当)

---

# 2. Responsibilities

## 2.1 担当

Task Queue は以下を担当する。

- タスク受付
- キュー管理
- 優先順位付け
- 並列実行制御
- 依存関係管理
- リトライ管理
- キャンセル処理

## 2.2 担当しない

以下は本モジュールの責務外とする。

- Task内容の生成
- 状態の正本管理(State Managerが担当)
- Workflow起動判断
- コード生成・レビュー

---

# 3. Design

## 3.1 キュー状態

|状態|説明|
|---|---|
|Queued|投入済|
|WaitingDependency|依存待ち|
|Ready|実行可能|
|Running|実行中|
|RetryWaiting|再試行待ち|
|Completed|完了|
|Failed|失敗|
|Cancelled|取消|

---

## 3.2 データモデル

Task Queue が扱う `TaskQueue` は Foundation(F01)の `Task` / `SubTask` Domain を利用する。

```text
TaskQueue
---------
task_id
priority
queue_name
status
depends_on[]
worker_id
retry_count
created_at
scheduled_at
started_at
finished_at
```

---

## 3.3 優先順位

1. Emergency
2. High
3. Normal
4. Low
5. Background

同一優先度ではFIFOとする。

---

## 3.4 実行ルール

- ReadyのみWorkerへ配信
- 依存タスク完了までWaitingDependency
- Worker障害時はRetryWaitingへ
- 最大リトライ回数超過でFailed

---

## 3.5 公開インターフェース

### enqueue()

入力: `task`　出力: `Result[TaskQueue]`

### dequeue()

入力: `queue_name`　出力: `Result[TaskQueue]`

### peek()

入力: `queue_name`　出力: `Result[TaskQueue]`

### cancel()

入力: `task_id`　出力: `Result[bool]`

### retry()

入力: `task_id`　出力: `Result[TaskQueue]`

### reprioritize()

入力: `task_id, priority`　出力: `Result[TaskQueue]`

### list()

入力: `queue_name`　出力: `Result[list[TaskQueue]]`

---

## 3.6 排他制御

- task_id単位ロック
- 同一Task二重実行禁止
- Workerハートビート監視

---

## 3.7 処理フロー

```text
Planner
      │
      ▼
Task Queue
      │
      ▼
優先順位付け・依存関係判定
      │
      ▼
Ready
      │
      ▼
Worker (Executor等) へ配信
      │
      ▼
State Managerへ状態通知
```

---

# 4. Constraints

## 4.1 Task Queueは内容を判断しない

Task Queue は

- Task内容の解釈
- 優先度以外の業務判断
- 設計判断

を行ってはならない。

---

## 4.2 状態の正本はState Manager

Task Queueが保持する`status`はキュー内部での実行制御用であり、正式な状態遷移の正本はState Managerとする。両者は同期する。

---

## 4.3 Logging

以下を記録する。

```text
timestamp
task_id
キュー投入
配信
完了
リトライ
キャンセル
エラー
```

---

## 4.4 エラー処理

- Worker異常終了
- キュー破損
- タイムアウト
- デッドロック検知

---

# 5. Design Audit

## 5.1 責務確認

- キュー管理のみ
- 業務処理を含まない

**判定：OK**

---

## 5.2 Foundation整合性

**F00**

- Single Responsibility
- Automation First
- Safety

に適合。

**判定：OK**

---

**F01**

`Task` / `SubTask` Domain を利用する。

**判定：OK**

---

**F02**

Common Interface(`BaseModule`)を継承する。

**判定：OK**

---

**F03**

Configuration Access Pattern経由で並列実行数・リトライ上限を取得する。

**判定：OK**

---

## 5.3 重厚壮大化監査

以下はMVP対象外。

- 分散キュー
- 複数Executor同時実行
- 自動スケーリング
- SLAベース優先順位
- コスト最適化

**判定：削除済み**

---

## 5.4 実装可能性

Task Queue は優先順位付き単一キューとリトライ管理のみで実装可能な単一責務のモジュールである。

State Managerとの責務分離が明確であり、Planner/Executor双方から利用可能である。

**判定：実装可能**

---

# 6. Summary

Task Queue は AI Development Pipeline のキュー管理モジュールである。

責務は**「投入されたタスクの優先順位付け・依存関係管理・並列実行制御を行い、実行可能なタスクをWorkerへ配信すること」**に限定する。

State Managerとの責務分離を維持し、キュー責務に限定することで単一責務を保つ。
