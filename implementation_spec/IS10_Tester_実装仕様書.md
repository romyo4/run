# IS10 Tester 実装仕様書

> 本書は `M10 Tester.txt`(確定済み詳細設計書, Design Freeze監査によりQuality Gate PASS後の遷移先をPR Creator(M11)へ修正済み)および `M00 Foundation.txt`(F00〜F03, 共通Result/Error/Logging規約)を唯一の正とする実装仕様書である。設計書に定めのない機能(Performance Test, Load Test, Security Scan等)は実装しない。

---

## 1. モジュール概要

Tester は、AI Development Pipeline において Executor が生成した実装成果物(Implementation)に対して、Build確認・Lint確認・Unit Test・Integration Test・Regression Test・Static Analysisを機械的に実行し、その結果をもとに品質ゲート(Quality Gate)を判定するモジュールである。品質ゲートをすべて満たした場合(PASS)は成果物を PR Creator(M11)へ引き渡し、一つでも満たさない場合(FAIL)は Executor(M09)へ差し戻す。Tester はテストの実行と結果評価のみを責務とし、コード修正・テストコード修正・設計変更・Pull Request作成・GitHub操作・コードレビュー・マージ判定は一切行わない。

---

## 2. ファイル構成

```text
src/tester/
├── __init__.py                    # 公開インターフェース(Tester, execute_tests/validate_quality/publish_report)のエクスポート
├── tester.py                      # Testerクラス本体(BaseModule継承)。公開インターフェース3関数の実装
├── models.py                      # BuildReport/LintReport/TestExecutionReport/StaticAnalysisReport/
│                                   #   QualityGateItemResult/QualityGateResult/TestReport/TesterConfig等のdataclass定義
├── quality_gate.py                # 品質ゲート判定ロジック(Build/Lint/Unit/Integration/Regression/Static Analysisの各判定)
├── report_publisher.py            # Test Report生成ロジック(publish_reportの実処理)
├── errors.py                      # Tester固有例外(Foundationのエラー階層を継承)
├── logging_utils.py               # ログ出力補助(所定8項目の整形、Secret/Token/Credentialのマスク処理)
├── runners/
│   ├── __init__.py
│   ├── build_runner.py            # Build確認の実行(run_build_check)
│   ├── lint_runner.py             # Lint確認の実行(run_lint_check)
│   ├── unit_test_runner.py        # Unit Testの実行(run_unit_tests)
│   ├── integration_test_runner.py # Integration Testの実行(run_integration_tests)
│   ├── regression_test_runner.py  # Regression Testの実行(run_regression_tests)
│   └── static_analysis_runner.py  # Static Analysisの実行(run_static_analysis)
└── tests/
    ├── __init__.py
    ├── test_tester.py
    ├── test_models.py
    ├── test_quality_gate.py
    ├── test_report_publisher.py
    ├── test_build_runner.py
    ├── test_lint_runner.py
    ├── test_unit_test_runner.py
    ├── test_integration_test_runner.py
    ├── test_regression_test_runner.py
    └── test_static_analysis_runner.py
```

各 `runners/*.py` は外部ツール(ビルドコマンド・Linter・テストランナー・静的解析ツール)を subprocess 経由で呼び出す薄いアダプタとし、Foundation原則の Adapter Pattern に従う。判定ロジック(合否基準)は `quality_gate.py` に集約し、`runners/` 側には持たせない。

---

## 3. データクラス定義

Foundation `foundation/types.py` が定義する `TestResult`(F01 Domain Model、共通属性 `id / created_at / updated_at / metadata` を持つ)を、Tester のモジュール固有属性を追加して利用する。属性追加はFoundation 3.3節の規約に従い、本仕様書側で定義しFoundation側の型定義に反映する(Design Freeze後のため既存属性の削除・型変更は行わない)。

```python
# foundation.types.TestResult へ追加するモジュール固有属性(Tester)
# id / created_at / updated_at / metadata は Foundation 共通定義を継承
@dataclass
class TestResult:
    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    # --- Tester固有属性 ---
    workflow_id: str
    build_report: "BuildReport"
    lint_report: "LintReport"
    unit_test_report: "TestExecutionReport"
    integration_test_report: "TestExecutionReport"
    regression_test_report: "TestExecutionReport"
    static_analysis_report: "StaticAnalysisReport"
    duration_seconds: float
```

以下は `src/tester/models.py` に定義する Tester 固有のデータクラス。

```python
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


class BuildStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass
class BuildReport:
    status: BuildStatus
    command: list[str]
    duration_seconds: float
    log_excerpt: str
    error_message: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status is BuildStatus.SUCCESS


@dataclass
class LintIssue:
    file_path: Path
    line: int
    rule: str
    severity: str  # "error" | "warning"
    message: str


@dataclass
class LintReport:
    error_count: int
    warning_count: int
    issues: list[LintIssue]
    duration_seconds: float

    @property
    def has_error(self) -> bool:
        return self.error_count > 0


@dataclass
class TestCaseResult:
    name: str
    passed: bool
    duration_seconds: float
    failure_message: str | None = None


@dataclass
class TestExecutionReport:
    """Unit Test / Integration Test / Regression Test 共通の実行結果"""
    test_type: str  # "unit" | "integration" | "regression"
    total: int
    passed: int
    failed: int
    skipped: int
    cases: list[TestCaseResult]
    duration_seconds: float

    @property
    def is_pass(self) -> bool:
        return self.total > 0 and self.failed == 0


@dataclass
class StaticAnalysisIssue:
    file_path: Path
    line: int
    rule: str
    severity: str  # "critical" | "major" | "minor" | "info"
    message: str


@dataclass
class StaticAnalysisReport:
    critical_count: int
    issues: list[StaticAnalysisIssue]
    duration_seconds: float

    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0


@dataclass
class QualityGateItemResult:
    item_name: str  # "build" | "lint" | "unit_test" | "integration_test" | "regression_test" | "static_analysis"
    passed: bool
    detail: str


@dataclass
class QualityGateResult:
    id: str
    workflow_id: str
    test_result: "TestResult"
    items: list[QualityGateItemResult]
    status: str  # "PASS" | "FAIL"
    evaluated_at: datetime
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_pass(self) -> bool:
        return self.status == "PASS"


@dataclass
class TestReport:
    id: str
    workflow_id: str
    quality_gate_result: QualityGateResult
    build_report: BuildReport
    lint_report: LintReport
    unit_test_report: TestExecutionReport
    integration_test_report: TestExecutionReport
    regression_test_report: TestExecutionReport
    static_analysis_report: StaticAnalysisReport
    summary: str
    duration_seconds: float
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TesterConfig:
    """F03: ConfigurationClient.get("tester", key) 経由で取得する設定値の型"""
    build_command: list[str]
    lint_command: list[str]
    unit_test_command: list[str]
    integration_test_command: list[str]
    regression_test_command: list[str]
    static_analysis_command: list[str]
    command_timeout_seconds: int
```

`QualityGateResult.test_result` に `TestResult` を保持することで、`publish_report()` は `QualityGateResult` のみを入力として `TestReport` を構築できる(設計書3.4の公開インターフェース定義を満たす)。

---

## 4. クラス・関数シグネチャ

### 4.1 Testerクラス(公開インターフェース)

```python
from foundation.base_module import BaseModule
from foundation.result import Result
from foundation.types import Implementation, TestResult

class Tester(BaseModule):
    def __init__(self, config: TesterConfig, logger: "logging.Logger") -> None: ...

    def name(self) -> str: ...

    def health_check(self) -> Result[bool]: ...

    def execute_tests(self, implementation: Implementation) -> Result[TestResult]:
        """Build/Lint/Unit/Integration/Regression/Static Analysisを順次実行しTestResultを返す。"""

    def validate_quality(self, test_result: TestResult) -> Result[QualityGateResult]:
        """TestResultの各項目を品質ゲート基準(3.5節)で判定しQualityGateResultを返す。"""

    def publish_report(self, quality_gate_result: QualityGateResult) -> Result[TestReport]:
        """QualityGateResultからTestReportを生成する。PASS時はPR Creatorへ、FAIL時はExecutorへの
        引き渡し判断は呼び出し元(Command Router / Workflow制御)が行い、Tester自身は遷移制御を持たない。"""
```

Tester は遷移先の呼び出し(PR Creator起動やExecutorへの差し戻し実行)そのものは行わない。`QualityGateResult.status`("PASS"/"FAIL")および`TestReport`を戻り値として返すことで、呼び出し元のWorkflow制御(Command Router等)が3.6節のフロー(PASS→PR Creator, FAIL→Executor)を実現する。これはTesterの責務(2.2節: レビュー・マージ判定・ビジネス判断を行わない)と整合する。

### 4.2 品質ゲート判定ロジック(`quality_gate.py`)

```python
def evaluate_quality_gate(
    test_result: TestResult,
) -> Result[list[QualityGateItemResult]]:
    """6項目(Build/Lint/Unit/Integration/Regression/Static Analysis)すべてを判定する。"""

def judge_build(build_report: BuildReport) -> QualityGateItemResult:
    """条件: Build == Success"""

def judge_lint(lint_report: LintReport) -> QualityGateItemResult:
    """条件: Lint Error件数 == 0(Warningは判定対象外)"""

def judge_unit_test(report: TestExecutionReport) -> QualityGateItemResult:
    """条件: Unit Test すべてPass"""

def judge_integration_test(report: TestExecutionReport) -> QualityGateItemResult:
    """条件: Integration Test すべてPass"""

def judge_regression_test(report: TestExecutionReport) -> QualityGateItemResult:
    """条件: Regression Test すべてPass"""

def judge_static_analysis(report: StaticAnalysisReport) -> QualityGateItemResult:
    """条件: Critical Errorなし(critical_count == 0)"""

def determine_gate_status(items: list[QualityGateItemResult]) -> str:
    """全項目passed=Trueの場合のみ'PASS'、それ以外は'FAIL'を返す(設計書3.5節)。"""
```

### 4.3 実行系(`runners/*.py`)

```python
# build_runner.py
def run_build_check(implementation: Implementation, config: TesterConfig) -> Result[BuildReport]: ...

# lint_runner.py
def run_lint_check(implementation: Implementation, config: TesterConfig) -> Result[LintReport]: ...

# unit_test_runner.py
def run_unit_tests(implementation: Implementation, config: TesterConfig) -> Result[TestExecutionReport]: ...

# integration_test_runner.py
def run_integration_tests(implementation: Implementation, config: TesterConfig) -> Result[TestExecutionReport]: ...

# regression_test_runner.py
def run_regression_tests(implementation: Implementation, config: TesterConfig) -> Result[TestExecutionReport]: ...

# static_analysis_runner.py
def run_static_analysis(implementation: Implementation, config: TesterConfig) -> Result[StaticAnalysisReport]: ...
```

各runnerはコマンド実行結果(標準出力・終了コード)を解析してdataclassへマッピングするのみで、判定(合否)ロジックは持たない(判定は`quality_gate.py`に集約)。

### 4.4 レポート生成(`report_publisher.py`)

```python
def build_test_report(quality_gate_result: QualityGateResult) -> Result[TestReport]:
    """QualityGateResult.test_resultから各Reportを取り出しTestReportを構築する。"""
```

### 4.5 実行フロー(execute_tests内部処理順序)

設計書3.6節に従い、以下の順序で実行し、いずれかがツール実行自体に失敗した場合(判定結果ではなく実行エラー)は即座に`Result[TestResult]`として失敗を返す。

```text
Build Check → Lint Check → Unit Test → Integration Test → Regression Test → Static Analysis → TestResult構築
```

---

## 5. エラー処理

`src/tester/errors.py` にて、Foundationのエラー階層(`FoundationError`)を継承したTester固有例外を定義する。新しい基底例外は追加せず、既存の`ValidationError` / `ConfigurationError` / `ExternalServiceError`を継承する。

```python
from foundation.errors import ValidationError, ConfigurationError, ExternalServiceError

class TesterValidationError(ValidationError):
    """execute_tests/validate_quality/publish_reportへの入力(Implementation/TestResult/
    QualityGateResult)がNoneまたは不正な場合に送出。"""

class TesterConfigurationError(ConfigurationError):
    """ConfigurationClient.get("tester", key)による設定取得の失敗、または必須設定値欠落時に送出。"""

class TestExecutionError(ExternalServiceError):
    """Build/Lint/Unit Test/Integration Test/Regression Test/Static Analysis用の外部ツール
    (subprocess)実行自体が失敗(起動不可・タイムアウト・異常終了)した場合に送出。
    テスト結果がFailであること自体はエラーではなく正常な判定結果として扱う。"""
```

- 各公開インターフェース(`execute_tests` / `validate_quality` / `publish_report`)は、内部で例外を捕捉し `Result[T](success=False, value=None, error=<FoundationError>)` として返却する。例外を呼び出し元へ送出しない。
- 「テストが失敗した」ことと「テスト実行そのものが失敗した」ことを区別する。前者は`TestExecutionReport.is_pass=False`として正常にResult成功で返し、品質ゲートFAILとして扱う。後者(ツール実行不能等)のみ`TestExecutionError`を用いる。
- Foundation 4.1「Safety: 失敗時は安全側(Deny/Fail)に倒す」原則に従い、実行エラー発生時は当該項目を`passed=False`として品質ゲートをFAILとする(PASS側へ倒さない)。
- 設定値変更不可の制約(設計書4.4)に反し、実行中に`TesterConfig`が変更された場合は`TesterConfigurationError`とする(`execute_tests`呼び出し開始時に一度だけ`TesterConfig`を取得し、以降のrunner呼び出しへ同一インスタンスを渡すことで担保する)。

---

## 6. ロギング仕様

`foundation.logger.get_logger("tester")` により取得したLoggerを`Tester.__init__`で保持し、全ログ出力に使用する。標準ライブラリ`logging`のみを使用する。

出力項目(設計書4.5節、固定8項目):

```text
timestamp | workflow_id | build_result | lint_result | test_result | quality_gate | duration | result
```

- `timestamp`: ログ出力時刻(Foundationのログフォーマット`timestamp | module_name | level | message`のtimestampをそのまま利用)
- `workflow_id`: 対象ワークフローID
- `build_result`: `BuildReport.status`("success"/"failure")
- `lint_result`: `LintReport.has_error`が`False`なら"no_error"、`True`なら"error"
- `test_result`: Unit/Integration/Regressionの合算結果("pass"/"fail")
- `quality_gate`: `QualityGateResult.status`("PASS"/"FAIL")
- `duration`: 実行全体の所要時間(秒)
- `result`: 当該ログイベント自体の成否("success"/"failure")

実装方針(`logging_utils.py`):

```python
def build_log_message(
    workflow_id: str,
    build_result: str,
    lint_result: str,
    test_result: str,
    quality_gate: str,
    duration_seconds: float,
    result: str,
) -> str:
    """上記8項目(timestampはlogging側で付与)をkey=value形式の1行に整形する。"""

def sanitize_for_log(text: str) -> str:
    """ログへ出力する文字列(コマンド標準出力・エラーメッセージ等)から、
    Secret/Token/Credentialに該当しうる文字列(例: 'token', 'password', 'secret',
    'api_key', 'credential'等をキー名に含む行、および長い英数字トークン様文字列)を
    正規表現でマスク('***REDACTED***')してから返す。"""
```

- `BuildReport.log_excerpt` / `LintIssue.message` / `StaticAnalysisIssue.message` 等、外部ツールの生出力に由来する文字列は、ログへ出力する前に必ず`sanitize_for_log()`を通す。
- 生の標準出力・標準エラー全文はログへ出力しない。ログへは件数・ステータス等の要約情報のみを出力し、詳細はTest Report(成果物)側にのみ保持する。
- 環境変数(APIキー・GitHubトークン等)を明示的にログへ渡す実装を行わない。runner内でsubprocess実行時に使用する環境変数はログ出力対象から除外する。

---

## 7. Unit Testケース一覧(unittest)

### `test_tester.py`
- `test_execute_tests_returns_success_result_when_all_stages_succeed`
- `test_execute_tests_returns_failure_result_when_implementation_is_none`
- `test_execute_tests_returns_failure_result_when_build_execution_raises_test_execution_error`
- `test_execute_tests_stops_pipeline_on_build_tool_execution_error`
- `test_execute_tests_fetches_tester_config_once_per_call`
- `test_validate_quality_returns_pass_result_when_all_items_pass`
- `test_validate_quality_returns_fail_result_when_any_item_fails`
- `test_validate_quality_returns_failure_result_when_test_result_is_none`
- `test_publish_report_returns_test_report_when_quality_gate_result_is_valid`
- `test_publish_report_returns_failure_result_when_quality_gate_result_is_none`
- `test_health_check_returns_success_result`
- `test_name_returns_tester`

### `test_models.py`
- `test_build_report_is_success_true_when_status_success`
- `test_build_report_is_success_false_when_status_failure`
- `test_lint_report_has_error_true_when_error_count_positive`
- `test_lint_report_has_error_false_when_error_count_zero`
- `test_test_execution_report_is_pass_true_when_no_failures_and_total_positive`
- `test_test_execution_report_is_pass_false_when_any_failure`
- `test_test_execution_report_is_pass_false_when_total_is_zero`
- `test_static_analysis_report_has_critical_true_when_critical_count_positive`
- `test_static_analysis_report_has_critical_false_when_critical_count_zero`
- `test_quality_gate_result_is_pass_true_when_status_pass`
- `test_quality_gate_result_is_pass_false_when_status_fail`

### `test_quality_gate.py`
- `test_judge_build_passes_on_success_status`
- `test_judge_build_fails_on_failure_status`
- `test_judge_lint_passes_when_no_error`
- `test_judge_lint_fails_when_error_count_positive`
- `test_judge_lint_passes_when_only_warnings_present`
- `test_judge_unit_test_passes_when_all_pass`
- `test_judge_unit_test_fails_when_any_case_fails`
- `test_judge_integration_test_passes_when_all_pass`
- `test_judge_integration_test_fails_when_any_case_fails`
- `test_judge_regression_test_passes_when_all_pass`
- `test_judge_regression_test_fails_when_any_case_fails`
- `test_judge_static_analysis_passes_when_no_critical_error`
- `test_judge_static_analysis_fails_when_critical_error_present`
- `test_determine_gate_status_returns_pass_when_all_items_passed`
- `test_determine_gate_status_returns_fail_when_one_item_failed`
- `test_determine_gate_status_returns_fail_when_all_items_failed`
- `test_evaluate_quality_gate_returns_six_items_in_fixed_order`

### `test_report_publisher.py`
- `test_build_test_report_includes_all_six_reports`
- `test_build_test_report_preserves_quality_gate_status`
- `test_build_test_report_returns_failure_result_when_test_result_missing_in_gate_result`

### `test_build_runner.py`
- `test_run_build_check_returns_success_status_on_zero_exit_code`
- `test_run_build_check_returns_failure_status_on_nonzero_exit_code`
- `test_run_build_check_returns_failure_result_when_command_not_found`
- `test_run_build_check_returns_failure_result_on_timeout`

### `test_lint_runner.py`
- `test_run_lint_check_parses_error_and_warning_counts`
- `test_run_lint_check_returns_zero_errors_when_no_issues`
- `test_run_lint_check_returns_failure_result_on_tool_execution_error`

### `test_unit_test_runner.py`
- `test_run_unit_tests_returns_report_with_all_cases_passed`
- `test_run_unit_tests_returns_report_with_failed_case_recorded`
- `test_run_unit_tests_returns_failure_result_on_tool_execution_error`

### `test_integration_test_runner.py`
- `test_run_integration_tests_returns_report_with_all_cases_passed`
- `test_run_integration_tests_returns_report_with_failed_case_recorded`
- `test_run_integration_tests_returns_failure_result_on_tool_execution_error`

### `test_regression_test_runner.py`
- `test_run_regression_tests_returns_report_with_all_cases_passed`
- `test_run_regression_tests_returns_report_with_failed_case_recorded`
- `test_run_regression_tests_returns_failure_result_on_tool_execution_error`

### `test_static_analysis_runner.py`
- `test_run_static_analysis_returns_zero_critical_when_no_issues`
- `test_run_static_analysis_returns_critical_count_matching_issues`
- `test_run_static_analysis_returns_failure_result_on_tool_execution_error`

---

## 8. MVP範囲の明記

設計書5.3節「重厚壮大化監査」にて対象外・削除済みとされた以下の機能は、本実装仕様書においても一切実装しない。

- Performance Test
- Load Test
- Security Scan
- Fuzz Testing
- Mutation Testing
- Chaos Engineering
- Cross Platform Matrix
- AI品質判定

また、以下は設計書2.2節・4章の制約により明示的に実装対象外とする。

- コード修正・テストコード修正・Design変更(4.1)
- コード品質評価・ビジネス評価・マージ判定(4.2)
- 手動テスト(4.3、MVPでは自動実行のみ)
- Pull Request作成・GitHub操作(責務外、M11 PR Creatorが担当)
- コードレビュー(責務外、M12 Reviewerが担当)

Tester が実装するのは、設計書3.2節に定める7項目(Build確認・Lint確認・Unit Test・Integration Test・Regression Test・Static Analysis・Test Report生成)と、3.5節の品質ゲート判定(6項目すべてを満たした場合のみPASS)、および3.4節の公開インターフェース(`execute_tests` / `validate_quality` / `publish_report`)のみである。
