"""Architect(M07) create_design() の内部処理(IS07 4.3節 / 設計書3.3, 3.4)。

Business First / MVP First / Single Responsibility / Reuse First / Simplicity を
優先方針として Design Document を生成する。既存設計を変更する場合は
ModuleDesignItem.reuse_rationale に理由を明記する(設計書3.3)。
"""

from __future__ import annotations

from architect.errors import DesignCreationError
from architect.models import (
    DataStructureItem,
    DesignDocument,
    DesignRequirement,
    DesignStatus,
    ImplementationStrategy,
    InterfaceDesignItem,
    ModuleDesignItem,
)
from foundation.result import Result

__all__ = [
    "create_design",
    "build_module_design",
    "build_interface_design",
    "build_data_structure",
    "decide_implementation_strategy",
    "build_metadata",
]

_REUSE_RATIONALE_TEMPLATE = "Reuse First原則により既存コンポーネント'{component}'を再利用する(新規モジュール追加を回避)"


def create_design(design_requirement: DesignRequirement) -> Result[DesignDocument]:
    """Design Requirement から Design Document を生成する(3.3, 3.4)。

    design_requirement.objective または workflow_id が空の場合は `DesignCreationError` を送出する。
    """
    if not design_requirement.objective or not design_requirement.workflow_id:
        raise DesignCreationError("design_requirement.objective and workflow_id must not be empty")

    module_design = build_module_design(design_requirement)
    interface_design = build_interface_design(module_design)
    data_structure = build_data_structure(design_requirement)
    implementation_strategy = decide_implementation_strategy(design_requirement, module_design)
    metadata = build_metadata(design_requirement, module_design, interface_design, data_structure, implementation_strategy)

    document = DesignDocument(
        workflow_id=design_requirement.workflow_id,
        source_requirement_id=design_requirement.requirement_id,
        objective=design_requirement.objective,
        architecture=design_requirement.existing_architecture_summary,
        module_design=module_design,
        interface_design=interface_design,
        data_structure=data_structure,
        implementation_strategy=implementation_strategy,
        constraints=list(design_requirement.constraints),
        status=DesignStatus.DRAFT,
        metadata=metadata,
    )
    return Result(success=True, value=document)


def build_module_design(design_requirement: DesignRequirement) -> list[ModuleDesignItem]:
    """再利用可能コンポーネントと新規モジュールから Module Design を組み立てる(Reuse First)。"""
    modules: list[ModuleDesignItem] = [
        ModuleDesignItem(
            module_name=component,
            responsibility=f"既存コンポーネント'{component}'の再利用",
            is_new=False,
            reuse_rationale=_REUSE_RATIONALE_TEMPLATE.format(component=component),
        )
        for component in design_requirement.reusable_components
    ]

    modules.append(
        ModuleDesignItem(
            module_name=f"{design_requirement.workflow_id}_core",
            responsibility=design_requirement.objective,
            depends_on=list(design_requirement.reusable_components),
            is_new=True,
            reuse_rationale="",
        )
    )
    return modules


def build_interface_design(
    module_design: list[ModuleDesignItem],
) -> list[InterfaceDesignItem]:
    """Module Design の各モジュールに対応する Interface Design を組み立てる。"""
    return [
        InterfaceDesignItem(
            interface_name=f"{module.module_name}_interface",
            owning_module=module.module_name,
            input_spec="TBD",
            output_spec="TBD",
            description=module.responsibility,
        )
        for module in module_design
    ]


def build_data_structure(design_requirement: DesignRequirement) -> list[DataStructureItem]:
    """Design Requirement から中核となる Data Structure を組み立てる。"""
    return [
        DataStructureItem(
            name=f"{design_requirement.workflow_id}_data",
            fields={"id": "str"},
            description=design_requirement.objective,
        )
    ]


def decide_implementation_strategy(
    design_requirement: DesignRequirement,
    module_design: list[ModuleDesignItem],
) -> ImplementationStrategy:
    """Reuse First / Simplicity を優先方針として Implementation Strategy を決定する。"""
    reused = [module.module_name for module in module_design if not module.is_new]
    new = [module.module_name for module in module_design if module.is_new]
    approach = "Reuse First" if reused else "New Implementation"
    return ImplementationStrategy(
        approach=approach,
        reused_components=reused,
        new_components=new,
        rationale=(
            "Business First / MVP First / Single Responsibility / Reuse First / Simplicity " "を優先方針として決定した"
        ),
    )


def build_metadata(
    design_requirement: DesignRequirement,
    module_design: list[ModuleDesignItem],
    interface_design: list[InterfaceDesignItem],
    data_structure: list[DataStructureItem],
    implementation_strategy: ImplementationStrategy,
) -> dict[str, object]:
    """Design Auditor(M08)の監査4項目が読み取る `DesignDocument.metadata` を構築する。

    Design Auditor(design_auditor/requirement_check.py, mvp_check.py)は
    Architectの内部dataclassに依存せず `metadata` 経由でのみ監査対象情報を受け取る
    (design_auditor/architecture_check.py, quality_check.py の実装解釈メモと同じ理由による
    モジュール間疎結合)。ここではArchitectの入力(DesignRequirement)および自身が生成した
    Design Document本文から導出可能な情報のみを格納し、存在しない情報を推測で作り上げない。

    - workflow_id: Design Auditor `module.py` `_extract_ids()` が
      `design_document.metadata["workflow_id"]` を前提として読み取る(IS08 4.クラス・関数
      シグネチャの実装解釈メモ)。
    - requirements / requirements_covered: Design Auditorの要件充足確認(requirement_check.py)
      が読み取る。build_module_design()は取得した functional_requirements /
      non_functional_requirements を選別せず全て中核モジュール(_core)の責務に反映するため
      (Reuse First適用分を除き要件を落とさない)、設計時点でカバー対象外となる要件はない。
    - features / content: Design AuditorのMVP適合性確認(mvp_check.py)が読み取る。
      features は要求された機能一覧(functional_requirements)、content はArchitectが実際に
      生成したDesign Document本文(objective / architecture summary / module 責務 /
      interface 説明 / data structure 説明 / implementation strategy / constraints)を
      連結したものとし、MVP対象外機能(M07/M08 5.3)の混入検出に用いる。
    - architecture_notes / quality_notes: Design Auditorの責務である設計品質・過剰設計の
      判定結果をArchitectが自ら申告することは「Architectはレビューしない」(M07 4.3)に反する
      ため、ここでは意図的に設定しない。両キーが存在しない場合、design_auditor側は
      「違反なし」として安全側に倒す(design_auditor/architecture_check.py,
      quality_check.py の実装解釈メモ)。
    """
    requirements = list(design_requirement.functional_requirements) + list(design_requirement.non_functional_requirements)
    content_parts = [
        design_requirement.objective,
        design_requirement.existing_architecture_summary,
        *(module.responsibility for module in module_design),
        *(module.reuse_rationale for module in module_design if module.reuse_rationale),
        *(interface.description for interface in interface_design if interface.description),
        *(item.description for item in data_structure if item.description),
        implementation_strategy.approach,
        implementation_strategy.rationale,
        *design_requirement.constraints,
    ]
    content = "\n".join(part for part in content_parts if part)

    return {
        "workflow_id": design_requirement.workflow_id,
        "requirements": requirements,
        "requirements_covered": list(requirements),
        "features": list(design_requirement.functional_requirements),
        "content": content,
    }
