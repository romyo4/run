"""Phase 1-A: github_smoke_test.pyの引数解析・エラーパスのテスト(実ネットワーク接続は行わない)。"""

import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from bootstrap.github_smoke_test import main


class GithubSmokeTestMainTest(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_main_returns_1_when_github_token_missing(self) -> None:
        buffer = io.StringIO()
        with redirect_stderr(buffer):
            exit_code = main(["owner/repo"])

        self.assertEqual(exit_code, 1)
        self.assertIn("GITHUB_TOKEN", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
