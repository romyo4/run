"""KnowledgeStore: 文書と全バージョン履歴のインメモリ管理(IS03 2節)。

document_id単位で全バージョンの履歴を保持し、最新版の既定利用・過去版参照(設計書3.4節)を
提供する。Vector Database・外部永続化ストア等は使用しない(MVPはインメモリのみ)。
KnowledgeManagerからのみ呼び出される内部コンポーネントであり、公開APIではない。
"""

from __future__ import annotations

import hashlib
from dataclasses import replace

from knowledge_manager.models import KnowledgeDocument, KnowledgeStatus


def compute_content_hash(content: str) -> str:
    """contentからcontent_hash(4.6: 整合性エラー検知用)を計算する。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class KnowledgeStore:
    """document_id -> 全バージョン履歴(list[KnowledgeDocument])のインメモリストア。"""

    def __init__(self) -> None:
        self._history: dict[str, list[KnowledgeDocument]] = {}

    def add(self, document: KnowledgeDocument) -> None:
        """新しいバージョンの文書を履歴へ追加する(load()/update()/create_version()から呼ばれる)。"""
        self._history.setdefault(document.document_id, []).append(document)

    def get_latest(self, document_id: str) -> KnowledgeDocument | None:
        """document_idの最新版(バージョン番号最大)を返す(3.4節: 最新版を既定で利用)。"""
        versions = self._history.get(document_id)
        if not versions:
            return None
        return max(versions, key=lambda doc: doc.version)

    def get_version(self, document_id: str, version: int) -> KnowledgeDocument | None:
        """document_idの指定バージョンを返す(3.4節: 過去版参照可能)。"""
        versions = self._history.get(document_id)
        if not versions:
            return None
        for document in versions:
            if document.version == version:
                return document
        return None

    def archive_latest(self, document_id: str) -> None:
        """現在の最新版をARCHIVEDへ遷移させる(新バージョン追加の直前に呼ぶ)。"""
        latest = self.get_latest(document_id)
        if latest is None:
            return
        versions = self._history[document_id]
        for idx, document in enumerate(versions):
            if document is latest:
                versions[idx] = replace(document, status=KnowledgeStatus.ARCHIVED)
                return

    def all_current_documents(self) -> list[KnowledgeDocument]:
        """document_idごとにstatus=CURRENTの最新版のみを返す(search()/list_documents()用)。"""
        current_documents: list[KnowledgeDocument] = []
        for versions in self._history.values():
            if not versions:
                continue
            latest = max(versions, key=lambda doc: doc.version)
            if latest.status is KnowledgeStatus.CURRENT:
                current_documents.append(latest)
        return current_documents
