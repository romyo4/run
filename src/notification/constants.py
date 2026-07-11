"""Notification (M15) 固定値。

モジュール名・最大再送回数(4.3=3回)・MVP対応チャネル一覧を集約し、
コード中への直書きを避ける(IS15 2. ファイル構成)。
"""

from __future__ import annotations

from notification.types import Channel

MODULE_NAME = "notification"

MAX_RETRY_COUNT = 3

SUPPORTED_CHANNELS: tuple[Channel, ...] = (Channel.SLACK, Channel.DISCORD, Channel.EMAIL)
