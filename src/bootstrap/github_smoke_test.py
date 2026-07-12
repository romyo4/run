"""Phase 1-A: GitHub Manager(M20)の実接続を確認する手動スモークテスト。

`run_workflow()`(Planner→...→Reviewer)自体はGitHub Managerを呼び出さないため
(GitHub ManagerはContext Manager・Weekly Reviewerからのみ利用される)、実接続の
確認には本スクリプトを直接実行する。テストスイート(unittest discover)には含めず、
GITHUB_TOKENと実リポジトリが揃った時点でユーザーが手動実行する想定。

使い方:
    GITHUB_TOKEN=ghp_xxx PYTHONPATH=src python -m bootstrap.github_smoke_test owner/repo
"""

import argparse
import sys

from bootstrap.wiring import build_application


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GitHub Manager real-connection smoke test")
    parser.add_argument("repository", help="'owner/repo' 形式のRepository識別子")
    args = parser.parse_args(argv)

    try:
        app = build_application(use_real_github=True)
    except RuntimeError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 1

    result = app.github_manager.get_repository(args.repository)
    if not result.success:
        print(f"get_repository failed: {result.error}", file=sys.stderr)
        return 1

    print(f"OK: {result.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
