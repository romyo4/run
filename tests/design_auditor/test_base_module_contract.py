import unittest
from typing import Any

from design_auditor.module import DesignAuditor
from foundation.errors import ConfigurationError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result


class FakeConfigurationClient(ConfigurationClient):
    @staticmethod
    def get(module_name: str, key: str) -> Result[Any]:
        return Result(success=True, value=True)


class FailingConfigurationClient(ConfigurationClient):
    @staticmethod
    def get(module_name: str, key: str) -> Result[Any]:
        return Result(success=False, error=ConfigurationError("config_clientに接続できない"))


class DesignAuditorNameTest(unittest.TestCase):
    def test_name_returns_design_auditor(self) -> None:
        module = DesignAuditor(FakeConfigurationClient())
        self.assertEqual(module.name(), "design_auditor")


class DesignAuditorHealthCheckTest(unittest.TestCase):
    def test_health_check_returns_success_result_when_config_client_reachable(self) -> None:
        module = DesignAuditor(FakeConfigurationClient())

        result = module.health_check()

        self.assertTrue(result.success)
        self.assertTrue(result.value)

    def test_health_check_returns_failure_result_when_config_client_unreachable(
        self,
    ) -> None:
        module = DesignAuditor(FailingConfigurationClient())

        result = module.health_check()

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ConfigurationError)


class DesignAuditorScopeTest(unittest.TestCase):
    def test_module_has_no_code_generation_or_github_api(self) -> None:
        """4.3 Auditorは実装しない: コード生成・GitHub操作・PR作成用のpublicメソッドを持たない。"""
        module = DesignAuditor(FakeConfigurationClient())

        forbidden_members = (
            "generate_code",
            "create_pull_request",
            "modify_code",
            "apply_fix",
            "update_code",
            "merge_pull_request",
            "generate_design",
            "fix_design",
        )
        for member in forbidden_members:
            self.assertFalse(
                hasattr(module, member),
                msg=f"DesignAuditor must not expose '{member}'",
            )

        public_methods = {name for name in dir(module) if not name.startswith("_") and callable(getattr(module, name))}
        self.assertEqual(
            public_methods,
            {
                "name",
                "health_check",
                "audit",
                "validate_architecture",
                "check_mvp",
                "publish_result",
            },
        )


if __name__ == "__main__":
    unittest.main()
