# IS07 Architect 実装仕様書

対象設計書: `M07 Architect.txt`（確定済み・変更なし）
前提モジュール: `M00 Foundation.txt`（F00〜F03、Result[T]、BaseModule、共通エラー階層、ロギング規約）
Python: 3.13 / 型ヒント必須 / dataclass / pathlib / logging標準ライブラリ（`get_logger()`経由）/ unittest / UTF-8 / Ruff・Black準拠

---

## 1. モジュール概要

Architect は、Planner（M06）が作成した Execution Plan を実装可能な Design Document へ変換する設計専任モジュールである。要件分析・Task分解は行わず、既に確定した Execution Plan・Knowledge・Project Context・Architecture Guidelines を入力として、Architecture Design・Module Design・Interface Design・Data Structure・Implementation Strategy・Constraints から成る Design Document を生成する。Architect は「設計のみ」を責務とし、コード生成・Pull Request作成・GitHub操作・設計品質のレビュー判定（Design Auditorの責務）は一切行わない。生成した Design Document は自己の構造的完全性のみを自己検証（`validate_design`）した上で publish し、後続の Design Auditor（M08）が要求適合性・アーキテクチャ整合性・MVP適合性を審査する2段構成になっている。

---

## 2. ファイル構成

```text
src/architect/
├── __init__.py        # パッケージ公開シンボル（ArchitectModule, 主要dataclass）のエクスポート
├── module.py           # ArchitectModule(BaseModule) 本体。4publicメソッドの入口・ログ出力・Result[T]組み立て
├── models.py            # DesignRequirement / DesignDocument / ValidationResult 等のdataclass定義
├── analyzer.py           # analyze_plan() の内部処理（要件抽出・既存アーキテクチャ分析・再利用可能コンポーネント検出・技術的制約分析）
├── designer.py          # create_design() の内部処理（Architecture/Module/Interface/DataStructure設計・Implementation Strategy決定）
├── validator.py          # validate_design() の内部処理（Design Documentの構造的完全性・内部整合性の自己検証。品質評価は行わない）
├── publisher.py         # publish_design() の内部処理（ValidatedDesignをDesign（Foundation Design Domain）として確定）
├── errors.py            # Architect固有例外（Foundation errors継承）
└── tests/
    ├── __init__.py
    ├── test_module.py
    ├── test_analyzer.py
    ├── test_designer.py
    ├── test_validator.py
    ├── test_publisher.py
    └── test_errors.py
```

依存方向: `architect` パッケージは `foundation`（F00〜F03一式）にのみ依存する。`planner`（Execution Plan の実体定義元）へは型参照のみを行い、Planner内部実装には依存しない（DESIGN_FREEZE_v1.0.md の依存グラフ `Planner(M06) → Architect(M07) → Design Auditor(M08)` に整合）。

---

## 3. データクラス定義

### 3.1 設計上の前提とマッピング方針

Foundation（F01）の Domain Model 一覧には `Design`（設計成果物・Architect/Design Auditorが利用）が定義されているが、`Design Requirement` `Validation Result` は一覧に存在しない。したがって本仕様書では以下の方針を採る。

- **`DesignDocument`**: Foundation の `Design` Domain（共通属性 `id` / `created_at` / `updated_at` / `metadata`）を継承し、M07設計書 3.4節の Design Document 項目をモジュール固有属性として追加する。3.4節の「Design ID」は Foundation共通属性 `id` に対応する。
- **`DesignRequirement`** / **`ValidationResult`**: Foundation Domain Model一覧に存在しないため、Architect内部専用のプレーンな dataclass として定義する（Foundation共通属性は付与しない）。ただしF00 Traceabilityのため独自IDを持つ。
- **`publish_design()` の出力「Design」**: Foundation `Design` Domain の実体は `DesignDocument` が実装しているため、新たなクラスを追加せず `DesignDocument`（`status=PUBLISHED`）をそのまま返す（Reuse First / Simplicity）。
- **`ExecutionPlan`**: 実体定義は Planner（M06）の実装仕様書（IS06、未作成）を正とする。Architectは重複定義を避けるため、M06設計書 3.5節記載のフィールド（Plan ID, Objective, Task List, Priority, Dependencies, Expected Output）に対応する構造的 `Protocol` としてのみ型参照する。
- **`project_context`**: Foundation `Context` Domain（Context Manager所有）をそのまま再利用し、型エイリアスとする。
- **`architecture_guidelines`**: M07設計書に内部構造の定義がないため、自由形式の `dict[str, Any]` 型エイリアスとする（存在しない構造を推測で dataclass 化しない）。
- **`knowledge`**: Foundation `Knowledge` Domain（Knowledge Manager所有）のリストとして扱う。

すべての Domain 系 dataclass は `@dataclass(kw_only=True)` とし、Foundation基底クラスとの継承時のフィールド順序制約（デフォルト値なしフィールドがデフォルト値ありフィールドより後に来られない）を回避する。

### 3.2 `architect/models.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, TypeAlias

from foundation.types import Context, Design, Knowledge


# --- 外部モジュール型の参照（実体はArchitect側で所有しない） ---

class ExecutionPlan(Protocol):
    """Planner(M06) が生成する Execution Plan の構造的参照。
    実体定義は Planner の実装仕様書(IS06)を正とする。
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


# --- Architect内部専用dataclass（Foundation Domain Model一覧に存在しないため共通属性なし） ---

@dataclass(kw_only=True)
class DesignRequirement:
    """analyze_plan() の出力（Design Requirement）。"""
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
    """validate_design() の出力（Validation Result）。"""
    validation_id: str
    design_id: str
    status: ValidationStatus
    issues: list[ValidationIssue] = field(default_factory=list)
    validated_at: datetime = field(default_factory=datetime.now)


@dataclass(kw_only=True)
class ValidatedDesign:
    """publish_design() の入力（Validated Design）。DesignDocumentと自己検証結果の組。"""
    design_document: "DesignDocument"
    validation_result: ValidationResult


# --- Design Document 内部構造（M07設計書 3.4節） ---

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
```

`Design`（Foundation基底）のフィールド（`id`, `created_at`, `updated_at`, `metadata`）は `foundation/types.py` の定義に従い、本仕様書側では再定義しない。

---

## 4. クラス・関数シグネチャ

### 4.1 `architect/module.py`

```python
from __future__ import annotations

from logging import Logger

from foundation.base_module import BaseModule
from foundation.interfaces import ConfigurationClient
from foundation.result import Result

from architect.models import (
    ArchitectureGuidelines,
    DesignDocument,
    DesignRequirement,
    ExecutionPlan,
    Knowledge,
    ProjectContext,
    ValidatedDesign,
    ValidationResult,
)


class ArchitectModule(BaseModule):
    """M07 Architect の公開インターフェース実装(BaseModule継承)。"""

    def __init__(
        self,
        config_client: ConfigurationClient,
        logger: Logger | None = None,
    ) -> None: ...

    def name(self) -> str:
        """"architect" を返す。"""
        ...

    def health_check(self) -> Result[bool]:
        """ConfigurationClient疎通確認等を行い、Result[bool]で稼働可否を返す。"""
        ...

    def analyze_plan(
        self,
        workflow_id: str,
        execution_plan: ExecutionPlan,
        knowledge: list[Knowledge] | None = None,
        project_context: ProjectContext | None = None,
        architecture_guidelines: ArchitectureGuidelines | None = None,
    ) -> Result[DesignRequirement]:
        """Execution Plan を分析し Design Requirement を生成する(M07設計書 3.5 analyze_plan)。
        Planner が確定した要求(objective / task_list等)は変更しない(4.2)。
        """
        ...

    def create_design(self, design_requirement: DesignRequirement) -> Result[DesignDocument]:
        """Design Requirement から Design Document を生成する(3.5 create_design)。"""
        ...

    def validate_design(self, design_document: DesignDocument) -> Result[ValidationResult]:
        """Design Documentの構造的完全性・内部整合性のみを自己検証する(3.5 validate_design)。
        要求適合性・品質評価はDesign Auditor(M08)の責務であり本メソッドでは行わない(4.3)。
        """
        ...

    def publish_design(self, validated_design: ValidatedDesign) -> Result[DesignDocument]:
        """検証済みDesignを確定し、status=PUBLISHEDのDesign Documentを返す(3.5 publish_design)。
        validation_result.status != VALID の場合は publish せず Result[DesignDocument](success=False)を返す。
        """
        ...
```

### 4.2 `architect/analyzer.py`

```python
from __future__ import annotations

from foundation.result import Result

from architect.models import (
    ArchitectureGuidelines,
    DesignRequirement,
    ExecutionPlan,
    Knowledge,
    ProjectContext,
)


def analyze_plan(
    workflow_id: str,
    execution_plan: ExecutionPlan,
    knowledge: list[Knowledge],
    project_context: ProjectContext | None,
    architecture_guidelines: ArchitectureGuidelines | None,
) -> Result[DesignRequirement]:
    """要件・既存アーキテクチャ・既存モジュール・再利用可能コンポーネント・技術的制約を分析する(3.2)。"""
    ...


def extract_constraints(execution_plan: ExecutionPlan) -> list[str]: ...


def identify_reusable_components(
    project_context: ProjectContext | None,
    architecture_guidelines: ArchitectureGuidelines | None,
) -> list[str]: ...


def summarize_existing_architecture(
    architecture_guidelines: ArchitectureGuidelines | None,
) -> str: ...
```

### 4.3 `architect/designer.py`

```python
from __future__ import annotations

from foundation.result import Result

from architect.models import DesignDocument, DesignRequirement


def create_design(design_requirement: DesignRequirement) -> Result[DesignDocument]:
    """Business First / MVP First / Single Responsibility / Reuse First / Simplicity を
    優先方針として Design Document を生成する(3.3, 3.4)。
    既存設計を変更する場合は ModuleDesignItem.reuse_rationale に理由を明記する(3.3)。
    """
    ...


def build_module_design(design_requirement: DesignRequirement) -> list["ModuleDesignItem"]: ...


def build_interface_design(
    module_design: list["ModuleDesignItem"],
) -> list["InterfaceDesignItem"]: ...


def build_data_structure(design_requirement: DesignRequirement) -> list["DataStructureItem"]: ...


def decide_implementation_strategy(
    design_requirement: DesignRequirement,
    module_design: list["ModuleDesignItem"],
) -> "ImplementationStrategy": ...
```

### 4.4 `architect/validator.py`

```python
from __future__ import annotations

from foundation.result import Result

from architect.models import DesignDocument, ValidationResult


def validate_design(design_document: DesignDocument) -> Result[ValidationResult]:
    """Design Documentの必須項目充足・内部整合性(Interfaceの参照先ModuleがModule Designに
    存在するか等)のみを検証する。要求充足度・MVP適合性・過剰設計判定はDesign Auditorの責務であり
    本関数の対象外(4.3)。
    """
    ...
```

### 4.5 `architect/publisher.py`

```python
from __future__ import annotations

from foundation.result import Result

from architect.models import DesignDocument, ValidatedDesign


def publish_design(validated_design: ValidatedDesign) -> Result[DesignDocument]:
    """ValidatedDesign.validation_result.status が VALID の場合のみ、
    design_document.status を PUBLISHED に更新して返す。
    INVALID の場合は publish せず Result[DesignDocument](success=False, error=ValidationError)を返す(F00 Safety)。
    """
    ...
```

### 4.6 `architect/__init__.py` 公開シンボル

```python
from architect.module import ArchitectModule
from architect.models import (
    DesignDocument,
    DesignRequirement,
    ValidatedDesign,
    ValidationResult,
    ValidationStatus,
    DesignStatus,
)

__all__ = [
    "ArchitectModule",
    "DesignDocument",
    "DesignRequirement",
    "ValidatedDesign",
    "ValidationResult",
    "ValidationStatus",
    "DesignStatus",
]
```

---

## 5. エラー処理

`architect/errors.py` にて Foundation の `errors.py` 例外階層を継承したArchitect固有例外を定義する。新しい基底例外は追加しない(Foundation 3.6の制約)。

```python
from __future__ import annotations

from foundation.errors import NotFoundError, ValidationError


class PlanAnalysisError(ValidationError):
    """Execution Planの分析に失敗した場合(必須フィールド欠落・Task List空等)。"""


class DesignCreationError(ValidationError):
    """Design Requirementから Design Document を生成できない場合。"""


class DesignValidationError(ValidationError):
    """Design Documentの自己検証(validate_design)で必須項目欠落・内部不整合が検出された場合。"""


class DesignNotFoundError(NotFoundError):
    """指定された design_id に対応する Design Document が存在しない場合。"""
```

運用方針:

- `analyze_plan` / `create_design` / `validate_design` / `publish_design` は、内部で例外を送出せず全て `Result[T]` に変換して返す（モジュール間API戻り値はResult[T]に統一というFoundation F02の方針に従う）。上記例外クラスは `Result.error` に格納するFoundationError系インスタンスとして使用し、呼び出し境界（`module.py`）でtry/exceptにより捕捉してResultへ変換する。
- `ConfigurationError` は `ConfigurationClient.get()` 呼び出し失敗時（`health_check()`内）にそのまま`Result.error`へ伝播させる。
- `ExternalServiceError` はArchitectが外部サービス通信を行わない(2.2 担当しない)ため使用しない。
- `PermissionDeniedError` / `StateTransitionError` はArchitectの責務範囲外のため使用しない（呼び出し元でPermission Manager/State Managerが必要に応じて付与する）。
- 失敗時は安全側に倒す(F00 Safety)。`validate_design`がINVALIDを返した場合、`publish_design`は必ず拒否する。

---

## 6. ロギング仕様

`foundation.logger.get_logger("architect")` を `ArchitectModule.__init__` で1回だけ取得し、インスタンス属性として保持する。出力形式は Foundation規約 `timestamp | module_name | level | message` に従う（フォーマッタ自体はFoundation側が提供）。

M07設計書 4.5節のログ項目（`timestamp`, `workflow_id`, `design_id`, `module_count`, `interface_count`, `result`）を `message` 部にキー=値形式で出力する。

```python
self._logger.info(
    "event=design_created workflow_id=%s design_id=%s module_count=%d interface_count=%d result=%s",
    design_requirement.workflow_id,
    design_document.id,
    len(design_document.module_design),
    len(design_document.interface_design),
    "SUCCESS",
)
```

- 出力タイミング: `analyze_plan` / `create_design` / `validate_design` / `publish_design` の各メソッド終了時（成功・失敗いずれも1回ずつ）。
- 失敗時は `result="FAILURE"` とし、`error`のメッセージ種別（例外クラス名）のみを記録し、Knowledge本文・Secret・Token・Credentialなど機密情報はログへ出力しない(Foundation 3.7 / M07 4.5)。
- `validate_design`実行時は `issue_count`（`ValidationIssue`件数）も追加項目として記録してよいが、M07設計書に明記されたログ項目(`design_id`, `module_count`, `interface_count`, `result`等)を欠落させてはならない。
- Foundation自体の内部ログ(Logger初期化失敗等)はArchitectのログとは区別し、Foundation側の責務とする。

---

## 7. Unit Testケース一覧

`unittest.TestCase` を使用する（pytest不使用）。設計書に明記の「テスト観点」は存在しないため、公開インターフェース(3.5)・制約(4.1〜4.5)・Design Audit所見(5.1〜5.4)から導出する。

### `tests/test_module.py` (`class TestArchitectModule`)

- `test_name_returns_architect`
- `test_health_check_returns_success_result_when_configuration_client_available`
- `test_health_check_returns_failure_result_when_configuration_client_unavailable`
- `test_analyze_plan_returns_success_result_with_design_requirement`
- `test_analyze_plan_returns_failure_result_when_execution_plan_task_list_empty`
- `test_analyze_plan_does_not_mutate_execution_plan_input`（4.2 要求を変更しない）
- `test_create_design_returns_success_result_with_design_document`
- `test_create_design_returns_failure_result_when_requirement_invalid`
- `test_validate_design_returns_valid_status_for_complete_document`
- `test_validate_design_returns_invalid_status_when_required_field_missing`
- `test_publish_design_returns_published_status_when_validation_valid`
- `test_publish_design_returns_failure_result_when_validation_invalid`（4.1/F00 Safety）
- `test_full_pipeline_analyze_create_validate_publish_end_to_end`
- `test_module_does_not_expose_code_generation_or_pr_methods`（4.1 実装・PR作成をしないことの境界確認）

### `tests/test_analyzer.py` (`class TestAnalyzer`)

- `test_analyze_plan_extracts_objective_from_execution_plan`
- `test_analyze_plan_extracts_constraints_from_execution_plan`
- `test_identify_reusable_components_uses_project_context`
- `test_summarize_existing_architecture_uses_architecture_guidelines`
- `test_analyze_plan_raises_plan_analysis_error_on_missing_objective`
- `test_analyze_plan_preserves_original_objective_text`（4.2 要求変更禁止の単体確認）

### `tests/test_designer.py` (`class TestDesigner`)

- `test_create_design_produces_module_design_item_per_reusable_component`
- `test_create_design_produces_interface_design_matching_module_design`
- `test_create_design_copies_constraints_from_requirement`
- `test_create_design_sets_reuse_rationale_when_existing_design_changed`（3.3 理由明記）
- `test_create_design_raises_design_creation_error_on_empty_requirement`
- `test_create_design_sets_status_draft`

### `tests/test_validator.py` (`class TestValidator`)

- `test_validate_design_detects_missing_objective`
- `test_validate_design_detects_empty_module_design`
- `test_validate_design_detects_interface_without_matching_module`
- `test_validate_design_returns_valid_when_all_required_fields_present`
- `test_validate_design_does_not_assess_mvp_conformance`（4.3 Design Auditor責務との境界確認）
- `test_validate_design_does_not_assess_requirement_fulfillment`（4.3 境界確認）

### `tests/test_publisher.py` (`class TestPublisher`)

- `test_publish_design_sets_status_published`
- `test_publish_design_preserves_design_id`
- `test_publish_design_rejects_when_validation_status_invalid`
- `test_publish_design_returns_result_wrapping_design_document`

### `tests/test_errors.py` (`class TestErrors`)

- `test_plan_analysis_error_is_validation_error_subclass`
- `test_design_creation_error_is_validation_error_subclass`
- `test_design_validation_error_is_validation_error_subclass`
- `test_design_not_found_error_is_not_found_error_subclass`

---

## 8. MVP範囲の明記

M07設計書 5.3節「重厚壮大化監査」にて**対象外・削除済み**と判定された以下の機能は、本実装仕様書の対象に含めない。実装時にこれらを推測で追加してはならない。

- 自動アーキテクチャ最適化
- マイクロサービス分割AI
- パフォーマンスシミュレーション
- コスト最適化AI
- UML自動生成
- Infrastructure設計
- Database自動最適化

加えて、M07設計書 2.2節「担当しない」に基づき、以下もArchitect実装の対象外とする。

- 要求分析・Task分解（Plannerの責務）
- コード生成・GitHub操作・Pull Request作成（Executor/PR Creatorの責務）
- コードレビュー（Reviewerの責務）
- 設計品質評価・MVP適合性判定・差し戻し判定（Design Auditorの責務。Architectの`validate_design`は構造的完全性の自己検証のみ）
- Workflow実行制御（State Manager / Command Routerの責務）

本実装仕様書で定義した `DesignRequirement` / `ValidationResult` / `ValidatedDesign` / `ArchitectureGuidelines`（dict型エイリアス）等は、M07設計書に構造の明記がないため必要最小限のフィールドのみを定義した。将来的にFoundation側でこれらがDomain Model(F01)として正式定義された場合は、本仕様書側の定義をそちらへ委譲する（Design Freeze後の変更はFoundation `version.py` の `DESIGN_VERSION` 更新に伴う次バージョンで対応する）。
