"""search()のキーワード一致検索の実処理(IS03 2節/5.3節)。

大文字小文字を区別しない単純な部分一致検索のみを提供する。形態素解析・
類似度スコアリング・埋め込みベクトル・Vector Database等は一切使用しない
(設計書5.3節でMVP対象外と判定済み)。KnowledgeManagerからのみ呼び出される
内部コンポーネントであり、公開APIではない。
"""

from __future__ import annotations

from knowledge_manager.models import KnowledgeDocument


def matches_keyword(document: KnowledgeDocument, keyword: str) -> bool:
    """documentのtitleまたはcontentにkeywordが大文字小文字を区別せず部分一致するか判定する。"""
    needle = keyword.lower()
    return needle in document.title.lower() or needle in document.content.lower()


def search_documents(documents: list[KnowledgeDocument], keyword: str) -> list[KnowledgeDocument]:
    """documentsのうちkeywordに部分一致するものだけを返す(該当なしは空リスト、エラーではない)。"""
    return [document for document in documents if matches_keyword(document, keyword)]
