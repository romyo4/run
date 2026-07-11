# M01 State Manager

## 1. Overview

State Manager は、AI Development Pipeline 全体で共通利用するタスク状態を一元管理するモジュールである。

本モジュールの目的は、Task・SubTask・Workflow・Pull Request・Review の状態を単一の場所で管理し、全モジュールが同一の状態情報を参照できるようにすることである。

State Manager は**状態の管理のみ**を担当し、要件分析・設計・実装・レビューなどの業務処理は行わない。

### 適用対象

- Task
- SubTask
- Workflow
- Pull Request
- Review

### 対象外

- 業務ロジックの実行
- Task内容の生成
- Workflow制御(起動判断はSchedulerが担当)
- Queue管理(Task Queueが担当)

---

# 2. Responsibilities

## 2.1 担当

State Manager は以下を担当する。

- タスク状態管理
- 状態遷移の妥当性検証
- 状態変更履歴保存
- タイムスタンプ管理
- 実行中タスク管理
- 他モジュールへの状態通知

## 2.2 担当しない

以下は本モジュールの責務外とする。

- Task生成・分解(Plannerが担当)
- Queue順序管理(Task Queueが担当)
- Workflow起動判断(Schedulerが担当)
- Configuration管理(Configuration Managerが担当)

---

# 3. Design

## 3.1 状態一覧

|State|説明|
|---|---|
|Created|生成直後|
|Planning|要件整理中|
|Designing|設計中|
|DesignReview|設計監査中|
|WaitingApproval|承認待ち|
|Executing|実装中|
|Testing|テスト中|
|Reviewing|レビュー中|
|PRCreated|PR作成済み|
|Merged|マージ済み|
|Completed|完了|
|Failed|失敗|
|Cancelled|キャンセル|

---

## 3.2 状態遷移

```text
Created
  ↓
Planning
  ↓
Designing
  ↓
DesignReview
  ↓
WaitingApproval
  ↓
Executing
  ↓
Testing
  ↓
Reviewing
  ↓
PRCreated
  ↓
Merged
  ↓
Completed
```

異常時

```text
任意状態
   ↓
Failed

任意状態
   ↓
Cancelled
```

---

## 3.3 データモデル

State Manager が扱う `TaskState` は Foundation(F01)の `Task` Domain を利用する。

```text
TaskState
---------
task_id
workflow_id
current_state
previous_state
updated_at
updated_by
retry_count
error_code
error_message
metadata
```

---

## 3.4 公開インターフェース

### get_state()

入力

```text
task_id
```

出力

```text
Result[TaskState]
```

---

### transition()

入力

```text
task_id
new_state
```

出力

```text
Result[TaskState]
```

---

### history()

入力

```text
task_id
```

出力

```text
Result[list[TaskState]]
```

---

### rollback()

入力

```text
task_id
```

出力

```text
Result[TaskState]
```

---

### list_running()

入力

```text
なし
```

出力

```text
Result[list[TaskState]]
```

---

## 3.5 バリデーション

禁止例

- Completed → Executing
- Failed → Testing
- Merged → Planning

許可された状態遷移のみ実施する。

---

## 3.6 処理フロー

```text
Task Queue
Planner
Executor
Tester
Reviewer
PR Creator
      │
      ▼
State Manager
      │
      ▼
状態遷移検証
      │
      ▼
状態更新・履歴保存
      │
      ▼
全モジュールへ状態提供
```

---

# 4. Constraints

## 4.1 State Managerは業務処理をしない

State Manager は

- Task内容の生成
- 優先順位判断
- 設計判断
- コード生成

を行ってはならない。

---

## 4.2 許可された遷移のみ

State Managerが定義する遷移表にない状態変更は拒否する(F00: Safety)。

---

## 4.3 排他制御

同一 `task_id` に対する同時更新は排他制御する。

---

## 4.4 Logging

以下を記録する。

```text
timestamp
task_id
更新前
更新後
実行者
理由
```

---

## 4.5 エラー処理

- 不正遷移
- 存在しないTask
- 排他エラー
- タイムアウト

---

# 5. Design Audit

## 5.1 責務確認

- 状態管理のみ
- 業務処理を含まない

**判定：OK**

---

## 5.2 Foundation整合性

**F00**

- Single Responsibility
- Safety
- Traceability

に適合。

**判定：OK**

---

**F01**

`Task` Domain を利用する。

**判定：OK**

---

**F02**

Common Interface(`BaseModule`)を継承する。

**判定：OK**

---

**F03**

Configuration Access Pattern経由で状態保持先(DB/ファイル)の接続設定を取得する。

**判定：OK**

---

## 5.3 重厚壮大化監査

以下はMVP対象外。

- SLA監視
- 優先度管理
- 分散ワーカー対応
- イベントストリーム連携
- 分散State Store
- CQRS基盤

**判定：削除済み**

---

## 5.4 実装可能性

State Manager は状態遷移表と履歴保存のみで実装可能な単一責務のモジュールである。

全モジュールの依存基盤として、Foundationの直上に位置付けて実装できる。

**判定：実装可能**

---

# 6. Summary

State Manager は AI Development Pipeline の状態管理モジュールである。

責務は**「Task・SubTask・Workflow・Pull Request・Reviewの状態を一元管理し、正当な状態遷移のみを許可すること」**に限定する。

全モジュールの依存基盤として利用可能であり、後続モジュール(Task Queue、Plannerなど)との整合性を保つ。
