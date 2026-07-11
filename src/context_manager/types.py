"""Context Manager(M19) 固有の dataclass・Enum 定義(IS19 3章)。

Foundation(F01) `Context` dataclass をそのまま継承し、モジュール固有属性を追加する。
Foundation側の `types.py` は変更しない(IS00 4.3節の方針)。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from foundation.types import Context
from foundation.utils import utc_now


class WorkflowType(str, Enum):
    """設計書 3.3節『Workflow別Context』および適用対象(1章)に定義された5種のみ。"""

    PLANNER = "planner"
    ARCHITECT = "architect"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    WEEKLY_REVIEWER = "weekly_reviewer"


@dataclass
class WorkflowScope:
    """GitHub Manager `build_repository_context()` へ渡すスコープ情報
    (設計書3.5 GitHub Managerの入力『Workflow Scope』に対応)。

    `repository` は GitHub Manager(M20)実装仕様書(IS20)がGitHub API呼び出しの
    必須入力として全メソッド共通に要求している値(owner/repo形式)。Context Manager
    設計書には明記が無かったため、統合時に判明した不足フィールドとして追加した
    (CHANGELOG.md参照)。既定値""は後方互換のためのものであり、実運用では
    呼び出し元が実際のRepository識別子を設定する。
    """

    workflow_id: str
    workflow_type: WorkflowType
    target_paths: list[str] = field(default_factory=list)
    repository: str = ""


@dataclass
class ContextRequest:
    """build() の入力。Context Manager が能動的に参照するのは
    Knowledge Manager / Configuration Manager / GitHub Manager の3モジュールのみであり、
    以下フィールドは呼び出し元(Command Router等)が既に保有する成果物をそのまま渡す。"""

    workflow_id: str
    workflow_type: WorkflowType
    workflow_scope: WorkflowScope
    execution_plan: Any | None = None
    user_instruction: str | None = None
    implementation: Any | None = None
    test_report: Any | None = None
    merged_pull_requests: list[Any] = field(default_factory=list)
    review_reports: list[Any] = field(default_factory=list)
    technical_debt_reports: list[Any] = field(default_factory=list)


@dataclass
class CollectedContext:
    """処理フロー『Collect』段階の出力。Workflow種別に関わらず収集可能な全情報を保持する中間データ。"""

    knowledge_documents: list[Any] = field(default_factory=list)
    repository_context: Any | None = None
    environment: str | None = None
    execution_plan: Any | None = None
    user_instruction: str | None = None
    implementation: Any | None = None
    test_report: Any | None = None
    merged_pull_requests: list[Any] = field(default_factory=list)
    review_reports: list[Any] = field(default_factory=list)
    technical_debt_reports: list[Any] = field(default_factory=list)


@dataclass
class SelectedContext:
    """処理フロー『Select』段階の出力。設計書3.3節のWorkflow別Context対応表に従い、
    workflow_typeに必要な項目のみをNone/空以外で保持する(不要な項目は追加しない、設計書4.2節)。"""

    workflow_type: WorkflowType
    business_goal: Any | None = None
    user_instruction: str | None = None
    knowledge: list[Any] = field(default_factory=list)
    requirements: list[Any] = field(default_factory=list)
    architecture_principles: list[Any] = field(default_factory=list)
    execution_plan: Any | None = None
    repository_context: Any | None = None
    coding_rules: list[Any] = field(default_factory=list)
    design_documents: list[Any] = field(default_factory=list)
    implementation: Any | None = None
    test_report: Any | None = None
    merged_pull_requests: list[Any] = field(default_factory=list)
    review_reports: list[Any] = field(default_factory=list)
    technical_debt_reports: list[Any] = field(default_factory=list)


@dataclass
class ContextMetadata:
    """設計書3.4節『Context Metadata』。ログ4.6節の記録項目と対応させる。"""

    workflow_id: str
    workflow_type: WorkflowType
    context_version: str
    built_at: datetime = field(default_factory=utc_now)
    environment: str | None = None


@dataclass
class AIContext(Context):
    """設計書3.4節『AI Context』。Foundation `Context`(F01)の共通属性
    (id/created_at/updated_at/metadata)を継承し、Context Manager固有属性を追加する。"""

    workflow_id: str = ""
    workflow_type: WorkflowType = WorkflowType.PLANNER
    selected_context: SelectedContext | None = None
    context_metadata: ContextMetadata | None = None
    context_version: str = ""


@dataclass
class ValidationResult:
    """validate()の出力『Validation Result』。"""

    is_valid: bool
    missing_fields: list[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=utc_now)
