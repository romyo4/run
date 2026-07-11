"""Context Manager(M19) 固有例外(IS19 5章)。

Foundation(`foundation.errors`)の例外階層をそのまま利用し、Context Manager固有の
新しい「基底例外」(`FoundationError`直下の兄弟クラス)は追加しない(M00 3.6節の制約)。
既存の`FoundationError`サブクラスをさらに継承する形で定義する。
"""

from foundation.errors import (
    ConfigurationError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)


class ContextNotFoundError(NotFoundError):
    """get(workflow_id) に対応するAIContextが存在しない場合。"""


class ContextValidationError(ValidationError):
    """未定義のworkflow_typeが指定された場合、またはvalidate()呼び出し自体の入力不正。"""


class KnowledgeRetrievalError(ExternalServiceError):
    """Knowledge Manager(M03) の get()/search()/list_documents() 呼び出しが失敗した場合。"""


class ContextConfigurationRetrievalError(ConfigurationError):
    """ConfigurationClient.get() 呼び出しが失敗した場合。"""


class RepositoryContextRetrievalError(ExternalServiceError):
    """GitHub Manager(M20) の build_repository_context() 呼び出しが失敗した場合。"""
