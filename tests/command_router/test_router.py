"""CommandRouterのテスト(IS05仕様書7節)。"""

from __future__ import annotations

import inspect
import unittest
from datetime import UTC, datetime

from command_router import router as router_module
from command_router.errors import DispatchTargetNotRegisteredError, UnknownCommandError
from command_router.models import (
    CommandType,
    DestinationModule,
    NormalizedCommand,
    RawCommand,
    RoutedCommand,
)
from command_router.router import CommandRouter
from foundation.errors import ExternalServiceError
from foundation.result import Result


def _make_raw(command: str, source: str = "cli") -> RawCommand:
    return RawCommand(
        command_id="cmd-1",
        source=source,
        user_id="user-1",
        timestamp=datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC),
        command=command,
    )


def _make_normalized(raw_text: str, source: str = "cli") -> NormalizedCommand:
    return NormalizedCommand(
        command_id="cmd-1",
        source=source,
        user_id="user-1",
        timestamp=datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC),
        raw_text=raw_text,
    )


def _split_payload(raw_text: str) -> str:
    parts = raw_text.strip().split(None, 1)
    return parts[1] if len(parts) > 1 else ""


def _make_routed(raw_text: str, command_type: CommandType, destination: DestinationModule) -> RoutedCommand:
    normalized = _make_normalized(raw_text)
    return RoutedCommand(
        normalized=normalized,
        command_type=command_type,
        payload=_split_payload(raw_text),
        destination=destination,
    )


class _RecordingHandler:
    def __init__(self, result: Result) -> None:
        self.result = result
        self.calls: list[RoutedCommand] = []

    def __call__(self, command: RoutedCommand) -> Result:
        self.calls.append(command)
        return self.result


class TestCommandRouterBasics(unittest.TestCase):
    def test_name_returns_command_router(self) -> None:
        router = CommandRouter(handlers={})
        self.assertEqual(router.name(), "command_router")

    def test_health_check_returns_success_true(self) -> None:
        router = CommandRouter(handlers={})
        result = router.health_check()
        self.assertTrue(result.success)
        self.assertTrue(result.value)


class TestCommandRouterClassify(unittest.TestCase):
    def setUp(self) -> None:
        self.router = CommandRouter(handlers={})

    def test_classify_plan_command_returns_command_type_plan(self) -> None:
        result = self.router.classify(_make_normalized("plan LP改善"))
        self.assertTrue(result.success)
        self.assertEqual(result.value, CommandType.PLAN)

    def test_classify_design_command_returns_command_type_design(self) -> None:
        result = self.router.classify(_make_normalized("design new schema"))
        self.assertTrue(result.success)
        self.assertEqual(result.value, CommandType.DESIGN)

    def test_classify_implement_command_returns_command_type_implement(self) -> None:
        result = self.router.classify(_make_normalized("implement feature X"))
        self.assertTrue(result.success)
        self.assertEqual(result.value, CommandType.IMPLEMENT)

    def test_classify_review_command_returns_command_type_review(self) -> None:
        result = self.router.classify(_make_normalized("review PR 123"))
        self.assertTrue(result.success)
        self.assertEqual(result.value, CommandType.REVIEW)

    def test_classify_status_command_returns_command_type_status(self) -> None:
        result = self.router.classify(_make_normalized("status"))
        self.assertTrue(result.success)
        self.assertEqual(result.value, CommandType.STATUS)

    def test_classify_help_command_returns_command_type_help(self) -> None:
        result = self.router.classify(_make_normalized("help"))
        self.assertTrue(result.success)
        self.assertEqual(result.value, CommandType.HELP)

    def test_classify_is_case_insensitive(self) -> None:
        result = self.router.classify(_make_normalized("PlAn something"))
        self.assertTrue(result.success)
        self.assertEqual(result.value, CommandType.PLAN)

    def test_classify_unrecognized_keyword_returns_command_type_unknown(self) -> None:
        result = self.router.classify(_make_normalized("foobar something"))
        self.assertTrue(result.success)
        self.assertEqual(result.value, CommandType.UNKNOWN)


class TestCommandRouterRoute(unittest.TestCase):
    def setUp(self) -> None:
        self.router = CommandRouter(handlers={})

    def test_route_status_returns_state_manager_not_scheduler(self) -> None:
        result = self.router.route(CommandType.STATUS)
        self.assertTrue(result.success)
        self.assertEqual(result.value, DestinationModule.STATE_MANAGER)
        self.assertNotEqual(result.value.value, "Scheduler")

    def test_route_unknown_command_type_returns_error_result(self) -> None:
        result = self.router.route(CommandType.UNKNOWN)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, UnknownCommandError)


class TestCommandRouterDispatch(unittest.TestCase):
    def test_dispatch_calls_registered_handler_for_destination(self) -> None:
        handler = _RecordingHandler(Result(success=True, value="ok"))
        router = CommandRouter(handlers={DestinationModule.PLANNER: handler})
        routed = _make_routed("plan LP改善", CommandType.PLAN, DestinationModule.PLANNER)

        result = router.dispatch(DestinationModule.PLANNER, routed)

        self.assertEqual(len(handler.calls), 1)
        self.assertIs(handler.calls[0], routed)
        self.assertTrue(result.success)
        self.assertEqual(result.value.command_id, "cmd-1")
        self.assertEqual(result.value.destination, DestinationModule.PLANNER)
        self.assertTrue(result.value.accepted)

    def test_dispatch_returns_error_when_handler_not_registered(self) -> None:
        router = CommandRouter(handlers={})
        routed = _make_routed("plan LP改善", CommandType.PLAN, DestinationModule.PLANNER)

        result = router.dispatch(DestinationModule.PLANNER, routed)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, DispatchTargetNotRegisteredError)

    def test_dispatch_propagates_handler_result_without_modification(self) -> None:
        handler_error = ExternalServiceError("planner backend unavailable")
        handler = _RecordingHandler(Result(success=False, value=None, error=handler_error))
        router = CommandRouter(handlers={DestinationModule.PLANNER: handler})
        routed = _make_routed("plan LP改善", CommandType.PLAN, DestinationModule.PLANNER)

        result = router.dispatch(DestinationModule.PLANNER, routed)

        self.assertFalse(result.success)
        self.assertIs(result.error, handler_error)

    def test_dispatch_does_not_invoke_github_or_slack_side_effects(self) -> None:
        # router.py はimport文レベルでGitHub API/Slack SDK等の外部通信ライブラリに
        # 依存してはならない(4.4節: Routerは転送専用)。docstring上の説明文言
        # (「GitHub API呼び出し」等、制約を説明するコメント)は対象外とし、実際の
        # import文のみを検査する。
        import_lines = [
            line.strip()
            for line in inspect.getsource(router_module).splitlines()
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        forbidden_modules = ["requests", "github", "slack_sdk", "httpx", "urllib", "socket"]
        for line in import_lines:
            for forbidden in forbidden_modules:
                self.assertNotIn(
                    forbidden,
                    line,
                    f"router.py must not import network/external-service libraries: {line!r}",
                )

        handler = _RecordingHandler(Result(success=True, value="ok"))
        router = CommandRouter(handlers={DestinationModule.PLANNER: handler})
        routed = _make_routed("plan LP改善", CommandType.PLAN, DestinationModule.PLANNER)

        router.dispatch(DestinationModule.PLANNER, routed)

        # 登録済みhandler以外は一切呼び出されない(転送専用: 4.4節)。
        self.assertEqual(len(handler.calls), 1)


class TestCommandRouterFullPipeline(unittest.TestCase):
    def test_full_pipeline_plan_command_reaches_planner_handler(self) -> None:
        handler = _RecordingHandler(Result(success=True, value="accepted"))
        router = CommandRouter(handlers={DestinationModule.PLANNER: handler})

        raw = _make_raw("/plan LP改善", source="slack")
        normalized_result = router.receive(raw)
        self.assertTrue(normalized_result.success)

        classify_result = router.classify(normalized_result.value)
        self.assertEqual(classify_result.value, CommandType.PLAN)

        route_result = router.route(classify_result.value)
        self.assertEqual(route_result.value, DestinationModule.PLANNER)

        routed = RoutedCommand(
            normalized=normalized_result.value,
            command_type=classify_result.value,
            payload=_split_payload(normalized_result.value.raw_text),
            destination=route_result.value,
        )
        dispatch_result = router.dispatch(route_result.value, routed)

        self.assertTrue(dispatch_result.success)
        self.assertEqual(len(handler.calls), 1)
        self.assertEqual(handler.calls[0].payload, "LP改善")

    def test_full_pipeline_unknown_command_is_not_dispatched(self) -> None:
        handler = _RecordingHandler(Result(success=True, value="ok"))
        router = CommandRouter(
            handlers={
                DestinationModule.PLANNER: handler,
                DestinationModule.DESIGNER: handler,
                DestinationModule.EXECUTOR: handler,
                DestinationModule.REVIEWER: handler,
                DestinationModule.STATE_MANAGER: handler,
                DestinationModule.SYSTEM: handler,
            }
        )

        raw = _make_raw("foobar something", source="cli")
        normalized_result = router.receive(raw)
        classify_result = router.classify(normalized_result.value)
        self.assertEqual(classify_result.value, CommandType.UNKNOWN)

        route_result = router.route(classify_result.value)
        self.assertFalse(route_result.success)
        self.assertIsInstance(route_result.error, UnknownCommandError)

        # route()が失敗した時点で呼び出し元はdispatch()を呼び出してはならない。
        self.assertEqual(len(handler.calls), 0)

    def test_full_pipeline_status_command_never_calls_scheduler_handler(self) -> None:
        state_manager_handler = _RecordingHandler(Result(success=True, value="ok"))
        router = CommandRouter(handlers={DestinationModule.STATE_MANAGER: state_manager_handler})

        # DestinationModuleにSchedulerは存在しない(Design Freeze是正事項)。
        self.assertNotIn("Scheduler", [d.value for d in DestinationModule])

        raw = _make_raw("status", source="cli")
        normalized_result = router.receive(raw)
        classify_result = router.classify(normalized_result.value)
        self.assertEqual(classify_result.value, CommandType.STATUS)

        route_result = router.route(classify_result.value)
        self.assertEqual(route_result.value, DestinationModule.STATE_MANAGER)

        routed = RoutedCommand(
            normalized=normalized_result.value,
            command_type=classify_result.value,
            payload=_split_payload(normalized_result.value.raw_text),
            destination=route_result.value,
        )
        dispatch_result = router.dispatch(route_result.value, routed)

        self.assertTrue(dispatch_result.success)
        self.assertEqual(len(state_manager_handler.calls), 1)


class TestCommandRouterLogging(unittest.TestCase):
    def test_logging_does_not_output_metadata_values(self) -> None:
        handler = _RecordingHandler(Result(success=True, value="ok"))
        router = CommandRouter(handlers={DestinationModule.PLANNER: handler})

        raw = RawCommand(
            command_id="cmd-1",
            source="cli",
            user_id="user-1",
            timestamp=datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC),
            command="plan LP改善 with secret",
            metadata={"api_token": "SECRET_TOKEN_XYZ"},
        )

        with self.assertLogs("command_router", level="INFO") as cm:
            normalized_result = router.receive(raw)
            classify_result = router.classify(normalized_result.value)
            route_result = router.route(classify_result.value)
            routed = RoutedCommand(
                normalized=normalized_result.value,
                command_type=classify_result.value,
                payload=_split_payload(normalized_result.value.raw_text),
                destination=route_result.value,
            )
            router.dispatch(route_result.value, routed)

        combined_output = "\n".join(cm.output)
        self.assertNotIn("SECRET_TOKEN_XYZ", combined_output)
        self.assertNotIn("LP改善 with secret", combined_output)

    def test_logging_records_required_six_fields(self) -> None:
        handler = _RecordingHandler(Result(success=True, value="ok"))
        router = CommandRouter(handlers={DestinationModule.PLANNER: handler})

        raw = _make_raw("plan LP改善", source="cli")

        with self.assertLogs("command_router", level="INFO") as cm:
            normalized_result = router.receive(raw)
            classify_result = router.classify(normalized_result.value)
            route_result = router.route(classify_result.value)
            routed = RoutedCommand(
                normalized=normalized_result.value,
                command_type=classify_result.value,
                payload=_split_payload(normalized_result.value.raw_text),
                destination=route_result.value,
            )
            router.dispatch(route_result.value, routed)

        self.assertGreater(len(cm.records), 0)
        combined_output = "\n".join(cm.output)
        for field_marker in (
            "source=",
            "command=",
            "command_type=",
            "destination=",
            "result=",
        ):
            self.assertIn(field_marker, combined_output)
        # timestamp: 各LogRecordはcreated(タイムスタンプ)を必ず保持する
        # (loggingのデフォルトフォーマッタに委譲: 6節)。
        for record in cm.records:
            self.assertTrue(hasattr(record, "created"))


if __name__ == "__main__":
    unittest.main()
