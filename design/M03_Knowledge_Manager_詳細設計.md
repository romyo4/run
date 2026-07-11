# M03 Knowledge Manager

> **Design Freeze 注記**: 本モジュールは旧 M03 Knowledge Manager と旧 M18 Knowledge Manager(同名・責務重複)を統合したものである。統合の経緯は `CHANGELOG.md` を参照。旧M18ファイルは本モジュールへのリダイレクトスタブとして残置する。

## 1. Overview

Knowledge Manager は、AI Development Pipeline において、プロジェクト全体で共有する知識(Knowledge)を一元管理するモジュールである。

本モジュールの目的は、Business Goal・プロジェクト方針・設計原則・コーディングルールなど、AIエージェントが継続的に参照すべき情報を統一的に管理し、各モジュールへ提供することである。

Knowledge Manager は**Knowledgeの管理および提供のみ**を担当し、要件分析・設計・実装・Workflow制御・Context生成は行わない。

### 適用対象

- Business Goal
- MVP方針
- Project Vision
- Development Rules
- Coding Rules
- Architecture Principles
- ADR(Architecture Decision Record)
- AI Instructions

### 対象外

- Context生成(Context Managerが担当)
- Configuration管理(Configuration Managerが担当)
- Workflow管理
- Repository管理
- GitHub操作
- Business判断そのもの

---

# 2. Responsibilities

## 2.1 担当

Knowledge Manager は以下を担当する。

- Knowledge読込
- Knowledge提供(取得・検索)
- Knowledge更新
- Knowledge分類
- Knowledgeバージョン管理

## 2.2 担当しない

以下は本モジュールの責務外とする。

- Context生成(Context Managerが担当。旧M03にあった「AIへのコンテキスト提供」責務はここで撤回し、Context Managerへ一本化する)
- Workflow管理
- コード生成
- Repository解析
- Business判断そのもの

---

# 3. Design

## 3.1 管理対象文書

|カテゴリ|対応する具体文書例|
|---|---|
|Business Goal|PROJECT.md, VISION.md|
|MVP Policy|ROADMAP.md, CURRENT_STATE.md|
|Architecture Principles|ARCHITECTURE.md, DECISIONS.md, ADR|
|Development Rules|CONSTRAINTS.md|
|Coding Rules|STYLE_GUIDE.md|

Knowledgeはカテゴリ単位で管理し、自由形式の長文をそのまま保持しない(構造化必須、4.3節)。

---

## 3.2 データモデル

Knowledge Manager が扱う `KnowledgeDocument` は Foundation(F01)の `Knowledge` Domain を利用する。

```text
KnowledgeDocument
-----------------
document_id
category
title
version
status
tags[]
updated_at
updated_by
content_hash
```

---

## 3.3 公開インターフェース

### load()

入力: `Knowledge Source(ファイルパス)`　出力: `Result[KnowledgeDocument]`

### get()

入力: `document_id`　出力: `Result[KnowledgeDocument]`

### get_latest()

入力: `document_id`　出力: `Result[KnowledgeDocument]`

### search()

入力: `keyword`　出力: `Result[list[KnowledgeDocument]]`

### list_documents()

入力: `category`　出力: `Result[list[KnowledgeDocument]]`

### update()

入力: `KnowledgeDocument`　出力: `Result[KnowledgeDocument]`

### create_version()

入力: `document_id, content`　出力: `Result[KnowledgeDocument]`

---

## 3.4 バージョン管理

- 全更新を履歴保存
- 最新版を既定で利用
- 必要に応じて過去版参照可能

---

## 3.5 更新権限

更新は Planner・Architect・Reviewer のみ許可する。

Executor・Context Managerなど他モジュールは参照専用(read-only)とする。

---

## 3.6 処理フロー

```text
Knowledge Files
Project Documents
Business Goal
        │
        ▼
load()
        │
        ▼
Knowledge Store
        │
        ▼
Planner
Architect
Design Auditor
Reviewer
Weekly Reviewer
Context Manager
```

Context Managerは本モジュールの`get()`/`search()`を呼び出す側であり、Knowledge Manager自身はContextを生成しない。

---

# 4. Constraints

## 4.1 Knowledgeのみ管理する

Knowledge Manager は

- Workflow実行
- Context生成
- コード生成
- Repository解析

を行ってはならない。

---

## 4.2 Business Goalを唯一の正とする

Business Goal は Knowledge Manager を唯一の管理元(Single Source of Truth)とする。

各モジュールが独自に保持してはならない。

---

## 4.3 構造化する

Knowledge は

```text
Category
Title
Content
Version
```

の形式で管理する。自由形式の長文を直接保持しない。

---

## 4.4 Repository情報を保持しない

Repository構造・Branch・Commit・Pull Requestなどは管理対象外とする。

---

## 4.5 Logging

以下を記録する。

```text
timestamp
knowledge_version
operation
category
result
```

Knowledge本文はログへ出力してはならない。

---

## 4.6 エラー処理

- 文書不存在
- バージョン競合
- 権限不足
- 整合性エラー

---

# 5. Design Audit

## 5.1 責務確認

- Knowledge管理のみ
- Knowledge提供のみ

Context生成・Workflow管理を含まない。

**判定：OK**

---

## 5.2 Foundation整合性

**F00**

- Business First
- Single Responsibility
- Documentation First

に適合。

**判定：OK**

---

**F01**

`Knowledge` Domain を利用する。

**判定：OK**

---

**F02**

Common Interface(`BaseModule`)を利用する。

**判定：OK**

---

**F03**

Business Goal・開発ルールの唯一の参照元となる。

**判定：OK**

---

## 5.3 重厚壮大化監査

以下はMVP対象外。

- Vector Database
- Semantic Search
- Knowledge Graph
- Embedding生成
- AI自動要約
- RAGパイプライン
- External Wiki連携
- 自動知識抽出
- AIによる陳腐化検知

**判定：削除済み**

---

## 5.4 実装可能性

Knowledge Manager はプロジェクト文書・Business Goal・開発ルールを読み込み、一元管理して各モジュールへ提供する単一責務のモジュールとして実装可能である。

MVPでは Markdown ファイルを知識ソースとし、シンプルなキーワード検索・取得機能のみを提供する。

**判定：実装可能**

---

# 6. Summary

Knowledge Manager は AI Development Pipeline の知識管理モジュールである。

責務は**「Business Goal・プロジェクト方針・設計原則・開発ルールを一元管理し、各モジュールへ提供すること」**に限定する。

これにより、

- Planner は事業目的を理解した計画を立てられる
- Architect は設計原則に沿った設計を行える
- Reviewer と Weekly Reviewer は Business Goal を基準に評価できる
- Context Manager は本モジュールから必要な知識を取得してContextを生成できる

プロジェクト全体で一貫した判断基準を維持しながら、シンプルなMVP構成を保つ。
