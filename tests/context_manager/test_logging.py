import inspect
import unittest

from context_manager.logging_utils import log_build_result
from context_manager.types import AIContext, CollectedContext, SelectedContext, WorkflowType


class LogBuildResultOutputTest(unittest.TestCase):
    def test_log_build_result_outputs_required_fields_only(self) -> None:
        with self.assertLogs("context_manager", level="INFO") as captured:
            log_build_result(
                workflow_id="wf-1",
                workflow_type=WorkflowType.PLANNER,
                context_version="v1",
                context_size=3,
                validation_result=True,
            )

        self.assertEqual(len(captured.records), 1)
        message = captured.records[0].getMessage()
        self.assertIn("workflow_id=wf-1", message)
        self.assertIn("workflow_type=planner", message)
        self.assertIn("context_version=v1", message)
        self.assertIn("context_size=3", message)
        self.assertIn("validation_result=True", message)


class LogBuildResultSignatureTest(unittest.TestCase):
    def test_log_build_result_accepts_only_primitive_arguments(self) -> None:
        signature = inspect.signature(log_build_result)
        allowed_annotations = {str, WorkflowType, int, bool}
        for parameter in signature.parameters.values():
            self.assertIn(
                parameter.annotation,
                allowed_annotations,
                msg=f"{parameter.name} has non-primitive annotation {parameter.annotation!r}",
            )
        self.assertIs(signature.return_annotation, None)

    def test_log_build_result_does_not_accept_context_object_as_argument(self) -> None:
        signature = inspect.signature(log_build_result)
        disallowed = {AIContext, SelectedContext, CollectedContext}
        annotations = {parameter.annotation for parameter in signature.parameters.values()}
        self.assertEqual(annotations & disallowed, set())


if __name__ == "__main__":
    unittest.main()
