"""Markdownファイル → KnowledgeDocument変換の実処理(load()の下請け、IS03 4.3構造検証)。

Knowledgeソースは以下の形式のMarkdownファイルのみを対象とする(5.3節: MVP対象外の
Vector Database/Embedding等は一切使用しない、単純なテキスト読込のみ)。

    Document_id: business_goal          (省略可。省略時はファイル名(拡張子除く)を使用)
    Category: business_goal             (必須。KnowledgeCategoryのいずれかの値)
    Title: プロジェクトのビジネスゴール    (必須)
    Tags: tag1, tag2                    (省略可)

    本文(Content)はここから。
    複数行に渡ってよい。

先頭の `Key: Value` 行が連続するメタデータブロックと、最初の空行以降の本文(Content)
から構成される。Category/Title/Content(4.3節の構造化必須要件)のいずれかが欠落・
不正な場合は `ValidationError` を送出する。ファイルが存在しない場合は `NotFoundError`
を送出する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from foundation.errors import NotFoundError, ValidationError
from knowledge_manager.models import KnowledgeCategory

_VALID_CATEGORY_VALUES = {category.value for category in KnowledgeCategory}


@dataclass
class ParsedKnowledgeSource:
    """load()実処理の中間結果(4.3構造検証を満たした後のフィールドのみを保持する)。"""

    document_id: str
    category: KnowledgeCategory
    title: str
    content: str
    tags: list[str] = field(default_factory=list)


def parse_markdown_source(source: Path) -> ParsedKnowledgeSource:
    """MarkdownファイルからKnowledge文書の構造化フィールドを取り出す(4.3節)。

    Args:
        source: Knowledgeソースファイルのパス。

    Returns:
        ParsedKnowledgeSource: Category/Title/Content/document_id/tagsを検証済みで保持する。

    Raises:
        NotFoundError: `source` が存在しない、またはファイルでない場合。
        ValidationError: Category/Title/Contentのいずれかが欠落・不正な場合(4.3構造要件違反)。
    """
    if not source.exists() or not source.is_file():
        raise NotFoundError(f"knowledge source not found: {source}")

    text = source.read_text(encoding="utf-8")
    lines = text.splitlines()

    metadata: dict[str, str] = {}
    body_start = len(lines)
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            body_start = idx + 1
            break
        if ":" not in stripped:
            body_start = idx
            break
        key, _, value = stripped.partition(":")
        metadata[key.strip().lower()] = value.strip()
        body_start = idx + 1

    content = "\n".join(lines[body_start:]).strip()

    category_raw = metadata.get("category", "")
    if category_raw.lower() not in _VALID_CATEGORY_VALUES:
        raise ValidationError(f"missing or invalid 'Category' section in knowledge source: {source}")

    title = metadata.get("title", "").strip()
    if not title:
        raise ValidationError(f"missing 'Title' section in knowledge source: {source}")

    if not content:
        raise ValidationError(f"missing content body in knowledge source: {source}")

    tags_raw = metadata.get("tags", "")
    tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]

    document_id = metadata.get("document_id", "").strip() or source.stem

    return ParsedKnowledgeSource(
        document_id=document_id,
        category=KnowledgeCategory(category_raw.lower()),
        title=title,
        content=content,
        tags=tags,
    )
