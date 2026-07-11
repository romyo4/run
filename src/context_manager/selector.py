"""処理フロー『Select』段階(IS19 4.3節)。

Workflow種別ごとに必要な項目のみを `CollectedContext` から選び `SelectedContext` を生成する。
"""

from context_manager.types import CollectedContext, SelectedContext, WorkflowType

# 設計書 3.3節の対応をそのまま定数化する。
WORKFLOW_FIELD_MAP: dict[WorkflowType, frozenset[str]] = {
    WorkflowType.PLANNER: frozenset({"business_goal", "user_instruction", "knowledge"}),
    WorkflowType.ARCHITECT: frozenset({"requirements", "knowledge", "architecture_principles"}),
    WorkflowType.EXECUTOR: frozenset({"execution_plan", "repository_context", "coding_rules", "design_documents"}),
    WorkflowType.REVIEWER: frozenset({"implementation", "design_documents", "test_report", "business_goal"}),
    WorkflowType.WEEKLY_REVIEWER: frozenset(
        {"merged_pull_requests", "review_reports", "business_goal", "technical_debt_reports"}
    ),
}

# collected.knowledge_documents(Knowledge Manager `KnowledgeDocument.category`, M03 3.2節)を
# カテゴリ値で振り分けてSelectedContextの各フィールドへ割り当てるための対応表。
# architecture_principlesカテゴリはdesign_documentsフィールドへも割り当てる
# (設計書はDesign Documentsの専用取得元を定めていないため、M03既存カテゴリで代替する。IS19 4.3節注記)。
_CATEGORY_TO_SELECTED_FIELDS: dict[str, tuple[str, ...]] = {
    "business_goal": ("business_goal",),
    "knowledge": ("knowledge",),
    "requirements": ("requirements",),
    "architecture_principles": ("architecture_principles", "design_documents"),
    "coding_rules": ("coding_rules",),
}

# CollectedContextから同名フィールドへそのまま転記するフィールド。
_DIRECT_FIELDS: tuple[str, ...] = (
    "user_instruction",
    "execution_plan",
    "repository_context",
    "implementation",
    "test_report",
    "merged_pull_requests",
    "review_reports",
    "technical_debt_reports",
)


def select(workflow_type: WorkflowType, collected: CollectedContext) -> SelectedContext:
    """WORKFLOW_FIELD_MAPに列挙された項目のみをCollectedContextから転記し、
    それ以外のフィールドはNone/空のままとする(設計書4.2節: 不要な情報を追加しない)。
    business_goal / knowledge / requirements / architecture_principles / coding_rules は、
    collected.knowledge_documents(Knowledge Manager `KnowledgeDocument.category`, M03 3.2節)を
    カテゴリ値で振り分けて割り当てる。design_documentsは同様にArchitecture Principlesカテゴリ由来の
    文書を割り当てる。
    """
    required_fields = WORKFLOW_FIELD_MAP[workflow_type]
    selected = SelectedContext(workflow_type=workflow_type)

    for category, field_names in _CATEGORY_TO_SELECTED_FIELDS.items():
        matches = [document for document in collected.knowledge_documents if getattr(document, "category", None) == category]
        if not matches:
            continue
        for field_name in field_names:
            if field_name in required_fields:
                setattr(selected, field_name, matches)

    for field_name in _DIRECT_FIELDS:
        if field_name in required_fields:
            setattr(selected, field_name, getattr(collected, field_name))

    return selected
