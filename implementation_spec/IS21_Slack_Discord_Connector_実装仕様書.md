# IS21 Slack / Discord Connector 実装仕様書

- 対象設計書: `M21 Slack Discord Connector.txt`（Design Freeze v1.0）
- 対象バージョン: `DESIGN_VERSION = "v1.0"`
- 実装言語: Python 3.13
- 配置先: `src/connector/`

本書は M21 Slack / Discord Connector の詳細設計書を実装可能な粒度に具体化したものであり、設計書に記載のない機能・APIを追加しない。設計書の記述と本書が矛盾する場合は設計書を正とする。Foundation(M00)が提供する `Result[T]` / `BaseModule` / エラー階層 / `get_logger()` / `ConfigurationClient` / Domain Model(`CommunicationMessage`, `Notification`)を前提として利用する。

---

## 1. モジュール概要

Slack / Discord Connector は、AI Development Pipeline における Slack・Discord との唯一の通信窓口であり、責務は「メッセージ受信」「メッセージ送信」「添付ファイル受信」「ユーザー識別」「チャネル識別」「プラットフォーム差異の吸収」に限定される。Slack・Discord固有のイベント形式・API呼び出し方法の違いはConnector内のAdapter層で吸収し、Command Routerへは共通フォーマット（Normalized Message）としてのみ引き渡す。コマンド解析・権限判定・Workflow起動・通知内容生成・AI実行・Repository操作は一切行わず、通知本文はNotificationモジュールが生成したものを送信するのみとする。MVPではセッション情報・会話履歴を保持せず、受信メッセージを共通フォーマットへ変換する処理のみを行う（設計書4.3）。

---

## 2. ファイル構成

```text
src/connector/
├── __init__.py         # 公開APIの再エクスポート
├── types.py             # Platform/EventType/MessageContentType Enum、
│                         # PlatformEvent・NormalizedMessage・OutboundMessage・
│                         # DeliveryResult・ConnectionStatus・Attachment の dataclass定義
├── exceptions.py        # Connector固有例外（Foundationのエラー階層を継承）
├── adapter.py            # Adapter Pattern共通インターフェース(MessageAdapter, ABC)
├── slack_adapter.py      # Slack固有の受信イベント解析・送信APIを実装するAdapter
├── discord_adapter.py    # Discord固有の受信イベント解析・送信APIを実装するAdapter
├── connector.py          # SlackDiscordConnector(BaseModule) 本体。公開インターフェース3関数を実装
└── tests/
    ├── test_types.py
    ├── test_slack_adapter.py
    ├── test_discord_adapter.py
    ├── test_connector.py
    └── test_exceptions.py
```

役割の要約:

| ファイル | 役割 |
|---|---|
| `types.py` | 設計書3.2(出力構造)・3.4(送信イベント)・3.5(成果物)に対応するデータ構造の定義のみを行う |
| `exceptions.py` | 設計書4.5(エラー処理観点)のうち、Foundationのエラー階層に存在しない「未対応プラットフォーム」「イベント解析失敗」を表す例外を追加定義 |
| `adapter.py` | 設計書4.2(共通フォーマットへ変換)・Foundation F00(Adapter Pattern)に対応する、Slack/Discordの差異を吸収する層の共通インターフェース |
| `slack_adapter.py` | 設計書3.3(Slack受信イベント: Message/Mention/Slash Command/File Upload)・3.4(送信イベント)をSlack API仕様に基づき実装するAdapter |
| `discord_adapter.py` | 設計書3.3(Discord受信イベント: Message/Mention/File Upload)・3.4(送信イベント)をDiscord API仕様に基づき実装するAdapter |
| `connector.py` | 設計書3.6(公開インターフェース: `receive()`/`send()`/`health()`)を実装する本体クラス。`BaseModule`を継承する(F02)。Platform種別に応じて適切なAdapterへ委譲する |

---

## 3. データクラス定義

Foundation(F01)の `CommunicationMessage` Domainは共通属性(`id`/`created_at`/`updated_at`/`metadata`)のみを保証し、モジュール固有属性はConnector側で追加定義する(Foundation 3.3節)。Connectorが生成する「Normalized Message」(設計書3.2)は、`CommunicationMessage`をフィールドとして内包する形で定義する。同様に、送信入力である「Notification Message」(設計書3.6 `send()`の入力)は、Foundation `Notification` Domainを内包しつつ、Connectorが配送に必要とする最小限の情報を追加した `OutboundMessage` として定義する。

補足(要確認事項): 設計書3.6は`send()`の入力名を「Notification Message」と記載するが、その具体的なフィールド構造はM21設計書内に明文化されていない(通知内容の生成はNotificationモジュールの責務であり、Connectorはその成果物を受け取って配送するのみ)。本書では、Connectorが配送処理に最小限必要とする情報(送信先platform/channel_id、内容種別、テキスト、添付)を`OutboundMessage`として補完定義する。これは新規責務の追加ではなく、設計書3.4(送信イベント種別)・3.2(出力構造との対称性)から導出した配送用の入力形状であり、通知本文の生成ロジックは一切含まない。

```python
# types.py
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from foundation.types import CommunicationMessage, Notification
from foundation.utils import utc_now


class Platform(str, Enum):
    """Connectorが対応するプラットフォーム(設計書「適用対象」)。"""

    SLACK = "slack"
    DISCORD = "discord"


class EventType(str, Enum):
    """受信イベント種別(設計書3.3)。Slack/Discord双方で共通に扱う。"""

    MESSAGE = "message"
    MENTION = "mention"
    SLASH_COMMAND = "slash_command"  # Slackのみ(設計書3.3)
    FILE_UPLOAD = "file_upload"


class MessageContentType(str, Enum):
    """送信イベント種別(設計書3.4)。"""

    TEXT = "text"
    MARKDOWN = "markdown"
    FILE = "file"
    IMAGE = "image"


@dataclass
class Attachment:
    """添付ファイル(設計書2.1「添付ファイル受信」、3.2「attachments」)。"""

    filename: str
    content_type: str
    url: str | None = None       # 受信時: プラットフォームがホストするURL
    data: bytes | None = None    # 送信時: 直接渡すバイナリ本体


@dataclass
class PlatformEvent:
    """receive()の入力(設計書3.6「Platform Event」)。

    どちらのプラットフォームからのイベントかを明示するためplatformを持つ。
    raw_payloadは各プラットフォームAPIが渡す生イベントをそのまま保持する。
    """

    platform: Platform
    raw_payload: dict[str, Any]
    received_at: datetime = field(default_factory=utc_now)


@dataclass
class NormalizedMessage:
    """receive()の出力(設計書3.2「Normalized Message」)。

    platform/user_id/channel_id/message/attachments/timestampは設計書3.2に明記された
    構造そのもの。event_typeは設計書4.5のログ項目(event_type)を記録するために必要な
    情報であり、本書で補完した追加フィールドである(受信イベントの種別を保持しないと
    ログ要件を満たせないため)。communication_messageはFoundation(F01)
    `CommunicationMessage` Domainの共通属性(id/created_at/updated_at/metadata)を保持する。
    """

    platform: Platform
    user_id: str
    channel_id: str
    message: str
    attachments: list[Attachment]
    timestamp: datetime
    event_type: EventType
    communication_message: CommunicationMessage = field(default_factory=CommunicationMessage)


@dataclass
class OutboundMessage:
    """send()の入力(設計書3.6「Notification Message」)。3節補足を参照。"""

    platform: Platform
    channel_id: str
    content_type: MessageContentType
    text: str | None = None
    attachments: list[Attachment] = field(default_factory=list)
    user_id: str | None = None
    notification: Notification = field(default_factory=Notification)


@dataclass
class DeliveryResult:
    """send()の出力(設計書3.5「Delivery Result」)。"""

    platform: Platform
    channel_id: str
    delivered: bool
    message_id: str | None = None       # プラットフォームAPIが返す送信先メッセージID
    error_message: str | None = None
    delivered_at: datetime = field(default_factory=utc_now)


@dataclass
class ConnectionStatus:
    """health()の出力(設計書3.5「Connection Status」)。

    Connectorは1インスタンスでSlack/Discord両方を扱うため(設計書2.1)、
    両プラットフォームの接続可否を1つの成果物にまとめて返す。
    """

    slack_connected: bool
    discord_connected: bool
    checked_at: datetime = field(default_factory=utc_now)
    detail: dict[str, str] = field(default_factory=dict)  # platform名 -> 補足メッセージ(任意)
```

---

## 4. クラス・関数シグネチャ

### 4.1 Adapter共通インターフェース(`adapter.py`)

設計書4.2「Slack と Discord の違いは Connector 内で吸収する」に対応するAdapter Pattern層。Slack/Discordそれぞれの実装は本ABCを継承する。

```python
from abc import ABC, abstractmethod
from typing import Any

from foundation.result import Result

from connector.types import ConnectionStatus, DeliveryResult, NormalizedMessage, OutboundMessage, Platform


class MessageAdapter(ABC):
    """Slack/Discordの差異を吸収する共通インターフェース(設計書4.2, Foundation F00: Adapter Pattern)。"""

    @property
    @abstractmethod
    def platform(self) -> Platform:
        """このAdapterが担当するプラットフォームを返す。"""

    @abstractmethod
    def parse_event(self, raw_payload: dict[str, Any]) -> Result[NormalizedMessage]:
        """プラットフォーム固有のPlatform Event(raw_payload)をNormalized Messageへ変換する。"""

    @abstractmethod
    def deliver(self, message: OutboundMessage) -> Result[DeliveryResult]:
        """OutboundMessageをプラットフォームAPI経由で送信する。"""

    @abstractmethod
    def check_connection(self) -> Result[bool]:
        """プラットフォームAPIへの接続可否を確認する。"""
```

### 4.2 `slack_adapter.py`

```python
from typing import Any

from foundation.interfaces import ConfigurationClient
from foundation.result import Result

from connector.adapter import MessageAdapter
from connector.types import ConnectionStatus, DeliveryResult, NormalizedMessage, OutboundMessage, Platform


class SlackAdapter(MessageAdapter):
    """Slack Events API / Web APIとの入出力を担当するAdapter。"""

    def __init__(self, config_client: ConfigurationClient) -> None:
        # ConfigurationClient.get("connector", "slack_bot_token") 等でトークンを取得する(F03)。
        # トークンはインスタンス内にのみ保持し、ログには一切出力しない(設計書4.5)。
        ...

    @property
    def platform(self) -> Platform: ...  # Platform.SLACK を返す

    def parse_event(self, raw_payload: dict[str, Any]) -> Result[NormalizedMessage]:
        """Slack Events APIペイロード(message/app_mention/slash command/file_shared)を
        NormalizedMessageへ変換する(設計書3.3)。event_typeはペイロードのtype・
        command有無・bot mention有無から判定する。解析できない形式はEventParseError。"""

    def deliver(self, message: OutboundMessage) -> Result[DeliveryResult]:
        """content_typeに応じてSlack Web APIを呼び分ける(設計書3.4)。
        TEXT/MARKDOWN: chat.postMessage相当、FILE/IMAGE: files.upload相当。
        API呼び出し失敗はSlackApiErrorとしてResult.errorに格納する。"""

    def check_connection(self) -> Result[bool]:
        """auth.test相当のAPI呼び出しで接続可否を確認する。"""
```

### 4.3 `discord_adapter.py`

```python
from typing import Any

from foundation.interfaces import ConfigurationClient
from foundation.result import Result

from connector.adapter import MessageAdapter
from connector.types import ConnectionStatus, DeliveryResult, NormalizedMessage, OutboundMessage, Platform


class DiscordAdapter(MessageAdapter):
    """Discord Gateway/REST APIとの入出力を担当するAdapter。"""

    def __init__(self, config_client: ConfigurationClient) -> None:
        # ConfigurationClient.get("connector", "discord_bot_token") 等でトークンを取得する(F03)。
        ...

    @property
    def platform(self) -> Platform: ...  # Platform.DISCORD を返す

    def parse_event(self, raw_payload: dict[str, Any]) -> Result[NormalizedMessage]:
        """DiscordのMESSAGE_CREATE等のイベントペイロードをNormalizedMessageへ変換する
        (設計書3.3: Message/Mention/File Upload)。解析できない形式はEventParseError。"""

    def deliver(self, message: OutboundMessage) -> Result[DeliveryResult]:
        """content_typeに応じてDiscord REST APIを呼び分ける(設計書3.4)。
        TEXT/MARKDOWN: メッセージ送信、FILE/IMAGE: 添付ファイル付きメッセージ送信。
        API呼び出し失敗はDiscordApiErrorとしてResult.errorに格納する。"""

    def check_connection(self) -> Result[bool]:
        """Bot接続状態(Gateway/REST到達性)を確認する。"""
```

### 4.4 公開インターフェース(`connector.py`)

設計書3.6の3関数(`receive()`/`send()`/`health()`)の名称・入出力を厳守する。`BaseModule`が要求する`name()`/`health_check()`(F02)は別途実装する。

```python
from foundation.base_module import BaseModule
from foundation.interfaces import ConfigurationClient
from foundation.result import Result

from connector.adapter import MessageAdapter
from connector.types import ConnectionStatus, DeliveryResult, NormalizedMessage, OutboundMessage, PlatformEvent, Platform


class SlackDiscordConnector(BaseModule):
    """Slack/Discordとの唯一の通信窓口(設計書全体)。送受信のみを担当する。"""

    def __init__(
        self,
        config_client: ConfigurationClient,
        slack_adapter: MessageAdapter | None = None,
        discord_adapter: MessageAdapter | None = None,
    ) -> None:
        # slack_adapter/discord_adapterを外部注入可能にする(テスト容易性のため)。
        # 未指定時はconfig_clientから SlackAdapter / DiscordAdapter を生成する。
        ...

    # --- F02: BaseModule ---
    def name(self) -> str: ...

    def health_check(self) -> Result[bool]: ...

    # --- 設計書3.6: 公開インターフェース ---
    def receive(self, event: PlatformEvent) -> Result[NormalizedMessage]: ...

    def send(self, message: OutboundMessage) -> Result[DeliveryResult]: ...

    def health(self) -> Result[ConnectionStatus]: ...

    # --- 内部ヘルパー ---
    def _adapter_for(self, platform: Platform) -> Result[MessageAdapter]:
        """platformに対応するAdapterを返す。未対応のPlatformはUnsupportedPlatformError。"""
```

各関数の仕様:

- **`name()`**: `"slack_discord_connector"` 等、固定のモジュール名を返す。
- **`health_check()`**: `health()`の結果(`ConnectionStatus`)から、Slack/Discordの少なくとも一方が接続可能であれば`Result(success=True, value=True)`を返す(F02が要求する真偽値判定への集約)。
- **`receive(event)`**: `event.platform`から`_adapter_for()`でAdapterを選択し、`adapter.parse_event(event.raw_payload)`へ委譲する。Adapterが返す`Result`をそのまま返す(Connector自身はメッセージ内容の解釈・加工を行わない)。
- **`send(message)`**: `message.platform`から`_adapter_for()`でAdapterを選択し、`adapter.deliver(message)`へ委譲する。通知本文の生成・加工は行わず、受け取った`OutboundMessage`をそのまま送信する(設計書4.4)。
- **`health()`**: 保持している全Adapter(Slack/Discord)の`check_connection()`を呼び出し、結果を`ConnectionStatus`へ集約して返す。個々のAdapter呼び出しが例外を送出しても、他方のチェックは継続する(1プラットフォーム障害が全体を落とさない)。

---

## 5. エラー処理

Foundation(M00 3.6)のエラー階層を継承して利用する。

```text
FoundationError (Foundation定義の基底)
├── ExternalServiceError … Slack/Discord API呼び出し失敗全般(認証エラー・レート制限・タイムアウト等)
└── ValidationError       … 未対応platform指定、Platform Eventのraw_payloadが解析不能な場合
```

設計書4.5(エラー処理観点として明記はされていないが、3.6の入出力仕様上必要となる)に基づき、`exceptions.py`にてConnector固有例外を追加する(Foundation 3.6「各モジュールは必要に応じてこれらを継承し、モジュール固有の例外を定義できる」に従う)。

```python
# exceptions.py
from foundation.errors import ExternalServiceError, ValidationError


class SlackApiError(ExternalServiceError):
    """Slack API呼び出しが失敗した場合に送出する。"""


class DiscordApiError(ExternalServiceError):
    """Discord API呼び出しが失敗した場合に送出する。"""


class UnsupportedPlatformError(ValidationError):
    """platformがSlack/Discordのいずれでもない場合に送出する。"""


class EventParseError(ValidationError):
    """Platform Eventのraw_payloadをNormalized Messageへ変換できない場合に送出する。"""
```

すべての公開インターフェース(`receive`/`send`/`health`/`health_check`)は、Adapter内部・Connector内部で発生した例外を捕捉し、`Result[T](success=False, value=None, error=<該当例外インスタンス>)`として返す。例外を呼び出し元(Command Router・Notification)へ直接送出しない(F02: `Result[T]`パターン、設計書4.2「Command RouterはプラットフォームAPI例外を意識してはならない」の裏付け)。

---

## 6. ロギング仕様

`foundation.logger.get_logger("connector")`で取得したLoggerを`connector.py`のモジュールレベルで1つ生成し、Adapter含む全クラスで共有する。

```python
from foundation.logger import get_logger

logger = get_logger("connector")
```

設計書4.5に定めるログ項目を、`receive()`/`send()`/`health()`実行の都度、以下のkey=value形式でmessage部に出力する。

```text
timestamp    : イベント発生時刻
platform     : "slack" | "discord"
user_id      : 対象ユーザーID(send()でuser_id未設定の場合はNone)
channel_id   : 対象チャネルID
event_type   : receive()時は EventType の値、send()時は MessageContentType の値、
               health()時は "health_check" 固定
result       : "success" | "failure"(失敗時はエラークラス名も付記)
```

**機密情報のマスキング方針(設計書4.5「メッセージ本文・添付ファイル・Access Tokenはログへ出力してはならない」)**:

- ログ出力は上記5項目+resultのみを明示的に組み立てて`logger.info()`/`logger.warning()`へ渡す。`NormalizedMessage`/`OutboundMessage`/`PlatformEvent`のインスタンスを`str()`/`repr()`や`dataclasses.asdict()`でそのままログへ渡すことを禁止する(`message`フィールド・`attachments`フィールドが漏洩するため)。
- Slack/Discordのbot tokenは`SlackAdapter`/`DiscordAdapter`のインスタンス変数にのみ保持し、ログ出力対象のいずれの項目にも含めない。トークン文字列が含まれる可能性がある外部ライブラリの例外は、`SlackApiError`/`DiscordApiError`へラップする際にトークン文字列を除去したメッセージへ置き換える。
- 失敗時は`result=failure`に加え、エラークラス名(例: `SlackApiError`)のみを記録し、例外メッセージ全文はToken漏洩リスクがあるため要約(種別のみ)にとどめる。

---

## 7. Unit Testケース一覧（unittest）

M21設計書には明示的な「テスト観点」節はないため、責務(2章)・公開インターフェース(3.6)・制約(4章)から導出したテスト観点に基づき列挙する。

### 7.1 `test_types.py`

- `test_normalized_message_holds_all_designed_fields`（platform/user_id/channel_id/message/attachments/timestampを保持する）
- `test_normalized_message_communication_message_defaults`（`communication_message`がFoundationの共通属性を既定生成する）
- `test_outbound_message_defaults_notification_when_not_given`
- `test_delivery_result_defaults_delivered_at`
- `test_connection_status_defaults_checked_at`
- `test_attachment_supports_url_or_data_independently`

### 7.2 `test_slack_adapter.py`

- `test_parse_event_normalizes_slack_message_event`
- `test_parse_event_normalizes_slack_mention_event`
- `test_parse_event_normalizes_slack_slash_command_event`
- `test_parse_event_normalizes_slack_file_upload_event`
- `test_parse_event_returns_event_parse_error_for_unrecognized_payload`
- `test_deliver_sends_text_message`
- `test_deliver_sends_markdown_message`
- `test_deliver_sends_file`
- `test_deliver_sends_image`
- `test_deliver_returns_slack_api_error_on_api_failure`
- `test_check_connection_returns_true_when_api_reachable`
- `test_check_connection_returns_false_when_api_unreachable`

### 7.3 `test_discord_adapter.py`

- `test_parse_event_normalizes_discord_message_event`
- `test_parse_event_normalizes_discord_mention_event`
- `test_parse_event_normalizes_discord_file_upload_event`
- `test_parse_event_returns_event_parse_error_for_unrecognized_payload`
- `test_deliver_sends_text_message`
- `test_deliver_sends_markdown_message`
- `test_deliver_sends_file`
- `test_deliver_sends_image`
- `test_deliver_returns_discord_api_error_on_api_failure`
- `test_check_connection_returns_true_when_api_reachable`
- `test_check_connection_returns_false_when_api_unreachable`

### 7.4 `test_connector.py`

- `test_receive_delegates_to_slack_adapter_for_slack_platform`
- `test_receive_delegates_to_discord_adapter_for_discord_platform`
- `test_receive_returns_unsupported_platform_error_for_unknown_platform`
- `test_receive_does_not_modify_normalized_message_content`（Connectorがメッセージ内容を加工しないことの確認）
- `test_send_delegates_to_slack_adapter_for_slack_platform`
- `test_send_delegates_to_discord_adapter_for_discord_platform`
- `test_send_returns_unsupported_platform_error_for_unknown_platform`
- `test_send_forwards_outbound_message_without_generating_content`（通知本文を生成しないことの確認）
- `test_health_aggregates_slack_and_discord_connection_status`
- `test_health_continues_when_one_platform_check_raises`（一方のAdapter障害が他方の判定を妨げない）
- `test_health_check_returns_true_when_at_least_one_platform_connected`
- `test_health_check_returns_false_when_both_platforms_disconnected`
- `test_name_returns_fixed_module_name`
- `test_receive_wraps_adapter_exception_into_failure_result`
- `test_send_wraps_adapter_exception_into_failure_result`

### 7.5 `test_exceptions.py`

- `test_slack_api_error_is_external_service_error_subclass`
- `test_discord_api_error_is_external_service_error_subclass`
- `test_unsupported_platform_error_is_validation_error_subclass`
- `test_event_parse_error_is_validation_error_subclass`

### 7.6 ロギング・機密情報マスキング（`test_connector.py`内に含める）

- `test_receive_log_output_does_not_contain_message_body`
- `test_send_log_output_does_not_contain_attachment_data`
- `test_log_output_does_not_contain_bot_token`
- `test_log_output_contains_required_fields`（timestamp/platform/user_id/channel_id/event_type/result）

---

## 8. MVP範囲の明記

設計書5.3節(重厚壮大化監査)にて対象外・削除済みとされた以下の機能は、本実装仕様の対象外とし、Connectorには実装しない。

- LINE対応
- Microsoft Teams対応
- Telegram対応
- Web UI対応
- 音声入力
- 音声読み上げ
- マルチチャネル同報
- メッセージキュー

また、設計書2.2(担当しない)・4.1(通信のみ担当する)・4.4(Notificationを生成しない)に基づき、以下も本モジュールの実装範囲外とする。

- コマンド解析(Command Routerが担当)
- 権限判定(Permission Managerが担当)
- Workflow起動(Scheduler/Command Routerが担当)
- 通知内容生成(Notificationが担当。Connectorは生成済み`OutboundMessage`を送信するのみ)
- AI実行
- Repository操作

セッション情報・会話履歴の保持は行わない(設計書4.3)。`receive()`は受信した`Platform Event`を`Normalized Message`へ変換して返すのみであり、過去のやり取りとの関連付け・文脈保持は実装しない。Connectorが内部に保持する状態は、Adapterが利用するAPI接続設定(トークン等、`ConfigurationClient`経由で取得)のみとする。
