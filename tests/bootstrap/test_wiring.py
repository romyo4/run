"""Task 4: 21モジュールの実インスタンス化(`wiring.py`)のテスト。

`build_application()`が例外なく完了し、返された`Application`が保持する全モジュールの
`health_check()`が成功(Result.success=True かつ Result.value=True相当)を返すことを確認する。
"""

import unittest

from bootstrap.wiring import build_application
from notification.types import Channel


class BuildApplicationTest(unittest.TestCase):
    def test_build_application_succeeds(self) -> None:
        app = build_application()
        self.assertIsNotNone(app)

    def test_all_modules_report_healthy(self) -> None:
        app = build_application()
        for module in app.all_modules():
            result = module.health_check()
            self.assertTrue(result.success, msg=f"{module.name()}: {result.error}")
            self.assertTrue(result.value, msg=f"{module.name()} reported unhealthy")

    def test_notification_resolves_channel_connector_for_slack_and_discord(self) -> None:
        """`NotificationChannelConnectorBridge`がbuild_application()の合成根で実際に
        NotificationModuleへ渡され、Slack/Discordの両チャネルについて
        ChannelConnectorが登録されていることを確認する(bootstrap/adapters.pyの
        NotificationChannelConnectorBridgeが未配線のまま放置されないための回帰テスト)。
        """
        app = build_application()

        channel_connectors = app.notification._channel_connectors  # noqa: SLF001 - 配線確認のみ

        self.assertIn(Channel.SLACK, channel_connectors)
        self.assertIn(Channel.DISCORD, channel_connectors)
        self.assertIsNotNone(channel_connectors[Channel.SLACK])
        self.assertIsNotNone(channel_connectors[Channel.DISCORD])


if __name__ == "__main__":
    unittest.main()
