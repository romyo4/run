import unittest
from typing import Any

from foundation.errors import ConfigurationError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from reviewer.config import MODULE_NAME, get_reviewer_config


class FakeConfigurationClient(ConfigurationClient):
    """設定値取得を模擬するテスト用Fake。呼び出し引数を記録する。"""

    calls: list[tuple[str, str]] = []
    values: dict[str, Any] = {
        "min_business_score": 0.5,
        "blocker_severity_blocks_approval": True,
    }

    @staticmethod
    def get(module_name: str, key: str) -> Result[Any]:
        FakeConfigurationClient.calls.append((module_name, key))
        return Result(success=True, value=FakeConfigurationClient.values[key])


class FailingConfigurationClient(ConfigurationClient):
    @staticmethod
    def get(module_name: str, key: str) -> Result[Any]:
        return Result(success=False, error=ConfigurationError("configuration unavailable"))


class GetReviewerConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeConfigurationClient.calls = []

    def test_get_reviewer_config_returns_success_result(self) -> None:
        result = get_reviewer_config(FakeConfigurationClient())
        self.assertTrue(result.success)
        self.assertEqual(result.value.min_business_score, 0.5)
        self.assertTrue(result.value.blocker_severity_blocks_approval)

    def test_get_reviewer_config_uses_module_name_reviewer(self) -> None:
        get_reviewer_config(FakeConfigurationClient())
        self.assertTrue(FakeConfigurationClient.calls)
        for module_name, _key in FakeConfigurationClient.calls:
            self.assertEqual(module_name, MODULE_NAME)
            self.assertEqual(module_name, "reviewer")

    def test_get_reviewer_config_returns_failure_result_when_client_fails(self) -> None:
        result = get_reviewer_config(FailingConfigurationClient())
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ConfigurationError)


if __name__ == "__main__":
    unittest.main()
