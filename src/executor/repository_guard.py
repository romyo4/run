"""単一Repository制約(IS09 4.4)を機械的に強制するファイルアクセスガード。"""

from __future__ import annotations

from pathlib import Path

from executor.errors import RepositoryBoundaryViolationError
from executor.models import RepositoryInfo
from foundation.result import Result


class RepositoryGuard:
    """「Executorが変更できるのは対象Repositoryのみ」(4.4)を強制する。"""

    def ensure_within_repository(self, repository_information: RepositoryInfo, target_path: Path) -> Result[bool]:
        """target_pathがrepository_information.root_path配下であることを検証する。

        配下でない場合(`../`等によるパストラバーサル、別Repositoryの絶対パス指定を含む)は
        Result[bool](success=False, value=False)を返す。
        """
        root = repository_information.root_path.resolve()
        candidate = target_path if target_path.is_absolute() else root / target_path
        resolved = candidate.resolve()

        if resolved == root or root in resolved.parents:
            return Result(success=True, value=True)

        return Result(
            success=False,
            value=False,
            error=RepositoryBoundaryViolationError(f"target_path '{target_path}' is outside repository root '{root}'"),
        )
