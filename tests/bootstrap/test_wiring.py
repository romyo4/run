"""Task 4: 21モジュールの実インスタンス化(`wiring.py`)のテスト。

`build_application()`が例外なく完了し、返された`Application`が保持する全モジュールの
`health_check()`が成功(Result.success=True かつ Result.value=True相当)を返すことを確認する。
"""

import unittest

from bootstrap.wiring import build_application


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


if __name__ == "__main__":
    unittest.main()
