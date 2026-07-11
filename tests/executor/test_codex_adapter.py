import tempfile
import unittest
from pathlib import Path

from executor.errors import CodexGenerationError
from executor.models import ChangeType, GeneratedTest, ModifiedFile
from tests.executor.fakes import FakeCodexAdapter, make_context


class CodexAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.context = make_context(self.tmp_root)

    def test_generate_implementation_returns_modified_files_on_success(self) -> None:
        modified_files = (ModifiedFile(Path("src/foo.py"), ChangeType.CREATED, "add foo"),)
        adapter = FakeCodexAdapter(modified_files=modified_files)

        result = adapter.generate_implementation(self.context)

        self.assertTrue(result.success)
        self.assertEqual(result.value, modified_files)
        self.assertIsNone(result.error)

    def test_generate_implementation_returns_error_result_on_external_failure(self) -> None:
        adapter = FakeCodexAdapter(fail_generate_implementation=True)

        result = adapter.generate_implementation(self.context)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, CodexGenerationError)

    def test_generate_tests_returns_generated_tests_on_success(self) -> None:
        generated_tests = (GeneratedTest(Path("tests/test_foo.py"), Path("src/foo.py"), "test foo"),)
        adapter = FakeCodexAdapter(generated_tests=generated_tests)

        result = adapter.generate_tests(self.context, ())

        self.assertTrue(result.success)
        self.assertEqual(result.value, generated_tests)

    def test_generate_tests_returns_error_result_on_external_failure(self) -> None:
        adapter = FakeCodexAdapter(fail_generate_tests=True)

        result = adapter.generate_tests(self.context, ())

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, CodexGenerationError)

    def test_codex_adapter_does_not_log_credentials(self) -> None:
        secret = "sk-super-secret-token-do-not-log"
        context = make_context(self.tmp_root, project_context={"api_key": secret})
        adapter = FakeCodexAdapter()

        with self.assertLogs("codex_adapter", level="INFO") as captured:
            adapter.generate_implementation(context)

        combined_output = "\n".join(captured.output)
        self.assertNotIn(secret, combined_output)


def _tmp_dir():
    import tempfile

    return tempfile.TemporaryDirectory()


if __name__ == "__main__":
    unittest.main()
