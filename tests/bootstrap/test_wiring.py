"""Task 4: 21モジュールの実インスタンス化(`wiring.py`)のテスト。

`build_application()`が例外なく完了し、返された`Application`が保持する全モジュールの
`health_check()`が成功(Result.success=True かつ Result.value=True相当)を返すことを確認する。
"""

import unittest
from unittest.mock import patch

from bootstrap.wiring import build_application
from github_manager.client import UrllibHttpTransport
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


class UseRealGithubTest(unittest.TestCase):
    """Phase 1-A: `use_real_github=True`時にGitHub Managerが実HttpTransport
    (`UrllibHttpTransport`)で構築され、`GITHUB_TOKEN`環境変数から認証情報を
    取得することを確認する(実際のネットワーク呼び出しは行わない)。"""

    def test_default_wiring_uses_stub_transport(self) -> None:
        app = build_application()

        transport = app.github_manager._client._transport  # noqa: SLF001 - 配線確認のみ

        self.assertNotIsInstance(transport, UrllibHttpTransport)

    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token-value"}, clear=False)
    def test_use_real_github_wires_urllib_transport(self) -> None:
        app = build_application(use_real_github=True)

        transport = app.github_manager._client._transport  # noqa: SLF001 - 配線確認のみ

        self.assertIsInstance(transport, UrllibHttpTransport)

    @patch.dict("os.environ", {}, clear=True)
    def test_use_real_github_without_token_raises_runtime_error(self) -> None:
        with self.assertRaises(RuntimeError):
            build_application(use_real_github=True)


if __name__ == "__main__":
    unittest.main()
