"""Knowledge Manager(M03)本体(IS03 4.1/4.2節)。

Knowledgeの読込・取得・検索・更新・バージョン管理を担当する単一責務モジュール。
Context生成(Context Managerの責務)・Configuration管理・Workflow制御・Repository情報は
一切扱わない(設計書2.2/4.1/4.4節)。全メソッドは例外を送出せず`Result[T]`にラップして返す
(F02準拠)。
"""

from __future__ import annotations

from logging import Logger
from pathlib import Path

from foundation.base_module import BaseModule
from foundation.errors import NotFoundError, ValidationError
from foundation.logger import get_logger
from foundation.result import Result
from knowledge_manager.exceptions import (
    KnowledgeDocumentNotFoundError,
    KnowledgeUpdatePermissionDeniedError,
    KnowledgeVersionConflictError,
)
from knowledge_manager.markdown_loader import parse_markdown_source
from knowledge_manager.models import KnowledgeCategory, KnowledgeDocument, KnowledgeStatus
from knowledge_manager.permissions import is_update_allowed
from knowledge_manager.search_index import search_documents
from knowledge_manager.store import KnowledgeStore, compute_content_hash

MODULE_NAME = "knowledge_manager"

# get()の過去版参照(設計書3.4節/IS03 0節)で使う版指定の区切り文字。
# document_id自体にはこの文字を含めない運用とする。
_VERSION_QUALIFIER_SEPARATOR = "@"


def _split_version_qualifier(document_id: str) -> tuple[str, int | None]:
    """document_idから過去版参照の版指定(例: 'doc_id@2')を取り出す(IS03 0節)。

    版指定を含まない場合は (document_id, None) を返す。
    """
    if _VERSION_QUALIFIER_SEPARATOR not in document_id:
        return document_id, None
    base_id, _, version_part = document_id.rpartition(_VERSION_QUALIFIER_SEPARATOR)
    if base_id and version_part.isdigit():
        return base_id, int(version_part)
    return document_id, None


class KnowledgeManager(BaseModule):
    """Knowledgeの読込・取得・検索・更新・バージョン管理を担当する(設計書2.1)。"""

    def __init__(self, store: KnowledgeStore, logger: Logger | None = None) -> None:
        self._store = store
        self._logger: Logger = logger or get_logger(MODULE_NAME)

    # --- F02: BaseModule ---
    def name(self) -> str:
        return MODULE_NAME

    def health_check(self) -> Result[bool]:
        return Result(success=True, value=self._store is not None)

    # --- 設計書3.3: 公開インターフェース ---
    def load(self, source: Path) -> Result[KnowledgeDocument]:
        """Knowledgeソース(Markdownファイル)を読み込み、version=1のKnowledgeDocumentを生成する。"""
        try:
            parsed = parse_markdown_source(source)
        except NotFoundError as exc:
            self._log_operation("load", None, None, "not_found")
            return Result(success=False, error=exc)
        except ValidationError as exc:
            self._log_operation("load", None, None, "validation_error")
            return Result(success=False, error=exc)

        document = KnowledgeDocument(
            document_id=parsed.document_id,
            category=parsed.category,
            title=parsed.title,
            content=parsed.content,
            version=1,
            status=KnowledgeStatus.CURRENT,
            tags=list(parsed.tags),
            updated_by="",
            content_hash=compute_content_hash(parsed.content),
        )
        self._store.add(document)
        self._log_operation("load", document.category, document.version, "success")
        return Result(success=True, value=document)

    def get(self, document_id: str) -> Result[KnowledgeDocument]:
        """document_idに版指定(例: 'doc_id@2')が含まれる場合はその版を、無ければ最新版を返す。"""
        base_id, version = _split_version_qualifier(document_id)
        if version is None:
            return self.get_latest(document_id)

        document = self._store.get_version(base_id, version)
        if document is None:
            error = KnowledgeDocumentNotFoundError(f"knowledge document not found: {document_id}")
            self._log_operation("get", None, None, "not_found")
            return Result(success=False, error=error)

        self._log_operation("get", document.category, document.version, "success")
        return Result(success=True, value=document)

    def get_latest(self, document_id: str) -> Result[KnowledgeDocument]:
        """document_idの最新版(バージョン番号最大)を返す(3.4節: 最新版を既定で利用)。"""
        document = self._store.get_latest(document_id)
        if document is None:
            error = KnowledgeDocumentNotFoundError(f"knowledge document not found: {document_id}")
            self._log_operation("get_latest", None, None, "not_found")
            return Result(success=False, error=error)

        self._log_operation("get_latest", document.category, document.version, "success")
        return Result(success=True, value=document)

    def search(self, keyword: str) -> Result[list[KnowledgeDocument]]:
        """titleまたはcontentにkeywordが部分一致するCURRENT状態の文書一覧を返す(該当なしは空リスト)。"""
        documents = search_documents(self._store.all_current_documents(), keyword)
        return Result(success=True, value=documents)

    def list_documents(self, category: KnowledgeCategory) -> Result[list[KnowledgeDocument]]:
        """指定categoryに属するCURRENT状態の文書一覧を返す(該当なしは空リスト)。"""
        documents = [document for document in self._store.all_current_documents() if document.category == category]
        return Result(success=True, value=documents)

    def update(self, document: KnowledgeDocument) -> Result[KnowledgeDocument]:
        """既存文書を更新し新バージョンとして保存する(3.5節: Planner/Architect/Reviewerのみ許可)。"""
        existing = self._store.get_latest(document.document_id)
        if existing is None:
            error = KnowledgeDocumentNotFoundError(f"knowledge document not found: {document.document_id}")
            self._log_operation("update", document.category, document.version, "not_found")
            return Result(success=False, error=error)

        if not is_update_allowed(document.updated_by):
            error = KnowledgeUpdatePermissionDeniedError(
                f"role not allowed to update knowledge document: {document.updated_by!r}"
            )
            self._log_operation("update", existing.category, document.version, "permission_denied")
            return Result(success=False, error=error)

        if document.version != existing.version:
            error = KnowledgeVersionConflictError(
                "stale version for document_id="
                f"{document.document_id}: expected {existing.version}, got {document.version}"
            )
            self._log_operation("update", existing.category, document.version, "version_conflict")
            return Result(success=False, error=error)

        self._store.archive_latest(document.document_id)
        new_document = KnowledgeDocument(
            document_id=existing.document_id,
            category=document.category,
            title=document.title,
            content=document.content,
            version=existing.version + 1,
            status=KnowledgeStatus.CURRENT,
            tags=list(document.tags),
            updated_by=document.updated_by,
            content_hash=compute_content_hash(document.content),
        )
        self._store.add(new_document)
        self._log_operation("update", new_document.category, new_document.version, "success")
        return Result(success=True, value=new_document)

    def create_version(self, document_id: str, content: str) -> Result[KnowledgeDocument]:
        """既存文書の新バージョンを作成する(IS03 0節: 権限判定は本メソッドでは行わない)。"""
        existing = self._store.get_latest(document_id)
        if existing is None:
            error = KnowledgeDocumentNotFoundError(f"knowledge document not found: {document_id}")
            self._log_operation("create_version", None, None, "not_found")
            return Result(success=False, error=error)

        self._store.archive_latest(document_id)
        new_document = KnowledgeDocument(
            document_id=existing.document_id,
            category=existing.category,
            title=existing.title,
            content=content,
            version=existing.version + 1,
            status=KnowledgeStatus.CURRENT,
            tags=list(existing.tags),
            updated_by=existing.updated_by,
            content_hash=compute_content_hash(content),
        )
        self._store.add(new_document)
        self._log_operation("create_version", new_document.category, new_document.version, "success")
        return Result(success=True, value=new_document)

    # --- 6節: ロギング ---
    def _log_operation(
        self,
        operation: str,
        category: KnowledgeCategory | None,
        knowledge_version: int | None,
        result: str,
    ) -> None:
        """4.5節のログ必須項目(timestamp/knowledge_version/operation/category/result)のみを出力する。

        Knowledge本文(content)・タイトル・タグ等は一切引数に取らず、呼び出し側から
        KnowledgeDocumentオブジェクト自体を渡さないことで、本文がログに混入する経路を
        構造的に排除する(4.5節: Knowledge本文はログへ出力してはならない)。
        """
        self._logger.info(
            "operation=%s category=%s version=%s result=%s",
            operation,
            category.value if category else "-",
            knowledge_version if knowledge_version is not None else "-",
            result,
        )
