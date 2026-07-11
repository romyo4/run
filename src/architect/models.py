"""Architect(M07) データクラス定義(IS07 3.2節)。

Foundation Domain Model一覧に存在しない `DesignRequirement` / `ValidationResult` は
Architect内部専用のプレーンなdataclassとして定義する(Foundation共通属性は付与しない)。
`DesignDocument` は Foundation `Design` Domain(F01)を継承する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, TypeAlias

from foundation.types import Context, Design, Knowledge

__all__ = [
    "ExecutionPlan",
    "ProjectContext",
    "ArchitectureGuidelines",
    "Knowledge",
    "DesignRequirement",
    "ValidationStatus",
    "ValidationIssue",
    "ValidationResult",
    "ValidatedDesign",
    "ModuleDesignItem",
    "InterfaceDesignItem",
    "DataStructureItem",
    "ImplementationStrategy",
    "DesignStatus",
    "DesignDocument",
]


# --- 外部モジュール型の参照(実体はArchitect側で所有しない) ---


class ExecutionPlan(Protocol):
    """Planner(M06) が生成する Execution Plan の構造的参照。

    実体定義は Planner の実装仕様書(IS06)を正とする。Architectはここで定義された
    属性への読み取りのみを行い、要求の変更は行わない(M07設計書 4.2)。
    """

    plan_id: str
    objective: str
    task_list: list[Any]
    priority: dict[str, str]
    dependencies: dict[str, list[str]]
    expected_output: str


ProjectContext: TypeAlias = Context
"""project_context 入力。Foundation の Context Domain(Context Manager所有)をそのまま再利用する。"""

ArchitectureGuidelines: TypeAlias = dict[str, Any]
"""architecture_guidelines 入力。M07設計書に内部構造の定義がないため自由形式で扱う。"""


# --- Architect内部専用dataclass(Foundation Domain Model一覧に存在しないため共通属性なし) ---


@dataclass(kw_only=True)
class DesignRequirement:
    """analyze_plan() の出力(Design Requirement)。"""

    requirement_id: str
    workflow_id: str
    source_execution_plan_id: str
    objective: str
    background: str = ""
    constraints: list[str] = field(default_factory=list)
    functional_requirements: list[str] = field(default_factory=list)
    non_functional_requirements: list[str] = field(default_factory=list)
    existing_architecture_summary: str = ""
    reusable_components: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


class ValidationStatus(str, Enum):
    """validate_design() の判定結果。Design Auditorの監査結果(PASS等)とは別軸の自己検証結果。"""

    VALID = "VALID"
    INVALID = "INVALID"


@dataclass(kw_only=True)
class ValidationIssue:
    field_name: str
    message: str


@dataclass(kw_only=True)
class ValidationResult:
    """validate_design() の出力(Validation Result)。"""

    validation_id: str
    design_id: str
    status: ValidationStatus
    issues: list[ValidationIssue] = field(default_factory=list)
    validated_at: datetime = field(default_factory=datetime.now)


@dataclass(kw_only=True)
class ValidatedDesign:
    """publish_design() の入力(Validated Design)。DesignDocumentと自己検証結果の組。"""

    design_document: DesignDocument
    validation_result: ValidationResult


# --- Design Document 内部構造(M07設計書 3.4節) ---


@dataclass(kw_only=True)
class ModuleDesignItem:
    module_name: str
    responsibility: str
    depends_on: list[str] = field(default_factory=list)
    is_new: bool = True
    reuse_rationale: str = ""


@dataclass(kw_only=True)
class InterfaceDesignItem:
    interface_name: str
    owning_module: str
    input_spec: str
    output_spec: str
    description: str = ""


@dataclass(kw_only=True)
class DataStructureItem:
    name: str
    fields: dict[str, str] = field(default_factory=dict)
    description: str = ""


@dataclass(kw_only=True)
class ImplementationStrategy:
    approach: str
    reused_components: list[str] = field(default_factory=list)
    new_components: list[str] = field(default_factory=list)
    rationale: str = ""


class DesignStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    PUBLISHED = "PUBLISHED"


@dataclass(kw_only=True)
class DesignDocument(Design):
    """Foundation Design Domain(F01) を実装するArchitect成果物。

    id / created_at / updated_at / metadata は Design 基底の共通属性。
    """

    workflow_id: str = ""
    source_requirement_id: str = ""
    objective: str = ""
    architecture: str = ""
    module_design: list[ModuleDesignItem] = field(default_factory=list)
    interface_design: list[InterfaceDesignItem] = field(default_factory=list)
    data_structure: list[DataStructureItem] = field(default_factory=list)
    implementation_strategy: ImplementationStrategy | None = None
    constraints: list[str] = field(default_factory=list)
    status: DesignStatus = DesignStatus.DRAFT
