# IS15 Notification 実装仕様書

- 対象設計書: `M15 Notification.txt`(確定版)
- 前提基盤: `M00 Foundation.txt`(F00原則カタログ / F01共通Domain Model / F02共通Interface / F03設定取得パターン)
- 対象パッケージ: `src/notification/`
- 言語/規約: Python 3.13、型ヒント必須、dataclass、pathlib、標準`logging`(`get_logger()`経由)、`unittest`、UTF-8、Ruff/Black準拠

---

## 1. モジュール概要

Notification は、AI Development Pipeline の各モジュールが発行する Workflow イベント(開始・完了・失敗・PR作成・レビュー結果・Weekly Review完了・システムエラー)を受け取り、Configuration管理下のテンプレートを用いて通知メッセージを生成し、Slack・Discord・Email の各チャネルへ配信し、その結果を通知履歴として記録する単一責務モジュールである。Notification は通知の**生成・チャネル選択・配信結果の記録**までを担当し、要件分析・設計・実装・レビュー・Workflow制御・Pull Request作成は一切行わない。また、Slack/Discordへの実際のAPI通信は M21 Slack/Discord Connector が担う責務であり、Notification はメッセージと送信先を渡して配信を委譲する側に徹する(詳細は8章参照)。

---

## 2. ファイル構成

```text
src/notification/
├── __init__.py          # パッケージ公開API(NotificationModule等の再エクスポート)
├── constants.py          # MODULE_NAME, MAX_RETRY_COUNT(=3), SUPPORTED_CHANNELS 等の定数
├── types.py              # 本モジュールのdataclass定義(3.データクラス定義 参照)
├── errors.py              # Foundationエラー階層を継承したNotification固有例外
├── channels.py            # ChannelConnectorインターフェース定義 + チャネル選択ロジック
├── templates.py           # Configuration経由のテンプレート取得・レンダリング(4.4対応)
├── history.py             # NotificationHistoryStore(通知履歴の記録、MVPはインメモリ)
├── service.py             # NotificationModule(BaseModule) 本体。create_message/send/publish実装
└── tests/
    ├── __init__.py
    ├── test_types.py
    ├── test_templates.py
    ├── test_channels.py
    ├── test_history.py
    └── test_service.py
```

| ファイル | 役割 |
|---|---|
| `constants.py` | モジュール名・最大再送回数(4.3=3回)・MVP対応チャネル一覧などの固定値を集約し、コード中への直書きを避ける |
| `types.py` | 3.1入力・3.5成果物に対応するdataclass、および`EventType`/`Channel`/`DeliveryStatus`のEnum定義 |
| `errors.py` | Foundationの`FoundationError`系を継承したNotification固有の例外クラス |
| `channels.py` | 実配信を担う外部Connector(M21等)を抽象化した`ChannelConnector`インターフェースと、Event/Configurationからチャネルを決定する`select_channel()` |
| `templates.py` | `ConfigurationClient`(F03)経由でテンプレート文字列を取得し、Eventの値で埋め込みレンダリングする |
| `history.py` | `publish()`が生成した`NotificationHistory`を記録するストア(MVP: インメモリ一覧。永続化は本モジュールの責務外) |
| `service.py` | `BaseModule`(F02)を継承した`NotificationModule`。公開インターフェース3メソッドを実装するオーケストレーション層 |

---

## 3. データクラス定義

Foundationの `foundation.types.Notification`(F01 Domain Model、共通属性 `id` / `created_at` / `updated_at` / `metadata` を持つ)を継承・利用する。`Event`・`Delivery Result` はFoundation共通Domainに存在しないため、本モジュール固有のdataclassとして`types.py`に定義する。

```python
# src/notification/types.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from foundation.types import Notification as NotificationDomain


class EventType(str, Enum):
    """3.2 通知対象に対応"""
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    PULL_REQUEST_CREATED = "pull_request_created"
    REVIEW_COMPLETED = "review_completed"
    WEEKLY_REVIEW_COMPLETED = "weekly_review_completed"
    SYSTEM_ERROR = "system_error"


class Channel(str, Enum):
    """3.3 通知チャネル(MVP対象のみ。LINE/Teams/SMS/Pushは対象外)"""
    SLACK = "slack"
    DISCORD = "discord"
    EMAIL = "email"


class DeliveryStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class NotificationEvent:
    """3.1 入力 / create_message()の入力。受領後、いかなる値も変更しない(4.2)。"""
    workflow_id: str
    event_type: EventType
    event_result: dict[str, Any]
    recipient: str
    notification_template: str
    configuration: dict[str, Any]


@dataclass
class NotificationMessage(NotificationDomain):
    """3.5 成果物: Notification Message。F01 Notification Domainを継承。"""
    workflow_id: str
    event_type: EventType
    channel: Channel
    recipient: str
    subject: str
    body: str
    template_id: str


@dataclass
class DeliveryResult:
    """3.5 成果物: Delivery Result。send()の戻り値。"""
    message_id: str
    workflow_id: str
    event_type: EventType
    channel: Channel
    status: DeliveryStatus
    retry_count: int
    duration_ms: float
    error_message: str | None = None


@dataclass
class NotificationHistory(NotificationDomain):
    """3.5 成果物: Notification History。publish()の戻り値。4.5ログ項目に対応。
    Notificationドメイン共通属性の created_at を 4.5 の timestamp として扱う。
    """
    workflow_id: str
    event_type: EventType
    channel: Channel
    delivery_status: DeliveryStatus
    retry_count: int
    duration_ms: float
```

備考:
- `NotificationDomain`(Foundation `types.Notification`)は非デフォルト引数のみ(`id`, `created_at`, `updated_at`, `metadata`)のため、サブクラスでの追加フィールドはすべて非デフォルトで問題なく継承できる。
- `event_result` / `configuration` は Foundation側で型が確定していない自由形式データのため `dict[str, Any]` とする。

---

## 4. クラス・関数シグネチャ

### 4.1 ChannelConnector インターフェース(実送信の抽象化)

```python
# src/notification/channels.py
from __future__ import annotations

from typing import Protocol

from foundation.result import Result
from notification.types import Channel, NotificationEvent, NotificationMessage


class ChannelConnector(Protocol):
    """Slack/Discord/Email への実配信を行う外部Connector(例: M21)を表す抽象境界。
    Notificationはこのインターフェースを介して配信を依頼するのみで、
    HTTP/SMTP等の実通信ロジックは本モジュールに実装しない。
    """

    def dispatch(self, message: NotificationMessage) -> Result[bool]:
        """1回分の送信試行を行い、成否を返す。再送制御はNotification側(service.py)が行う。"""
        ...


def select_channel(event: NotificationEvent) -> Result[Channel]:
    """3.3 通知チャネル選択。event.configuration からMVP対応チャネルを決定する。
    対応外チャネルが指定された場合は Result(success=False, error=UnsupportedChannelError) を返す。
    """
    ...
```

### 4.2 テンプレート処理

```python
# src/notification/templates.py
from __future__ import annotations

from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from notification.types import NotificationEvent


def render_message_body(
    event: NotificationEvent,
    config_client: ConfigurationClient,
) -> Result[str]:
    """F03 ConfigurationClient.get("notification", event.notification_template) で
    テンプレート文字列を取得し、event_type/event_resultの値で埋め込みレンダリングする。
    コード内に固定文字列テンプレートを持たない(4.4)。
    """
    ...
```

### 4.3 通知履歴ストア(MVP: インメモリ)

```python
# src/notification/history.py
from __future__ import annotations

from foundation.result import Result
from notification.types import DeliveryResult, NotificationHistory


class NotificationHistoryStore:
    """publish()が生成したNotificationHistoryを保持する。
    MVPではプロセス内インメモリ一覧のみ。永続化(DB等)は対象外。
    """

    def __init__(self) -> None: ...

    def append(self, history: NotificationHistory) -> Result[bool]: ...

    def list_all(self) -> Result[list[NotificationHistory]]: ...
```

### 4.4 NotificationModule 本体(公開インターフェース)

```python
# src/notification/service.py
from __future__ import annotations

from foundation.base_module import BaseModule
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from notification.channels import ChannelConnector
from notification.history import NotificationHistoryStore
from notification.types import (
    Channel,
    DeliveryResult,
    NotificationEvent,
    NotificationHistory,
    NotificationMessage,
)


class NotificationModule(BaseModule):
    def __init__(
        self,
        config_client: ConfigurationClient,
        channel_connectors: dict[Channel, ChannelConnector],
        history_store: NotificationHistoryStore,
    ) -> None: ...

    def name(self) -> str:
        """'notification' を返す(F02 BaseModule)。"""
        ...

    def health_check(self) -> Result[bool]:
        """依存先(ConfigurationClient等)への疎通確認結果を返す(F02 BaseModule)。"""
        ...

    def create_message(self, event: NotificationEvent) -> Result[NotificationMessage]:
        """3.6 create_message(): Event を受け取り、テンプレートをレンダリングして
        NotificationMessage を生成する。event自体は変更しない(4.2)。
        """
        ...

    def send(self, message: NotificationMessage) -> Result[DeliveryResult]:
        """3.6 send(): NotificationMessage を対応するChannelConnectorへ委譲して配信する。
        送信失敗時は最大3回まで再送し(4.3)、それでも失敗した場合は
        DeliveryStatus.FAILED として結果を返す(例外は送出せずResult内に格納)。
        """
        ...

    def publish(self, delivery_result: DeliveryResult) -> Result[NotificationHistory]:
        """3.6 publish(): DeliveryResult を NotificationHistory へ変換し、
        NotificationHistoryStoreへ記録した上で返す。
        """
        ...
```

Result[T] パターンの扱い:
- `Result.success = False` は「処理自体が実行不能だった」場合(入力不正・設定取得不能・想定外例外)にのみ用いる。
- 配信自体の成否(3回再送しても届かなかった等)は `Result.success = True` のまま `DeliveryResult.status = DeliveryStatus.FAILED` として表現する(再送を尽くした末の失敗記録は正常系のビジネス結果であるため)。

---

## 5. エラー処理

Foundationのエラー階層(`FoundationError`)を継承し、本モジュール固有の例外は最小限に留める。

```python
# src/notification/errors.py
from __future__ import annotations

from foundation.errors import ConfigurationError, ExternalServiceError, ValidationError


class NotificationError(Exception):
    """Notificationモジュール内部で捕捉し、Result[T].error へ格納するための基底。
    公開APIから直接送出はしない(F02 Result[T]パターンに従う)。
    """


class TemplateNotFoundError(ConfigurationError):
    """event.notification_template に対応するテンプレートがConfigurationに存在しない場合。"""


class UnsupportedChannelError(ValidationError):
    """MVP対応外(Slack/Discord/Email以外)のチャネルが指定された場合。"""


class DeliveryFailedError(ExternalServiceError):
    """ChannelConnector.dispatch() が最大再送回数(3回)を尽くしても失敗した場合の内部記録用。
    send()の戻り値としては例外送出せず、DeliveryResult.status=FAILEDとして返す。
    """
```

適用方針:
- `create_message()`: `foundation.validation.require_not_none` / `require_non_empty` で `NotificationEvent` の必須項目を検証し、不正時は `ValidationError` を `Result.error` に格納して `success=False` で返す。テンプレート未検出時は `TemplateNotFoundError`(`ConfigurationError`派生)。
- `send()`: チャネル未対応時は `UnsupportedChannelError`(`ValidationError`派生)を `Result.error` に格納し `success=False`。再送を尽くした通信失敗は例外化せず `DeliveryResult.status=FAILED` として `success=True` で返す(上記5章末尾の方針どおり)。ChannelConnector呼び出し中に予期しない例外が発生した場合のみ `ExternalServiceError` として捕捉し `success=False` とする。
- `publish()`: 想定される失敗要因はないため、原則 `success=True`。`history_store.append()` が失敗した場合のみ `ExternalServiceError` 相当として `success=False`。
- すべての例外はモジュール境界(`service.py`の公開メソッド内)で捕捉し、呼び出し元へは常に `Result[T]` を返す。例外を外部へ伝播させない。

---

## 6. ロギング仕様

`foundation.logger.get_logger("notification")` を各ファイルの先頭でモジュールロガーとして取得する。

```python
from foundation.logger import get_logger

logger = get_logger("notification")
```

4.5 記載のログ項目を、各処理段階で出力する。

| タイミング | ログ内容(4.5準拠項目) |
|---|---|
| `create_message()` 完了時 | `timestamp`, `workflow_id`, `event_type` |
| `send()` の各試行(初回+再送) | `timestamp`, `workflow_id`, `event_type`, `channel`, `retry_count` |
| `send()` 完了時 | `timestamp`, `workflow_id`, `event_type`, `channel`, `delivery_result`(status), `retry_count`, `duration` |
| `publish()` 完了時 | `timestamp`, `workflow_id`, `event_type`, `channel`, `delivery_result`, `retry_count`, `duration` |

禁止事項(4.5準拠):
- Secret・Access Token・Credentialはログへ出力しない。
- `NotificationMessage.body`(通知本文)や `recipient` の詳細(メールアドレス等の個人特定情報)は4.5で明示的な記録対象に含まれていないため、ログには `workflow_id` / `event_type` / `channel` 等の識別情報のみを出力し、本文・宛先そのものは出力しない。
- ログレベルは正常系 `INFO`、再送発生時 `WARNING`、3回再送後も失敗時 `ERROR` とする。

---

## 7. Unit Testケース一覧

設計書に明示の「テスト観点」章は存在しないため、3章(公開インターフェース)・4章(Constraints)・5章(Design Audit)の記載内容を根拠にテストケースを導出する。`unittest.TestCase` ベースで記述する。

### `tests/test_types.py`
- `test_notification_event_is_immutable`: `NotificationEvent` が `frozen=True` で変更不可であること
- `test_notification_message_inherits_notification_domain_fields`: `NotificationMessage` が `id`/`created_at`/`updated_at`/`metadata` を持つこと

### `tests/test_templates.py`
- `test_render_message_body_workflow_completed`: Workflow Completed テンプレート(3.4例)で `Workflow` / `Status` / `Pull Request` / `Duration` が埋め込まれること
- `test_render_message_body_review_completed`: Review通知テンプレートで判定結果(APPROVED等)とコメントが埋め込まれること
- `test_render_message_body_weekly_review`: Weekly Review通知テンプレートで最優先タスク・技術的負債件数が埋め込まれること
- `test_render_message_body_template_not_found_returns_error`: Configurationに存在しないテンプレートIDを指定した場合、`Result.success is False` かつ `error` が `TemplateNotFoundError` であること
- `test_render_message_body_no_hardcoded_template_in_code`: テンプレート文字列がコード内に定数として存在しないこと(4.4)

### `tests/test_channels.py`
- `test_select_channel_slack`: configurationでSlack指定時に`Channel.SLACK`が返ること
- `test_select_channel_discord`: Discord指定時に`Channel.DISCORD`が返ること
- `test_select_channel_email`: Email指定時に`Channel.EMAIL`が返ること
- `test_select_channel_unsupported_returns_error`: LINE等MVP対象外チャネル指定時、`Result.success is False` かつ `error` が `UnsupportedChannelError` であること

### `tests/test_history.py`
- `test_append_and_list_all`: `append()`後、`list_all()`で当該履歴が取得できること
- `test_history_contains_logging_fields`: 記録された`NotificationHistory`が4.5の全項目(workflow_id/event_type/channel/delivery_status/retry_count/duration_ms/created_at)を保持すること

### `tests/test_service.py`
- `test_name_returns_notification`: `name()` が `"notification"` を返すこと
- `test_health_check_success`: 依存先が正常な場合 `Result[bool]` で `success=True, value=True` を返すこと
- `test_create_message_success`: 正常なEventから`NotificationMessage`が生成されること
- `test_create_message_missing_required_field_returns_validation_error`: `workflow_id`等必須項目欠落時、`ValidationError`を含む失敗Resultが返ること
- `test_create_message_does_not_mutate_event`: `create_message()`呼び出し前後で入力`NotificationEvent`の内容が変化しないこと(4.2)
- `test_send_success_on_first_attempt`: ChannelConnectorが1回目で成功した場合、`retry_count=0`で`DeliveryStatus.SUCCESS`が返ること
- `test_send_retries_up_to_three_times_then_succeeds`: 2回失敗後3回目で成功した場合、`retry_count=2`で`SUCCESS`が返ること
- `test_send_fails_after_max_retries`: 3回とも失敗した場合、例外を送出せず`Result.success=True`かつ`DeliveryResult.status=FAILED`, `retry_count=3`が返ること(4.3)
- `test_send_unsupported_channel_returns_error`: 未対応チャネル指定時、`UnsupportedChannelError`を含む失敗Resultが返ること
- `test_send_records_duration`: `DeliveryResult.duration_ms`が0以上の値で記録されること
- `test_publish_creates_history_from_delivery_result`: `publish()`が`DeliveryResult`の内容を反映した`NotificationHistory`を生成し、ストアへ記録すること
- `test_publish_does_not_send_or_generate_message`: `publish()`呼び出しが`ChannelConnector.dispatch()`やテンプレートレンダリングを一切呼び出さないこと(責務分離の確認、5.1/2.2準拠)
- `test_notification_module_does_not_expose_workflow_control_methods`: `NotificationModule`がWorkflow起動・PR作成・レビュー等のメソッドを一切持たないこと(2.2/4.1責務境界の確認)

---

## 8. MVP範囲の明記

設計書5.3(重厚壮大化監査)にて対象外(削除済み)と判定された以下の機能は、本実装仕様および実装コードに一切含めない。

- 通知優先度AI
- 配信最適化
- マルチチャネル同時配信制御
- A/Bテスト
- 配信分析
- 開封率分析
- 配信スケジューリング
- 通知ルールエンジン

また、将来拡張チャネルとして明記されているLINE・Microsoft Teams・SMS・Push Notification(3.3)は本実装に含めない。`Channel` Enumおよび`select_channel()`はSlack/Discord/EmailのMVP3チャネルのみを扱う。

**実送信(Connector責務)の明確な除外:**
Notificationは通知内容(`NotificationMessage`)の生成・チャネル選択・配信結果の記録までを担当し、Slack API・Discord API・SMTP等への実際のネットワーク送信は本モジュールでは実装しない。実送信は `channels.py` の `ChannelConnector` インターフェースを介して外部Connector(Slack/DiscordについてはM21 Slack/Discord Connector)へ委譲する。M21は「メッセージの送受信のみ」を担当し「通知内容生成」を行わない(M21設計書2.2/4.4)ため、両モジュールの責務境界は本仕様の`ChannelConnector.dispatch()`呼び出し箇所で一致する。Email用Connectorの実装(SMTP等)についても同様に本モジュールの外部依存として扱い、`src/notification/`配下では実装しない。

再送制御について:
設計書2.2は「リトライ制御」をNotificationの担当外としているが、これはWorkflow全体の再実行制御(業務プロセスレベルの再試行)を指すものと解釈する。一方、4.3は「再送制御(最大3回)」をNotification自身の制約として明記しているため、これは通知メッセージの配信試行に限定した再送であり、`send()`内部の実装対象とする。両者は対象範囲が異なるため矛盾しない。
