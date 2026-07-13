# Phase 3: Shadow Mode開始 — 設計書

## 背景・目的

`docs/ROADMAP_v1.1.md`の推奨着手順序では、Phase 1-B(Slack)とPhase 1-C(Codex)の間に
「Phase 3(Shadow Mode開始)」を挟むことになっていたが、実際にはPhase 1-Cを先に完了させて
しまったため、本設計はその追いつき作業である。

ロードマップが定めるPhase 3 Shadow Mode開始の成果物は次の2点である。

1. Permission Managerの`DEFAULT_PERMISSIONS`をShadow Mode用に一時的に絞ったプロファイルとして
   定義する。
2. Monitoring→Notificationの実アラート配線を確認する(障害時に人間へ通知が届くこと自体の
   動作確認)。

加えて、Shadow Modeの趣旨(「実際のPR作成は行わず、Command Router〜Reviewerまでの判断結果を
ログ・Slack通知のみで出力し、人間が結果を検証する期間を設ける」)を具体化するため、
Workflow(`run_workflow()`)のReviewer最終判断をNotification経由で人間に届ける配線も
本設計のスコープに含める。

**スコープ外(意図的に含めない)**:
- `run_workflow()`に`shadow_mode`のような分岐フラグを追加すること。PR Creatorの実書き込み
  経路(実GitHub API呼び出し)自体がまだ存在しないため、それを止めるためのフラグは時期尚早
  (YAGNI)。
- Phase 3の残り2段階(限定スコープでの本番運用、本番拡大)。これらはPhase 1-D/1-E・
  Phase 4より後にロードマップ上位置づけられており、本設計の対象外。

## セクション1: Permission Manager Shadow Modeプロファイル

### 決定事項: 案B(Pythonコード定数 + コンストラクタ引数)を採用

`PermissionManager.reload()`は`ConfigurationClient.get("permission_manager", "permissions")`の
戻り値をそのまま`tuple()`で包むのみで、JSON由来の辞書を`PermissionEntry`へ変換する処理を
持たない。一方`config/default.json`はJSONプリミティブしか保持できないため、ロードマップの
原文言(「`config/default.json`の`permission_manager.extra`領域に定義」)通りに進めると、
Design Freeze済みの`reload()`へ新たなパース処理を追加する必要がある(案A)。

本設計では、影響範囲を最小化するため**案B**を採用する。

- `src/permission_manager/default_permissions.py`に、`DEFAULT_PERMISSIONS`と同じ形式の
  `SHADOW_MODE_PERMISSIONS: tuple[PermissionEntry, ...]`定数を追加する。
  - 内容は`DEFAULT_PERMISSIONS`から`PermissionEntry(Module.EXECUTOR, Operation.PULL_REQUEST_CREATE, Effect.ALLOW)`
    を除いたもの(Shadow Mode中はExecutorのPull Request作成操作を許可しない)。
  - 「表に無い組み合わせ=Deny」という既存のフェイルセーフ方針(設計書4.3)に従い、Denyの
    エントリを明示的に追加する必要はない。
- `PermissionManager.__init__`に新しい任意引数`permissions: tuple[PermissionEntry, ...] | None = None`
  を追加する(省略時は従来通り`DEFAULT_PERMISSIONS`を使用し、既存の呼び出し元・テストへの
  影響はゼロ)。
- `reload()`の実装・既存テストには一切変更を加えない。

### `docs/ROADMAP_v1.1.md`の文言修正

Phase 3の該当する成果物の記述を、上記の実際の実装内容(Pythonコード定数 + コンストラクタ引数
経由での差し替え)に合わせて修正する。

### `bootstrap/wiring.py`の変更

`build_application()`に新しい任意引数`shadow_mode: bool = False`を追加する。

```python
permission_manager = PermissionManager(
    config_client=config,
    permissions=SHADOW_MODE_PERMISSIONS if shadow_mode else None,
)
```

他の`use_real_*`フラグとは異なり、外部サービス接続の有無ではなくPermission Managerの
権限テーブルのみを切り替える。環境変数は不要。

## セクション2: Monitoring→Notification 実アラート配線

Monitoring(M16)は設計上Read Onlyであり、Notificationへの通知送信は行わない(意図的な
責務分離)。この2つを繋ぐコードは現状どこにも存在しない。

### 通知先設定(セクション2・3共通)

`recipient`/`configuration["channel"]`の値は、セクション2(Monitoringアラート)・
セクション3(Reviewer判断結果)の両方で共通の設定値として`config/default.json`の
`notification`セクション(Configuration.extra経由)に追加する。

- `notification.default_recipient`: 通知先(Slackチャネル名またはユーザーID相当の文字列)
- `notification.default_channel`: `"slack"`固定(MVP範囲、Discordは対象外)

呼び出し元(`monitoring_smoke_test.py`・`run_workflow()`)はいずれもこの2キーを
`configuration_manager.get("notification", "default_recipient"/"default_channel")`経由で
取得し、`NotificationEvent`組み立て時にそのまま使う。

### 成果物

- `src/bootstrap/adapters.py`に、`MonitoringReport`(の`health_status.overall_healthy`)が
  不健全な場合に`NotificationEvent`(`event_type=EventType.SYSTEM_ERROR`)を組み立てる純粋関数
  `monitoring_report_to_notification_event(report: MonitoringReport, recipient: str, channel: Channel) -> NotificationEvent | None`
  を追加する(健全な場合は`None`を返し、呼び出し元は通知をスキップする)。
- `config/default.json`の`notification`セクション(Configuration.extra経由)に、
  `system_error_template`キーとしてテンプレート文字列を追加する
  (`render_message_body()`が`config_client.get("notification", event.notification_template)`
  でテンプレート文字列を取得する既存の仕組みに従う)。
- `src/bootstrap/monitoring_smoke_test.py`(新規、GitHub/Slack/Claudeスモークテストと同じ
  位置づけ): `use_real_slack=True`でアプリを構築し、意図的に不健全な`SystemStatus`を組み立てて
  Monitoringの`collect()`→`analyze()`→`report()`に通し、上記の橋渡し関数経由で
  Notification→実Slackへ送信して、実際に人間に通知が届くことを確認する手動スクリプト。
  自動テストスイートには含めない(既存の`*_smoke_test.py`群と同じ理由)。

### Unit Test

`monitoring_report_to_notification_event()`自体は純粋関数のため、フェイクの`MonitoringReport`
(健全/不健全の両方)を用いてUnit Testで検証する(実Slack接続は行わない)。

## セクション3: `run_workflow()`のReviewer判断結果をNotificationへ配信

### 変更内容

`src/bootstrap/workflow.py::run_workflow()`の末尾、`app.reviewer.publish_review(...)`が
成功した直後に、以下を追加する。

1. `ReviewOutcome`(`decision`/`next_module`)から`NotificationEvent`を組み立てる
   (`event_type=EventType.REVIEW_COMPLETED`、`event_result={"decision": outcome.decision.value, "next_module": outcome.next_module}`、
   `notification_template`は`config/default.json`の`notification`セクションに追加する
   `review_completed_template`キー、`recipient`/`configuration["channel"]`は上記
   「通知先設定(セクション2・3共通)」の`default_recipient`/`default_channel`を使う)。
2. `app.notification.create_message()` → `send()` → `publish()`を呼び出す。

### シグネチャ変更なし

`run_workflow()`の引数(`app`/`request`/`business_goal`)は変更しない。`shadow_mode`のような
分岐フラグは追加しない(スコープ外の節を参照)。通知先・テンプレートはすべて設定ファイル経由。

### 失敗時の扱い

通知の送信(`create_message`/`send`/`publish`のいずれか)が失敗しても、`run_workflow()`自体の
戻り値(`Result[ReviewOutcome]`)は変更しない(パイプライン本体の成否に影響させない)。
警告ログのみ出力する。

### Unit Test

既存の`tests/bootstrap/test_workflow.py`のフェイク`Application`に、`NotificationModule`の
フェイク実装(または既存の`tests/notification/fakes.py`を再利用)を追加し、
`run_workflow()`成功時に`create_message`/`send`/`publish`が正しい引数で呼び出されることを
検証する。また、通知が失敗してもワークフロー全体の結果は成功のまま返ることを検証する
テストケースを追加する。

## テスト方針(共通)

既存の方針(GitHub/Slack/Claude Phase)を踏襲する。

- 自動Unit Testはフェイク実装のみを用い、実ネットワーク通信は一切行わない。
- 実際の疎通確認(Monitoring→Slack通知が届くこと)は`monitoring_smoke_test.py`として、
  ユーザーが手動実行する形にする。
- 全体テストスイート(`unittest discover`)・Ruff・Blackがすべて成功することを実装完了の
  条件とする。

## 完了条件

- [ ] `SHADOW_MODE_PERMISSIONS`定数と`PermissionManager`のコンストラクタ引数追加
- [ ] `docs/ROADMAP_v1.1.md`のPhase 3該当箇所の文言修正
- [ ] `bootstrap/wiring.py`に`shadow_mode`引数追加
- [ ] `monitoring_report_to_notification_event()`実装 + Unit Test
- [ ] `config/default.json`の`notification`セクションにテンプレート2件追加
- [ ] `monitoring_smoke_test.py`新規作成
- [ ] `run_workflow()`にReviewer判断結果の通知配信を追加 + Unit Test
- [ ] 全Unit Test・Ruff・Black成功
- [ ] `docs/CHANGELOG.md`に本フェーズの記録を追加
