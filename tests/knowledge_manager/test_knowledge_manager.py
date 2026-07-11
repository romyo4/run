"""Knowledge Manager (M03) のunittestテストケース(IS03 7章)。"""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

import knowledge_manager.search_index as search_index_module
from foundation.errors import NotFoundError, PermissionDeniedError, ValidationError
from knowledge_manager import (
    KnowledgeCategory,
    KnowledgeDocument,
    KnowledgeManager,
    KnowledgeStatus,
    KnowledgeStore,
)
from knowledge_manager.exceptions import (
    KnowledgeDocumentNotFoundError,
    KnowledgeUpdatePermissionDeniedError,
    KnowledgeVersionConflictError,
)


def _write_markdown(
    directory: Path,
    *,
    filename: str = "business_goal.md",
    document_id: str | None = None,
    category: str | None = "business_goal",
    title: str | None = "プロジェクトのビジネスゴール",
    tags: str | None = "core, mvp",
    content: str = "本文はここから始まる。\n複数行に渡ってよい。",
) -> Path:
    lines: list[str] = []
    if document_id is not None:
        lines.append(f"Document_id: {document_id}")
    if category is not None:
        lines.append(f"Category: {category}")
    if title is not None:
        lines.append(f"Title: {title}")
    if tags is not None:
        lines.append(f"Tags: {tags}")
    lines.append("")
    lines.append(content)

    path = directory / filename
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


class KnowledgeManagerTestBase(unittest.TestCase):
    def _make_manager(self) -> KnowledgeManager:
        return KnowledgeManager(KnowledgeStore())

    def _seed(
        self,
        manager: KnowledgeManager,
        document_id: str,
        *,
        category: KnowledgeCategory = KnowledgeCategory.BUSINESS_GOAL,
        title: str = "タイトル",
        content: str = "本文",
        version: int = 1,
        status: KnowledgeStatus = KnowledgeStatus.CURRENT,
        tags: list[str] | None = None,
        updated_by: str = "",
    ) -> KnowledgeDocument:
        document = KnowledgeDocument(
            document_id=document_id,
            category=category,
            title=title,
            content=content,
            version=version,
            status=status,
            tags=tags or [],
            updated_by=updated_by,
        )
        manager._store.add(document)
        return document


class TestKnowledgeManagerLoad(KnowledgeManagerTestBase):
    def test_load_valid_markdown_file_returns_success_result(self) -> None:
        manager = self._make_manager()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_markdown(Path(tmp_dir))

            result = manager.load(path)

            self.assertTrue(result.success, msg=result.error)
            assert result.value is not None
            self.assertEqual(result.value.title, "プロジェクトのビジネスゴール")
            self.assertEqual(result.value.category, KnowledgeCategory.BUSINESS_GOAL)

    def test_load_missing_file_returns_not_found_error(self) -> None:
        manager = self._make_manager()
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_path = Path(tmp_dir) / "does_not_exist.md"

            result = manager.load(missing_path)

            self.assertFalse(result.success)
            self.assertIsInstance(result.error, NotFoundError)

    def test_load_missing_category_section_returns_validation_error(self) -> None:
        manager = self._make_manager()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_markdown(Path(tmp_dir), category=None)

            result = manager.load(path)

            self.assertFalse(result.success)
            self.assertIsInstance(result.error, ValidationError)

    def test_load_assigns_initial_version_number_one(self) -> None:
        manager = self._make_manager()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_markdown(Path(tmp_dir))

            result = manager.load(path)

            assert result.value is not None
            self.assertEqual(result.value.version, 1)

    def test_load_sets_status_current(self) -> None:
        manager = self._make_manager()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_markdown(Path(tmp_dir))

            result = manager.load(path)

            assert result.value is not None
            self.assertEqual(result.value.status, KnowledgeStatus.CURRENT)


class TestKnowledgeManagerGet(KnowledgeManagerTestBase):
    def test_get_existing_document_returns_success(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1", title="タイトル1")

        result = manager.get("doc-1")

        self.assertTrue(result.success, msg=result.error)
        assert result.value is not None
        self.assertEqual(result.value.document_id, "doc-1")

    def test_get_nonexistent_document_returns_not_found_error(self) -> None:
        manager = self._make_manager()

        result = manager.get("does-not-exist")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, NotFoundError)

    def test_get_without_version_qualifier_returns_latest_version(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1", version=1, status=KnowledgeStatus.ARCHIVED)
        self._seed(manager, "doc-1", version=2, status=KnowledgeStatus.CURRENT)

        result = manager.get("doc-1")

        self.assertTrue(result.success, msg=result.error)
        assert result.value is not None
        self.assertEqual(result.value.version, 2)


class TestKnowledgeManagerGetLatest(KnowledgeManagerTestBase):
    def test_get_latest_returns_highest_version_number(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1", version=1, status=KnowledgeStatus.ARCHIVED)
        self._seed(manager, "doc-1", version=2, status=KnowledgeStatus.ARCHIVED)
        self._seed(manager, "doc-1", version=3, status=KnowledgeStatus.CURRENT)

        result = manager.get_latest("doc-1")

        self.assertTrue(result.success, msg=result.error)
        assert result.value is not None
        self.assertEqual(result.value.version, 3)

    def test_get_latest_nonexistent_document_returns_not_found_error(self) -> None:
        manager = self._make_manager()

        result = manager.get_latest("does-not-exist")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, NotFoundError)

    def test_get_latest_reflects_recently_created_version(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1", version=1, content="旧内容")

        create_result = manager.create_version("doc-1", "新内容")
        self.assertTrue(create_result.success, msg=create_result.error)

        result = manager.get_latest("doc-1")

        assert result.value is not None
        self.assertEqual(result.value.version, 2)
        self.assertEqual(result.value.content, "新内容")


class TestKnowledgeManagerSearch(KnowledgeManagerTestBase):
    def test_search_keyword_in_title_returns_matching_documents(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1", title="Business Goal Overview", content="内容")
        self._seed(manager, "doc-2", title="Other", content="内容")

        result = manager.search("Business")

        self.assertTrue(result.success, msg=result.error)
        assert result.value is not None
        document_ids = {document.document_id for document in result.value}
        self.assertEqual(document_ids, {"doc-1"})

    def test_search_keyword_in_content_returns_matching_documents(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1", title="タイトル", content="これはコーディングルールに関する説明です。")
        self._seed(manager, "doc-2", title="タイトル", content="無関係な内容")

        result = manager.search("コーディングルール")

        assert result.value is not None
        document_ids = {document.document_id for document in result.value}
        self.assertEqual(document_ids, {"doc-1"})

    def test_search_no_match_returns_empty_list_not_error(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1", title="タイトル", content="内容")

        result = manager.search("該当しないキーワード")

        self.assertTrue(result.success, msg=result.error)
        self.assertEqual(result.value, [])

    def test_search_is_case_insensitive(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1", title="Architecture Principles", content="内容")

        result = manager.search("architecture")

        assert result.value is not None
        document_ids = {document.document_id for document in result.value}
        self.assertEqual(document_ids, {"doc-1"})

    def test_search_does_not_depend_on_embedding_or_vector_store(self) -> None:
        # ドキュメンテーション文字列上で「使用しない」旨に言及することは許容し、
        # 実際のimport文にVector Database/Embedding系ライブラリが含まれていないことのみを検査する。
        import_lines = [
            line.strip()
            for line in inspect.getsource(search_index_module).splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        forbidden_terms = ("numpy", "embedding", "vector", "faiss", "sentence_transformers")
        for line in import_lines:
            for term in forbidden_terms:
                with self.subTest(line=line, term=term):
                    self.assertNotIn(term, line.lower())


class TestKnowledgeManagerListDocuments(KnowledgeManagerTestBase):
    def test_list_documents_filters_by_category(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1", category=KnowledgeCategory.CODING_RULES)
        self._seed(manager, "doc-2", category=KnowledgeCategory.BUSINESS_GOAL)

        result = manager.list_documents(KnowledgeCategory.CODING_RULES)

        self.assertTrue(result.success, msg=result.error)
        assert result.value is not None
        document_ids = {document.document_id for document in result.value}
        self.assertEqual(document_ids, {"doc-1"})

    def test_list_documents_unknown_category_returns_empty_list(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1", category=KnowledgeCategory.CODING_RULES)

        result = manager.list_documents(KnowledgeCategory.MVP_POLICY)

        self.assertTrue(result.success, msg=result.error)
        self.assertEqual(result.value, [])

    def test_list_documents_returns_only_current_status_per_document_id(self) -> None:
        manager = self._make_manager()
        self._seed(
            manager,
            "doc-1",
            category=KnowledgeCategory.DEVELOPMENT_RULES,
            version=1,
            status=KnowledgeStatus.ARCHIVED,
        )
        self._seed(
            manager,
            "doc-1",
            category=KnowledgeCategory.DEVELOPMENT_RULES,
            version=2,
            status=KnowledgeStatus.CURRENT,
        )

        result = manager.list_documents(KnowledgeCategory.DEVELOPMENT_RULES)

        assert result.value is not None
        self.assertEqual(len(result.value), 1)
        self.assertEqual(result.value[0].version, 2)


class TestKnowledgeManagerUpdate(KnowledgeManagerTestBase):
    def _make_update_document(
        self, existing: KnowledgeDocument, *, updated_by: str, version: int | None = None
    ) -> KnowledgeDocument:
        return KnowledgeDocument(
            document_id=existing.document_id,
            category=existing.category,
            title="更新後タイトル",
            content="更新後内容",
            version=existing.version if version is None else version,
            tags=existing.tags,
            updated_by=updated_by,
        )

    def test_update_by_planner_role_succeeds(self) -> None:
        manager = self._make_manager()
        existing = self._seed(manager, "doc-1")

        result = manager.update(self._make_update_document(existing, updated_by="planner"))

        self.assertTrue(result.success, msg=result.error)

    def test_update_by_architect_role_succeeds(self) -> None:
        manager = self._make_manager()
        existing = self._seed(manager, "doc-1")

        result = manager.update(self._make_update_document(existing, updated_by="architect"))

        self.assertTrue(result.success, msg=result.error)

    def test_update_by_reviewer_role_succeeds(self) -> None:
        manager = self._make_manager()
        existing = self._seed(manager, "doc-1")

        result = manager.update(self._make_update_document(existing, updated_by="reviewer"))

        self.assertTrue(result.success, msg=result.error)

    def test_update_by_executor_role_returns_permission_denied_error(self) -> None:
        manager = self._make_manager()
        existing = self._seed(manager, "doc-1")

        result = manager.update(self._make_update_document(existing, updated_by="executor"))

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, PermissionDeniedError)
        self.assertIsInstance(result.error, KnowledgeUpdatePermissionDeniedError)

    def test_update_by_context_manager_role_returns_permission_denied_error(self) -> None:
        manager = self._make_manager()
        existing = self._seed(manager, "doc-1")

        result = manager.update(self._make_update_document(existing, updated_by="context_manager"))

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, PermissionDeniedError)

    def test_update_with_stale_version_returns_version_conflict_error(self) -> None:
        manager = self._make_manager()
        existing = self._seed(manager, "doc-1", version=2)

        stale_document = self._make_update_document(existing, updated_by="planner", version=1)
        result = manager.update(stale_document)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, KnowledgeVersionConflictError)

    def test_update_with_latest_version_succeeds_and_preserves_history(self) -> None:
        manager = self._make_manager()
        existing = self._seed(manager, "doc-1", version=1, content="旧内容")

        result = manager.update(self._make_update_document(existing, updated_by="planner"))

        self.assertTrue(result.success, msg=result.error)
        assert result.value is not None
        self.assertEqual(result.value.version, 2)

        previous_version = manager._store.get_version("doc-1", 1)
        assert previous_version is not None
        self.assertEqual(previous_version.content, "旧内容")
        self.assertEqual(previous_version.status, KnowledgeStatus.ARCHIVED)

    def test_update_persists_new_content_hash(self) -> None:
        manager = self._make_manager()
        existing = self._seed(manager, "doc-1", content="旧内容")

        result = manager.update(self._make_update_document(existing, updated_by="planner"))

        assert result.value is not None
        self.assertNotEqual(result.value.content_hash, existing.content_hash)
        self.assertNotEqual(result.value.content_hash, "")

    def test_update_nonexistent_document_returns_not_found_error(self) -> None:
        manager = self._make_manager()
        phantom = KnowledgeDocument(
            document_id="does-not-exist",
            category=KnowledgeCategory.BUSINESS_GOAL,
            title="タイトル",
            content="内容",
            version=1,
            updated_by="planner",
        )

        result = manager.update(phantom)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, KnowledgeDocumentNotFoundError)


class TestKnowledgeManagerCreateVersion(KnowledgeManagerTestBase):
    def test_create_version_increments_version_number(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1", version=1)

        result = manager.create_version("doc-1", "新しい内容")

        self.assertTrue(result.success, msg=result.error)
        assert result.value is not None
        self.assertEqual(result.value.version, 2)

    def test_create_version_marks_previous_version_as_archived(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1", version=1)

        manager.create_version("doc-1", "新しい内容")

        previous_version = manager._store.get_version("doc-1", 1)
        assert previous_version is not None
        self.assertEqual(previous_version.status, KnowledgeStatus.ARCHIVED)

    def test_create_version_keeps_previous_version_retrievable_by_get(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1", version=1, content="バージョン1の内容")

        manager.create_version("doc-1", "バージョン2の内容")

        result = manager.get("doc-1@1")

        self.assertTrue(result.success, msg=result.error)
        assert result.value is not None
        self.assertEqual(result.value.content, "バージョン1の内容")

    def test_create_version_nonexistent_document_returns_not_found_error(self) -> None:
        manager = self._make_manager()

        result = manager.create_version("does-not-exist", "内容")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, KnowledgeDocumentNotFoundError)

    def test_create_version_updates_content_hash(self) -> None:
        manager = self._make_manager()
        existing = self._seed(manager, "doc-1", content="旧内容")

        result = manager.create_version("doc-1", "新しい内容")

        assert result.value is not None
        self.assertNotEqual(result.value.content_hash, existing.content_hash)
        self.assertNotEqual(result.value.content_hash, "")


class TestKnowledgeManagerLogging(KnowledgeManagerTestBase):
    SECRET_MARKER = "SECRET_CONTENT_MARKER_XYZ"

    def test_update_log_message_does_not_contain_document_content(self) -> None:
        manager = self._make_manager()
        existing = self._seed(manager, "doc-1", content="通常の内容")
        updated_document = KnowledgeDocument(
            document_id=existing.document_id,
            category=existing.category,
            title="タイトル",
            content=self.SECRET_MARKER,
            version=existing.version,
            updated_by="planner",
        )

        with self.assertLogs("knowledge_manager", level="INFO") as captured:
            manager.update(updated_document)

        combined_output = "\n".join(captured.output)
        self.assertNotIn(self.SECRET_MARKER, combined_output)

    def test_load_log_message_does_not_contain_document_content(self) -> None:
        manager = self._make_manager()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_markdown(Path(tmp_dir), content=self.SECRET_MARKER)

            with self.assertLogs("knowledge_manager", level="INFO") as captured:
                manager.load(path)

        combined_output = "\n".join(captured.output)
        self.assertNotIn(self.SECRET_MARKER, combined_output)

    def test_log_message_includes_operation_category_version_result(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "doc-1")

        with self.assertLogs("knowledge_manager", level="INFO") as captured:
            manager.get_latest("doc-1")

        combined_output = "\n".join(captured.output)
        self.assertIn("operation=", combined_output)
        self.assertIn("category=", combined_output)
        self.assertIn("version=", combined_output)
        self.assertIn("result=", combined_output)


class TestKnowledgeManagerHealthCheck(KnowledgeManagerTestBase):
    def test_health_check_returns_success_when_store_available(self) -> None:
        manager = self._make_manager()

        result = manager.health_check()

        self.assertTrue(result.success)
        self.assertTrue(result.value)


class TestKnowledgeCategoryAndStatusEnums(unittest.TestCase):
    def test_all_five_categories_are_defined(self) -> None:
        expected = {
            "business_goal",
            "mvp_policy",
            "architecture_principles",
            "development_rules",
            "coding_rules",
        }
        actual = {category.value for category in KnowledgeCategory}
        self.assertEqual(actual, expected)

    def test_category_enum_has_no_extra_members(self) -> None:
        self.assertEqual(len(list(KnowledgeCategory)), 5)


if __name__ == "__main__":
    unittest.main()
