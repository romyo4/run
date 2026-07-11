"""Tester(M10)固有例外(IS10 5節)。

Foundationのエラー階層(`FoundationError`)を継承したTester固有例外を定義する。新しい
基底例外は追加せず、既存の`ValidationError` / `ConfigurationError` / `ExternalServiceError`
を継承する。
"""

from __future__ import annotations

from foundation.errors import ConfigurationError, ExternalServiceError, ValidationError

__all__ = [
    "TesterValidationError",
    "TesterConfigurationError",
    "TestExecutionError",
]


class TesterValidationError(ValidationError):
    """execute_tests/validate_quality/publish_reportへの入力(Implementation/TestResult/
    QualityGateResult)がNoneまたは不正な場合に送出。"""


class TesterConfigurationError(ConfigurationError):
    """ConfigurationClient.get("tester", key)による設定取得の失敗、または必須設定値欠落時に送出。"""


class TestExecutionError(ExternalServiceError):
    """Build/Lint/Unit Test/Integration Test/Regression Test/Static Analysis用の外部ツール
    (subprocess)実行自体が失敗(起動不可・タイムアウト・異常終了)した場合に送出。
    テスト結果がFailであること自体はエラーではなく正常な判定結果として扱う。"""
