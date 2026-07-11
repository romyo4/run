"""Knowledge Manager(M03)・GitHub Manager(M20)呼び出し先の抽象化(IS19 4.1節)。

具体クラスをimportせず `typing.Protocol` で最小限のインターフェースのみを定義する。
実体は各モジュールの実装(またはテスト用フェイク)を注入する。
"""

from typing import Any, Protocol

from context_manager.types import WorkflowScope
from foundation.result import Result


class KnowledgeManagerPort(Protocol):
    """Knowledge Manager(M03) 3.3節の公開インターフェースのうち、
    Context Managerが利用する参照専用メソッドのみを抽出する(4.4節: 参照のみ)。"""

    def get(self, document_id: str) -> Result[Any]:
        """`KnowledgeDocument` 単体取得。"""
        ...

    def search(self, keyword: str) -> Result[list[Any]]:
        """キーワード検索。Planner Context の自由項目『Knowledge』等に利用する。"""
        ...

    def list_documents(self, category: str) -> Result[list[Any]]:
        """カテゴリ単位の一覧取得。Business Goal・MVP Policy・Architecture Principles・
        Coding Rules 等、M03 3.1節のカテゴリ単位の取得に利用する。"""
        ...


class GitHubManagerPort(Protocol):
    """GitHub Manager(M20) 3.5節の公開インターフェースのうち、
    Context Managerが利用する `build_repository_context()` のみを抽出する。"""

    def build_repository_context(self, repository: str, workflow_scope: WorkflowScope) -> Result[Any]:
        """指定Workflowに必要なRepository情報のみを取得する(M20 3.3節: Repository全体は返却しない)。

        `repository` はIS20仕様書が全メソッド共通の必須入力として定めるRepository識別子。
        """
        ...
