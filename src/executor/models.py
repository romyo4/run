"""Executor(M09)固有の作業用dataclass定義(IS09 3節)。

FoundationのDomain Model(F01)のうち`Design`/`Implementation`をそのまま利用し、
Executor固有の属性はこのモジュールでのみ追加する。`foundation.types`の既存属性
(id/created_at/updated_at/metadata)の削除・型変更は行わない。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from foundation.types import Design, Implementation  # F01: Foundation Domain Model


class ChangeType:
    """ファイル変更種別(列挙の代わりにStrで簡潔に表現する)。"""

    CREATED = "created"
    MODIFIED = "modified"


@dataclass(frozen=True)
class RepositoryInfo:
    """入力`repository_information`を表す。単一Repository制約(4.4)の判定基準となる。"""

    repository_id: str
    root_path: Path
    default_branch: str


@dataclass(frozen=True)
class ModifiedFile:
    """実装により変更・作成されたファイル1件を表す。"""

    path: Path  # repository_information.root_path からの相対パス
    change_type: str  # ChangeType.CREATED / ChangeType.MODIFIED
    summary: str  # 変更内容の要約(Codexが生成した説明文)


@dataclass(frozen=True)
class GeneratedTest:
    """生成されたテストコード1件を表す。テストの実行は行わない(対象外)。"""

    path: Path  # 生成先の相対パス
    target_path: Path  # テスト対象実装ファイルの相対パス
    summary: str


@dataclass(frozen=True)
class ImplementationContext:
    """load_design()の出力。implement()への唯一の入力。"""

    workflow_id: str
    design_id: str
    approved_design: Design  # Design Auditorが承認したDesign(F01)
    design_document: Design  # Architectが作成した元のDesign Document(F01)
    project_context: Mapping[str, Any]
    repository_information: RepositoryInfo
    execution_plan: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ExecutionReport:
    """実装結果レポート。成果物3件(Implementation/Modified Files/Generated Tests)の要約。"""

    workflow_id: str
    design_id: str
    repository_id: str
    modified_files: tuple[ModifiedFile, ...]
    generated_tests: tuple[GeneratedTest, ...]
    summary: str
    created_at: datetime


@dataclass(frozen=True)
class ImplementationResult:
    """implement()の出力。"""

    implementation: Implementation  # F01 Domain(id/created_at/updated_at/metadataを含む)
    modified_files: tuple[ModifiedFile, ...]
    generated_tests: tuple[GeneratedTest, ...]
    execution_report: ExecutionReport
