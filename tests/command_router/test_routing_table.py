"""routing_table.resolve_destination()のテスト(IS05仕様書7節)。"""

from __future__ import annotations

import unittest

from command_router.errors import UnknownCommandError
from command_router.models import CommandType, DestinationModule
from command_router.routing_table import ROUTING_TABLE, resolve_destination
from foundation.result import Result


class _FakeConfigClient:
    """ConfigurationClient(F03)の最小限のテスト用フェイク。"""

    def __init__(self, override: dict[CommandType, DestinationModule] | None) -> None:
        self._override = override

    def get(self, module_name: str, key: str) -> Result[dict]:
        if self._override is None:
            return Result(success=False, value=None, error=None)
        return Result(success=True, value=self._override, error=None)


class TestRoutingTable(unittest.TestCase):
    def test_resolve_destination_plan_maps_to_planner(self) -> None:
        result = resolve_destination(CommandType.PLAN)
        self.assertTrue(result.success)
        self.assertEqual(result.value, DestinationModule.PLANNER)

    def test_resolve_destination_design_maps_to_designer(self) -> None:
        result = resolve_destination(CommandType.DESIGN)
        self.assertTrue(result.success)
        self.assertEqual(result.value, DestinationModule.DESIGNER)

    def test_resolve_destination_implement_maps_to_executor(self) -> None:
        result = resolve_destination(CommandType.IMPLEMENT)
        self.assertTrue(result.success)
        self.assertEqual(result.value, DestinationModule.EXECUTOR)

    def test_resolve_destination_review_maps_to_reviewer(self) -> None:
        result = resolve_destination(CommandType.REVIEW)
        self.assertTrue(result.success)
        self.assertEqual(result.value, DestinationModule.REVIEWER)

    def test_resolve_destination_status_maps_to_state_manager(self) -> None:
        result = resolve_destination(CommandType.STATUS)
        self.assertTrue(result.success)
        self.assertEqual(result.value, DestinationModule.STATE_MANAGER)

    def test_resolve_destination_help_maps_to_system(self) -> None:
        result = resolve_destination(CommandType.HELP)
        self.assertTrue(result.success)
        self.assertEqual(result.value, DestinationModule.SYSTEM)

    def test_resolve_destination_unknown_returns_error_result(self) -> None:
        result = resolve_destination(CommandType.UNKNOWN)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, UnknownCommandError)

    def test_routing_table_does_not_contain_scheduler_destination(self) -> None:
        destination_values = [d.value for d in DestinationModule]
        self.assertNotIn("Scheduler", destination_values)
        self.assertNotIn("Scheduler", [d.value for d in ROUTING_TABLE.values()])

    def test_resolve_destination_uses_configuration_client_override_when_present(
        self,
    ) -> None:
        override = {CommandType.PLAN: DestinationModule.REVIEWER}
        config_client = _FakeConfigClient(override)
        result = resolve_destination(CommandType.PLAN, config_client)
        self.assertTrue(result.success)
        self.assertEqual(result.value, DestinationModule.REVIEWER)

    def test_resolve_destination_falls_back_to_static_table_when_config_client_unavailable(
        self,
    ) -> None:
        config_client = _FakeConfigClient(override=None)
        result = resolve_destination(CommandType.PLAN, config_client)
        self.assertTrue(result.success)
        self.assertEqual(result.value, DestinationModule.PLANNER)

        result_no_client = resolve_destination(CommandType.PLAN, None)
        self.assertTrue(result_no_client.success)
        self.assertEqual(result_no_client.value, DestinationModule.PLANNER)


if __name__ == "__main__":
    unittest.main()
