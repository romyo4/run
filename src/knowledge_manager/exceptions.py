"""Knowledge Manager(M03)固有例外(IS03 5節)。

Foundation(`foundation.errors`)の例外階層をそのまま利用し、M03固有の新しい
「基底例外」(`FoundationError`直下の兄弟クラス)は追加しない(M00 3.6節の制約)。
既存の`FoundationError`サブクラスをさらに継承する形で定義する。
"""

from __future__ import annotations

from foundation.errors import NotFoundError, PermissionDeniedError, ValidationError


class KnowledgeDocumentNotFoundError(NotFoundError):
    """document_id に対応するKnowledgeDocumentが存在しない(4.6: 文書不存在)。"""


class KnowledgeVersionConflictError(ValidationError):
    """update()時、渡されたversionがStore上の最新versionと一致しない(4.6: バージョン競合)。"""


class KnowledgeIntegrityError(ValidationError):
    """content_hashが内容と一致しない等の整合性エラー(4.6: 整合性エラー)。"""


class KnowledgeUpdatePermissionDeniedError(PermissionDeniedError):
    """updated_by が Planner/Architect/Reviewer 以外(4.6: 権限不足、3.5節)。"""
