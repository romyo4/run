import unittest
from typing import Any

from foundation.interfaces import ConfigurationClient
from foundation.result import Result


class FakeConfigurationClient(ConfigurationClient):
    def get(self, module_name: str, key: str) -> Result[Any]:
        return Result(success=True, value=f"{module_name}.{key}")


class ConfigurationClientTest(unittest.TestCase):
    def test_configuration_client_cannot_be_instantiated_directly(self) -> None:
        with self.assertRaises(TypeError):
            ConfigurationClient()  # type: ignore[abstract]

    def test_configuration_client_subclass_get_returns_result(self) -> None:
        result = FakeConfigurationClient().get("state_manager", "storage_backend")
        self.assertTrue(result.success)
        self.assertEqual(result.value, "state_manager.storage_backend")


if __name__ == "__main__":
    unittest.main()
