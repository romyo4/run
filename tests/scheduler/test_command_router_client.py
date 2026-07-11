"""Scheduler(M14) command_router_client.pyのテスト(IS14仕様書7節 test_command_router_client.py)。

Scheduler→Command Routerの一方向依存(Design Freeze監査確定事項)を検証する。
"""

from __future__ import annotations

import inspect
import unittest
from datetime import UTC, datetime
from typing import Any

from foundation.errors import ExternalServiceError
from foundation.result import Result
from scheduler import command_router_client as command_router_client_module
from scheduler.command_router_client import CommandRouterAdapter, CommandRouterClient, RawCommand
from scheduler.exceptions import CommandRouterDispatchError
from scheduler.models import ExecutionRequest, TriggerType

_NOW = datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC)


class _FakeCommandRouter:
    """CommandRouterClient Protocolを満たすテスト用フェイク。receive()のみ提供する。

    実際のCommand Router(M05)の`receive()`と同様、引数はdictではなく属性アクセス
    可能なRaw Command形状(`RawCommand`)であることを検証する。
    """

    def __init__(self, result: Result[Any]) -> None:
        self._result = result
        self.received_raw_commands: list[RawCommand] = []

    def receive(self, raw_command: RawCommand) -> Result[Any]:
        self.received_raw_commands.append(raw_command)
        return self._result


def _make_request(retry_count: int = 0) -> ExecutionRequest:
    return ExecutionRequest(
        request_id="req-1",
        workflow_id="wf-1",
        trigger_type=TriggerType.MANUAL,
        source="cli",
        requested_at=_NOW,
        payload={"note": "LP改善"},
        retry_count=retry_count,
    )


class TestCommandRouterAdapterSubmit(unittest.TestCase):
    def test_submit_converts_execution_request_to_raw_command_format(self) -> None:
        fake_router = _FakeCommandRouter(Result(success=True, value={"accepted": True}))
        adapter = CommandRouterAdapter(fake_router)
        request = _make_request(retry_count=2)

        adapter.submit(request)

        self.assertEqual(len(fake_router.received_raw_commands), 1)
        raw_command = fake_router.received_raw_commands[0]
        # Command Router(M05)のRaw Command契約(属性アクセス前提)を満たすことを検証する。
        self.assertEqual(raw_command.command_id, "req-1")
        self.assertEqual(raw_command.source, "cli")
        self.assertEqual(raw_command.timestamp, _NOW)
        self.assertEqual(raw_command.command, "wf-1")
        self.assertEqual(raw_command.attachments, [])
        self.assertEqual(raw_command.metadata["trigger_type"], "MANUAL")
        self.assertEqual(raw_command.metadata["retry_count"], 2)
        self.assertEqual(raw_command.metadata["payload"], {"note": "LP改善"})
        # user_idはExecutionRequestに存在しないため、Scheduler内部起動コマンドを示す
        # 固定文字列が設定されること(空文字列や欠落ではないこと)のみを確認する。
        self.assertTrue(raw_command.user_id)

    def test_submit_returns_success_result_on_command_router_ack(self) -> None:
        fake_router = _FakeCommandRouter(Result(success=True, value={"accepted": True}))
        adapter = CommandRouterAdapter(fake_router)

        result = adapter.submit(_make_request())

        self.assertTrue(result.success)
        self.assertEqual(result.value, {"accepted": True})
        self.assertIsNone(result.error)

    def test_submit_wraps_command_router_failure_as_command_router_dispatch_error(self) -> None:
        fake_router = _FakeCommandRouter(Result(success=False, value=None, error=ExternalServiceError("router down")))
        adapter = CommandRouterAdapter(fake_router)

        result = adapter.submit(_make_request())

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, CommandRouterDispatchError)
        self.assertIsNone(result.value)

    def test_submit_never_forwards_command_router_call_back_to_scheduler(self) -> None:
        # command_router_client.py はimport文レベルでscheduler_module(Scheduler本体)に
        # 依存してはならない(Scheduler→Command Routerの一方向依存: Design Freeze監査確定事項)。
        import_lines = [
            line.strip()
            for line in inspect.getsource(command_router_client_module).splitlines()
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        for line in import_lines:
            self.assertNotIn(
                "scheduler_module",
                line,
                f"command_router_client.py must not import scheduler_module (one-way dependency): {line!r}",
            )

        # CommandRouterClient Protocolはreceive()のみを公開し、Scheduler側へコールバック
        # するためのメソッド(register_callback等)を一切持たない。
        protocol_members = {name for name in vars(CommandRouterClient) if not name.startswith("_")}
        self.assertEqual(protocol_members, {"receive"})

        # CommandRouterAdapterはsubmit()以外にCommand Router側から呼び出される公開APIを
        # 持たない(コールバック経路が存在しないことの回帰防止)。
        adapter_public_methods = {
            name for name, value in vars(CommandRouterAdapter).items() if not name.startswith("_") and callable(value)
        }
        self.assertEqual(adapter_public_methods, {"submit"})

    def test_command_router_client_does_not_import_command_router_package(self) -> None:
        # Command Router(M05)の具象クラス(command_router.models.RawCommand等)を直接
        # importしてはならない。SchedulerはRaw Command契約と同一形状の値を自前で構築し、
        # ダックタイピングでreceive()へ渡す(依存方向はScheduler→Command Routerの一方向のみ)。
        import_lines = [
            line.strip()
            for line in inspect.getsource(command_router_client_module).splitlines()
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        for line in import_lines:
            self.assertNotIn(
                "command_router",
                line,
                f"command_router_client.py must not import command_router package directly: {line!r}",
            )

    def test_raw_command_shape_matches_command_router_raw_command_fields(self) -> None:
        # Scheduler側RawCommandは、Command Router(M05)のRawCommandと同一のフィールド名
        # 集合を持つこと(属性アクセスによるダックタイピングが成立するための前提)。
        from command_router.models import RawCommand as CommandRouterRawCommand

        scheduler_fields = {f for f in RawCommand.__dataclass_fields__}
        command_router_fields = {f for f in CommandRouterRawCommand.__dataclass_fields__}
        self.assertEqual(scheduler_fields, command_router_fields)


if __name__ == "__main__":
    unittest.main()
