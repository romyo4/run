"""パイプライン各モジュール間のデータ受け渡しにおける型不整合を吸収するアダプタ。

いずれも既存モジュールのソースコード(design/実装仕様書ではなく実際のsrc/実装)を唯一の
正として、実際に要求されている属性名に合わせて変換する。2026-07統合レビューで判明した
以下3件の不整合の是正:

1. Planner `ExecutionPlan`(`planner.types`)は`id`属性を持つが、Architect
   `analyzer.py`(および`architect.models.ExecutionPlan` Protocol)は`plan_id`を読む。
2. Design Auditor `ApprovedDesign`(`design_auditor.types`)は`metadata`属性を持たないが、
   Executor `_validate_approval()`(`executor.executor`)は`getattr(approved_design,
   "metadata", None)`経由で`approval_status`/`design_id`キーを読む。
3. Notification(M15) `channels.ChannelConnector` Protocolは`send(NotificationMessage)
   -> Result[bool]`を要求するが、Connector(M21) `SlackDiscordConnector.send()`は
   `OutboundMessage`を受け取り`Result[DeliveryResult]`を返す、互いに独立したデータ
   クラスを使う別のシグネチャである。両者を実際に接続する配線(composition root)は
   どこにも存在しないため、`NotificationChannelConnectorBridge`で変換する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from connector.connector import SlackDiscordConnector
from connector.types import MessageContentType, OutboundMessage, Platform
from design_auditor.types import ApprovedDesign
from foundation.result import Result
from notification.errors import UnsupportedChannelError
from notification.types import Channel, NotificationMessage
from planner.types import ExecutionPlan

__all__ = [
    "ArchitectExecutionPlanView",
    "ExecutorApprovedDesignView",
    "NotificationChannelConnectorBridge",
    "to_architect_execution_plan",
    "to_connector_outbound_message",
    "to_executor_approved_design",
]

# executor.executor._validate_approval()が参照するmetadataキー名と同一の規約
# (executor/executor.py 内の _APPROVAL_STATUS_METADATA_KEY 等と一致させる)。
_APPROVAL_STATUS_METADATA_KEY = "approval_status"
_APPROVED_STATUS_VALUE = "approved"
_APPROVED_DESIGN_ID_METADATA_KEY = "design_id"


@dataclass
class ArchitectExecutionPlanView:
    """Architect `analyzer.py` / `architect.models.ExecutionPlan` Protocolが要求する
    `plan_id`属性を、Planner `ExecutionPlan.id`から補って公開するビュー。

    `plan_id`/`objective`/`task_list`/`dependencies`はanalyzer.pyが実際に読む属性。
    `expected_output`はPlannerの`ExecutionPlan`にも同名で存在する1:1の項目。
    `priority`はanalyzer.py自体は現時点で読まないが、`architect.models.ExecutionPlan`
    Protocol(analyze_plan()の型注釈上の契約)が要求するため、構造的に満たす目的でのみ
    空dictを既定値として保持する(Plannerの`ExecutionPlan`にはPlan単位のpriorityが
    存在しないため)。
    """

    plan_id: str
    objective: str
    task_list: list[Any]
    dependencies: dict[str, list[str]]
    expected_output: str
    priority: dict[str, str] = field(default_factory=dict)


def to_architect_execution_plan(execution_plan: ExecutionPlan) -> ArchitectExecutionPlanView:
    """PlannerのExecutionPlanを、ArchitectがそのままAnalyzer入力として使える形へ変換する。"""
    return ArchitectExecutionPlanView(
        plan_id=execution_plan.id,
        objective=execution_plan.objective,
        task_list=execution_plan.task_list,
        dependencies=execution_plan.dependencies,
        expected_output=execution_plan.expected_output,
    )


@dataclass
class ExecutorApprovedDesignView:
    """Executor `_validate_approval()` が要求する`metadata["approval_status"]`/
    `metadata["design_id"]`を、Design Auditorの`ApprovedDesign`(metadata非保持)から
    補って公開するビュー。

    `metadata`以外の属性(`design_id`/`audit_id`/`approved_at`/`comments`等)は、
    executor.py側が将来アクセスする可能性を考慮し、`source`(元のApprovedDesign)へ
    そのまま委譲する。
    """

    source: ApprovedDesign
    metadata: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        # dataclassフィールド(source/metadata)は通常の属性解決で見つかるため、
        # ここに到達するのはsource側にのみ存在する属性へのアクセス時のみ。
        source = self.__dict__.get("source")
        if source is None:
            raise AttributeError(name)
        return getattr(source, name)


def to_executor_approved_design(approved_design: ApprovedDesign) -> ExecutorApprovedDesignView:
    """Design AuditorのApprovedDesignを、Executorがそのままload_design()入力として
    使える形へ変換する。"""
    return ExecutorApprovedDesignView(
        source=approved_design,
        metadata={
            _APPROVAL_STATUS_METADATA_KEY: _APPROVED_STATUS_VALUE,
            _APPROVED_DESIGN_ID_METADATA_KEY: approved_design.design_id,
        },
    )


# Notification(M15) Channel <-> Connector(M21) Platform。Channel.EMAILはConnector(M21)が
# 対応するプラットフォームではないため、意図的に対応表から除外する(SlackDiscordConnectorの
# 責務外であり、silent mishandlingを避けるため呼び出し前にエラーとして扱う)。
_CHANNEL_TO_PLATFORM: dict[Channel, Platform] = {
    Channel.SLACK: Platform.SLACK,
    Channel.DISCORD: Platform.DISCORD,
}


def to_connector_outbound_message(message: NotificationMessage) -> Result[OutboundMessage]:
    """NotificationのNotificationMessageを、ConnectorがそのままSlackDiscordConnector.send()
    入力として使えるOutboundMessageへ変換する。

    channel_idは`message.recipient`(design/M15 Notification.txt 3.1「recipient」)、
    text は `message.subject`/`message.body`を結合したもの(design/M15 Notification.txt
    5章の代表例「PR #152 を作成しました」のようなプレーンテキスト通知)、content_typeは
    Slack/Discordのプレーンテキスト通知にのみ対応するMVP範囲(design/M15 Notification.txt
    5章)に合わせ`MessageContentType.TEXT`を用いる。
    """
    platform = _CHANNEL_TO_PLATFORM.get(message.channel)
    if platform is None:
        return Result(
            success=False,
            error=UnsupportedChannelError(f"Connector(M21)が対応していないChannelです: {message.channel.value!r}"),
        )

    return Result(
        success=True,
        value=OutboundMessage(
            platform=platform,
            channel_id=message.recipient,
            content_type=MessageContentType.TEXT,
            text=f"{message.subject}\n\n{message.body}",
        ),
    )


@dataclass
class NotificationChannelConnectorBridge:
    """Notification `channels.ChannelConnector` Protocolを、Connector(M21)の
    `SlackDiscordConnector`へ委譲することで満たすブリッジ。

    `to_connector_outbound_message()`でNotificationMessageをOutboundMessageへ変換し、
    `SlackDiscordConnector.send()`の戻り値(`Result[DeliveryResult]`)の
    `DeliveryResult.delivered`を`Result[bool]`へ変換して返す。Channel.EMAILは
    Connector(M21)が対応しないため、`SlackDiscordConnector.send()`を呼び出さずに
    `UnsupportedChannelError`を返す。
    """

    connector: SlackDiscordConnector

    def send(self, message: NotificationMessage) -> Result[bool]:
        outbound_result = to_connector_outbound_message(message)
        if not outbound_result.success or outbound_result.value is None:
            return Result(success=False, error=outbound_result.error)

        delivery_result = self.connector.send(outbound_result.value)
        if not delivery_result.success or delivery_result.value is None:
            return Result(success=False, error=delivery_result.error)

        return Result(success=True, value=delivery_result.value.delivered)
