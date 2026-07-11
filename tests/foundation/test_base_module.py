import unittest

from foundation.base_module import BaseModule
from foundation.result import Result


class ConcreteModule(BaseModule):
    def name(self) -> str:
        return "concrete"

    def health_check(self) -> Result[bool]:
        return Result(success=True, value=True)


class IncompleteModule(BaseModule):
    def name(self) -> str:
        return "incomplete"


class BaseModuleTest(unittest.TestCase):
    def test_base_module_cannot_be_instantiated_directly(self) -> None:
        with self.assertRaises(TypeError):
            BaseModule()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_name(self) -> None:
        with self.assertRaises(TypeError):
            IncompleteModule()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_health_check(self) -> None:
        module = ConcreteModule()
        self.assertEqual(module.name(), "concrete")

    def test_concrete_subclass_health_check_returns_result_bool(self) -> None:
        result = ConcreteModule().health_check()
        self.assertTrue(result.success)
        self.assertTrue(result.value)


if __name__ == "__main__":
    unittest.main()
