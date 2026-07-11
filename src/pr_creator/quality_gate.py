"""Quality Gate PASS判定ロジック(IS11 2章 quality_gate.py)。

test_report(Tester(M10)成果物)は、実際には`tester.models.TestReport`であり、既に
`quality_gate_result.status`("PASS"/"FAIL")としてQuality Gateの判定結果を保持している
(IS10 3節: `TestReport.quality_gate_result`, `QualityGateResult.status`)。

6項目(build/lint/unit test/integration test/regression test/static analysis)の合否
判定そのものはTester(M10)の責務であり(設計書M10 2.1「品質ゲート判定」)、PR Creatorは
「Testerが既に判定した結果がPASSしているか」を確認するのみで、判定を再計算しない
(設計書M11 2.1は「Pull Request作成」のみを担当し品質判定を含まない。4.2は
「Quality Gate必須」= 既に判定済みの結果を確認する制約であり、PR Creator自身が
判定を行うことは想定していない)。

過去バージョンではtest_report.metadataに`build_passed`等のフラットなbool値6件が
格納されている前提で再判定していたが、Tester側は実際にはそのようなキーを一切
生成しない(TestReport.metadataは既定で空dict)ため、常に未PASS判定となる不整合が
あった(2026-07 統合レビューで是正)。本モジュールはTesterの内部型
(`tester.models.TestReport`)に直接依存せず、ダックタイピングで
`quality_gate_result.status`にのみアクセスする(モジュール間の疎結合を維持する)。

フェイルセーフ方針: 期待する属性が存在しない、またはstatusが"PASS"以外の場合は
「未PASS」として扱う(表にない組み合わせ=Denyという他モジュールと同一の設計思想)。
"""

from __future__ import annotations

from typing import Any

from pr_creator.errors import QualityGateNotPassedError

__all__ = ["is_passed", "ensure_passed"]

_PASS_STATUS = "PASS"


def is_passed(test_report: Any) -> bool:
    """test_reportのQuality GateがPASSしている場合にTrueを返す。

    `test_report.quality_gate_result.status == "PASS"`であるかのみを確認する。
    属性が欠落している場合はフェイルセーフとして未PASS(False)を返す。
    """
    quality_gate_result = getattr(test_report, "quality_gate_result", None)
    if quality_gate_result is None:
        return False
    return getattr(quality_gate_result, "status", None) == _PASS_STATUS


def ensure_passed(test_report: Any) -> None:
    """Quality GateがPASSしていない場合にQualityGateNotPassedErrorを送出する(IS11 4.2)。"""
    if not is_passed(test_report):
        raise QualityGateNotPassedError("Quality Gateが全ての項目でPASSしていないため、Pull Requestを作成できません。")
