import unittest
from types import SimpleNamespace

from foundation.types import Implementation
from pr_creator.models import PullRequestTemplate
from pr_creator.template import build_template, build_title, render


class PullRequestTemplateTestCase(unittest.TestCase):
    def _full_template(self) -> PullRequestTemplate:
        return PullRequestTemplate(
            summary="ログイン機能を追加した。",
            purpose="ユーザー認証を可能にするため。",
            changes=["src/auth/login.py", "tests/auth/test_login.py"],
            test_result="全テストPASS(unit: 12, integration: 3)",
            related_issue="#123",
            notes="レビュー観点: セッション有効期限",
        )

    def test_render_contains_all_sections_in_fixed_order(self) -> None:
        rendered = render(self._full_template())
        headings = [
            "# Summary",
            "## Purpose",
            "## Changes",
            "## Test Result",
            "## Related Issue",
            "## Notes",
        ]
        indices = [rendered.index(heading) for heading in headings]
        self.assertEqual(indices, sorted(indices))

    def test_render_includes_summary_purpose_changes_test_result_related_issue_notes_headings(
        self,
    ) -> None:
        rendered = render(self._full_template())
        for heading in (
            "# Summary",
            "## Purpose",
            "## Changes",
            "## Test Result",
            "## Related Issue",
            "## Notes",
        ):
            self.assertIn(heading, rendered)

    def test_render_handles_empty_changes_list(self) -> None:
        template = PullRequestTemplate(
            summary="変更なし",
            purpose="動作確認のみ",
            changes=[],
            test_result="PASS",
            related_issue=None,
        )
        rendered = render(template)
        self.assertIn("## Changes", rendered)
        self.assertNotIn("None", rendered)

    def test_render_handles_missing_related_issue(self) -> None:
        template = PullRequestTemplate(
            summary="summary",
            purpose="purpose",
            changes=["a.py"],
            test_result="PASS",
            related_issue=None,
        )
        rendered = render(template)
        related_section = rendered.split("## Related Issue")[1].split("## Notes")[0]
        self.assertIn("N/A", related_section)

    def test_render_handles_missing_notes(self) -> None:
        template = PullRequestTemplate(
            summary="summary",
            purpose="purpose",
            changes=["a.py"],
            test_result="PASS",
            related_issue="#1",
            notes=None,
        )
        rendered = render(template)
        notes_section = rendered.split("## Notes")[1]
        self.assertIn("N/A", notes_section)

    def test_build_title_from_implementation_result_and_workflow_id(self) -> None:
        implementation_result = Implementation(metadata={"title": "ログイン機能の追加"})
        title = build_title(implementation_result, "WF-2026-001")
        self.assertIn("WF-2026-001", title)
        self.assertIn("ログイン機能の追加", title)

    def test_build_title_reads_metadata_from_implementation_result_implementation_attribute(self) -> None:
        """実際のExecutor成果物(`executor.models.ImplementationResult`)は`.implementation`に
        Foundation `Implementation`を保持する(2026-07 統合レビューの是正)。"""
        implementation_result = SimpleNamespace(implementation=Implementation(metadata={"title": "決済機能の追加"}))
        title = build_title(implementation_result, "WF-2026-002")
        self.assertIn("WF-2026-002", title)
        self.assertIn("決済機能の追加", title)

    def test_build_template_uses_modified_files_from_implementation_result(self) -> None:
        """変更ファイル一覧はExecutorの`ImplementationResult.modified_files`から取得する
        (`Implementation.metadata`には件数しか含まれないため)。"""
        modified_files = [
            SimpleNamespace(path="src/auth/login.py"),
            SimpleNamespace(path="tests/auth/test_login.py"),
        ]
        implementation_result = SimpleNamespace(
            implementation=Implementation(metadata={"summary": "ログイン機能を追加", "purpose": "認証を可能にする"}),
            modified_files=modified_files,
        )
        test_report = SimpleNamespace(summary="Quality Gate PASS: 6/6 item(s) passed.")

        pr_template = build_template(implementation_result, test_report, {})

        self.assertEqual(pr_template.changes, ["src/auth/login.py", "tests/auth/test_login.py"])
        self.assertEqual(pr_template.summary, "ログイン機能を追加")
        self.assertEqual(pr_template.purpose, "認証を可能にする")
        self.assertEqual(pr_template.test_result, "Quality Gate PASS: 6/6 item(s) passed.")

    def test_build_template_uses_test_report_summary_for_test_result(self) -> None:
        implementation_result = Implementation(metadata={})
        test_report = SimpleNamespace(summary="Quality Gate FAIL: 5/6 item(s) passed.")

        pr_template = build_template(implementation_result, test_report, {})

        self.assertEqual(pr_template.test_result, "Quality Gate FAIL: 5/6 item(s) passed.")

    def test_build_template_falls_back_to_passed_when_test_report_summary_missing(self) -> None:
        implementation_result = Implementation(metadata={})
        test_report = SimpleNamespace()

        pr_template = build_template(implementation_result, test_report, {})

        self.assertEqual(pr_template.test_result, "PASSED")

    def test_build_template_falls_back_to_metadata_changed_files_when_modified_files_absent(self) -> None:
        """`modified_files`を持たない(Foundation `Implementation`のみの)場合は、
        後方互換として`metadata["changed_files"]`を参照する。"""
        implementation_result = Implementation(metadata={"changed_files": ["a.py"]})
        test_report = SimpleNamespace(summary="PASSED")

        pr_template = build_template(implementation_result, test_report, {})

        self.assertEqual(pr_template.changes, ["a.py"])


if __name__ == "__main__":
    unittest.main()
