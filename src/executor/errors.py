"""Executor(M09)固有例外(IS09 5節)。

Foundationのエラー階層(`FoundationError`)配下にExecutor固有例外を追加するのみとし、
新しい基底例外(FoundationErrorの直下の兄弟クラス)は追加しない。
"""

from __future__ import annotations

from foundation.errors import (
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)


class DesignNotApprovedError(ValidationError):
    """承認されていないDesign Documentを実装しようとした場合に送出する(4.3)。

    - design_document に対応する approved_design が存在しない場合
    - design_document.id と approved_design が参照するdesign_idが一致しない場合
    に発生する。
    """


class DesignDocumentNotFoundError(NotFoundError):
    """入力として渡されたDesign Documentが特定できない場合に送出する。"""


class MultiRepositoryNotAllowedError(ValidationError):
    """複数Repositoryにまたがる変更を試みた場合に送出する(4.4, MVP制約)。"""


class RepositoryBoundaryViolationError(ValidationError):
    """対象Repositoryルート配下以外への書込みを試みた場合に送出する(4.4)。"""


class CodexGenerationError(ExternalServiceError):
    """Codex呼び出しが失敗した場合に送出する(外部サービスエラー)。"""
