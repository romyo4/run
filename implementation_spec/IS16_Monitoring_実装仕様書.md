# IS16 Monitoring 実装仕様書

本書は `M16 Monitoring.txt`(確定済み詳細設計書)を実装可能な形へ具体化したものである。設計書に記載のない機能は追加しない。Foundation(`M00 Foundation.txt`)が定義する F00〜F03・共通エラー階層・ロギング規約・`Result[T]` パターンを前提とする。

---

## 1. モジュール概要

Monitoring は、AI Development Pipeline を構成する各モジュールおよび Workflow の稼働状況を継続的に監視し、システムの健全性を可視化するモジュールである。Workflow(Running/Completed/Failed/Waiting)・Module(Planner〜Notification)・System(CPU/Memory/Disk/Network)の各状態と Metrics(Execution Time/Success Rate/Failure Rate/Retry Count/Queue Length)を収集し、Health Check(Alive/Ready/Healthy)を行った上で Monitoring Report(Health Status/Metrics/Failures/Warnings/Performance Summary)を生成する。責務は監視・状態収集・Report生成に限定され、Workflow制御・コード修正・Pull Request作成・通知文生成・レビュー・Business判断は一切行わない。異常検知後の通知内容・通知チャネルの決定は Notification モジュール(M15)に委譲する。システム状態を変更しない Read Only モジュールであり、閾値は Configuration Manager(M17)経由で取得する。

---

## 2. ファイル構成

`src/monitoring/` 配下に以下のファイルを配置する。

| ファイル | 役割 |
|---|---|
| `__init__.py` | `MonitoringModule` および公開データクラス・Enumの再エクスポート |
| `constants.py` | 監視対象モジュール名・Workflow状態・Health Check項目・Configurationキー名などの定数/Enum定義 |
| `models.py` | Monitoring固有のdataclass定義(F01のDomain Model共通属性規約に準拠) |
| `errors.py` | Monitoring固有の例外定義(Foundationのエラー階層を継承) |
| `collector.py` | `collect()` の実処理を担う `MetricsCollector` |
| `health_checker.py` | `health_check()` / `analyze()` の実処理を担う `HealthChecker` |
| `reporter.py` | `report()` の実処理を担う `ReportGenerator` |
| `monitoring_module.py` | `BaseModule` を継承した公開インターフェース本体 `MonitoringModule` |
| `tests/__init__.py` | テストパッケージ初期化 |
| `tests/test_models.py` | dataclass生成・バリデーションのテスト |
| `tests/test_collector.py` | `collect()` のテスト |
| `tests/test_health_checker.py` | `analyze()` / `health_check()` のテスト |
| `tests/test_reporter.py` | `report()` のテスト |
| `tests/test_monitoring_module.py` | `MonitoringModule` 全体の結合テスト |

Foundation(`foundation.*`)は既存モジュールとして import 前提とし、本仕様では変更しない。

---

## 3. データクラス定義

Foundation F01 の共通属性規約(`id` / `created_at` / `updated_at` / `metadata`)に従い、Monitoring固有のDomainをすべて `models.py` に定義する。これらは Foundation `types.py` の共通Domain一覧(Task/Workflow/…)を再定義するものではなく、Monitoringが自身の監視対象・成果物を表現するために追加するモジュール固有dataclassである(Foundation 3.3「モジュール固有の属性はモジュール側の詳細設計書で追加定義する」に基づく)。

```python
# constants.py
from enum import Enum


class MonitoredModuleName(str, Enum):
    """3.2 監視対象 Module 一覧"""
    PLANNER = "Planner"
    ARCHITECT = "Architect"
    DESIGN_AUDITOR = "Design Auditor"
    EXECUTOR = "Executor"
    TESTER = "Tester"
    PR_CREATOR = "PR Creator"
    REVIEWER = "Reviewer"
    WEEKLY_REVIEWER = "Weekly Reviewer"
    SCHEDULER = "Scheduler"
    NOTIFICATION = "Notification"


class WorkflowState(str, Enum):
    """3.2 監視対象 Workflow 状態"""
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    WAITING = "Waiting"


class HealthCheckItem(str, Enum):
    """3.3 Health Check 確認項目"""
    ALIVE = "Alive"
    READY = "Ready"
    HEALTHY = "Healthy"


# Configuration Manager(M17)から取得する閾値キー(F03 ConfigurationClient経由)
CONFIG_KEY_EXECUTION_TIME_THRESHOLD_MINUTES = "execution_time_threshold_minutes"
CONFIG_KEY_FAILURE_RATE_THRESHOLD_PERCENT = "failure_rate_threshold_percent"
CONFIG_KEY_RETRY_COUNT_THRESHOLD = "retry_count_threshold"
```

```python
# models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from monitoring.constants import MonitoredModuleName, WorkflowState


# --- 3.1 入力側(collect()の入力を構成する要素) ---

@dataclass
class WorkflowStatus:
    """入力: workflow_status の1件分"""
    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    workflow_id: str
    state: WorkflowState


@dataclass
class ModuleStatus:
    """入力: module_status の1件分"""
    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    module: MonitoredModuleName
    last_heartbeat_at: datetime | None
    is_responding: bool


@dataclass
class SystemResourceStatus:
    """入力: system_metrics(CPU/Memory/Disk/Network)"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io_bytes_per_sec: float


@dataclass
class ExecutionLogEntry:
    """入力: execution_log の1件分(4.5 Logging項目に準拠)"""
    timestamp: datetime
    workflow_id: str
    module: MonitoredModuleName
    execution_time_seconds: float
    is_failure: bool


@dataclass
class SystemStatus:
    """collect() の入力(3.5)。workflow_status/module_status/system_metrics/execution_log の集約"""
    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    workflows: list[WorkflowStatus]
    modules: list[ModuleStatus]
    system_resources: SystemResourceStatus
    execution_log: list[ExecutionLogEntry]


# --- 3.5 collect() の出力 / analyze() の入力 ---

@dataclass
class WorkflowMetrics:
    workflow_id: str
    state: WorkflowState
    execution_time_seconds: float


@dataclass
class ModuleMetrics:
    module: MonitoredModuleName
    execution_time_seconds: float
    success_rate: float
    failure_rate: float
    retry_count: int
    queue_length: int


@dataclass
class Metrics:
    """3.2 Metrics(Execution Time/Success Rate/Failure Rate/Retry Count/Queue Length)"""
    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    collected_at: datetime
    system_resources: SystemResourceStatus
    workflow_metrics: list[WorkflowMetrics]
    module_metrics: list[ModuleMetrics]


# --- 3.3/3.5 health_check() / analyze() の出力 ---

@dataclass
class ModuleHealth:
    """3.3 Health Check(Alive/Ready/Healthy)の1モジュール分の結果"""
    module: MonitoredModuleName
    alive: bool
    ready: bool
    healthy: bool

    @property
    def is_healthy(self) -> bool:
        """3.5 health_check() 出力(Healthy/Unhealthy)の判定"""
        return self.alive and self.ready and self.healthy


# --- 3.5 analyze() の出力 / report() の入力 ---

@dataclass
class HealthStatus:
    """3.4 Monitoring Report の構成要素: Health Status"""
    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    evaluated_at: datetime
    overall_healthy: bool
    module_health: list[ModuleHealth]
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


# --- 3.4 report() の出力 ---

@dataclass
class PerformanceSummary:
    """3.4 Monitoring Report の構成要素: Performance Summary"""
    average_execution_time_seconds: float
    success_rate: float
    failure_rate: float
    total_workflows: int


@dataclass
class MonitoringReport:
    """3.4 Monitoring Report(Health Status/Metrics/Failures/Warnings/Performance Summary)"""
    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    health_status: HealthStatus
    metrics: Metrics
    failures: list[str]
    warnings: list[str]
    performance_summary: PerformanceSummary
```

---

## 4. クラス・関数シグネチャ

### 4.1 公開インターフェース(3.5準拠) — `monitoring_module.py`

`BaseModule`(F02)を継承し、`collect()` / `analyze()` / `report()` / `health_check()` を設計書3.5のシグネチャ通りに公開する。

`BaseModule.health_check(self) -> Result[bool]` はモジュール自身(Monitoring自体)の稼働確認を意味するF02契約だが、M16 3.5の `health_check()` は「監視対象Moduleの健全性」を確認するMonitoring固有の公開APIであり、対象を表す引数を持つ。両者は責務が異なるため、`module` 引数の有無で分岐する単一メソッドとして統合する(メソッド名を分けて新規APIを追加することはしない)。

```python
# monitoring_module.py
from foundation.base_module import BaseModule
from foundation.result import Result

from monitoring.constants import MonitoredModuleName
from monitoring.models import HealthStatus, Metrics, MonitoringReport, SystemStatus
from monitoring.collector import MetricsCollector
from monitoring.health_checker import HealthChecker
from monitoring.reporter import ReportGenerator


class MonitoringModule(BaseModule):
    """M16 Monitoring の公開インターフェース本体。Read Only。"""

    def __init__(
        self,
        collector: MetricsCollector,
        health_checker: HealthChecker,
        reporter: ReportGenerator,
    ) -> None: ...

    def name(self) -> str:
        """F02 BaseModule契約。'Monitoring' を返す。"""
        ...

    def health_check(self, module: MonitoredModuleName | None = None) -> Result[bool]:
        """
        module=None: F02 BaseModule契約(Monitoring自身のAlive/Ready/Healthy確認)。
        module指定時: 3.5 health_check()(指定Moduleの Healthy/Unhealthy 判定)。
        """
        ...

    def collect(self, system_status: SystemStatus) -> Result[Metrics]:
        """3.5 collect(): System Status -> Metrics"""
        ...

    def analyze(self, metrics: Metrics) -> Result[HealthStatus]:
        """3.5 analyze(): Metrics -> Health Status(Performance Analysisを含む)"""
        ...

    def report(self, health_status: HealthStatus, metrics: Metrics) -> Result[MonitoringReport]:
        """
        3.5 report(): Health Status -> Monitoring Report。
        Monitoring Reportは Metrics も構成要素として含む(3.4)ため、
        直前の collect() で得た Metrics を併せて受け取る。
        """
        ...
```

### 4.2 内部実装クラス

```python
# collector.py
from foundation.result import Result
from monitoring.models import Metrics, SystemStatus


class MetricsCollector:
    """3.5 collect() の実処理。System Status から Metrics を集計する。"""

    def collect(self, system_status: SystemStatus) -> Result[Metrics]: ...
```

```python
# health_checker.py
from foundation.result import Result
from monitoring.constants import MonitoredModuleName
from monitoring.models import HealthStatus, Metrics, ModuleHealth, ModuleStatus


class HealthChecker:
    """3.3 Health Check(Alive/Ready/Healthy)と 3.5 analyze() の実処理。閾値はConfigurationClient経由(F03/4.4)。"""

    def check_module(self, module: MonitoredModuleName, module_status: ModuleStatus) -> Result[ModuleHealth]:
        """1モジュール分の Alive/Ready/Healthy を判定する。"""
        ...

    def analyze(self, metrics: Metrics) -> Result[HealthStatus]:
        """Metricsと閾値(Execution Time/Failure Rate/Retry Count)からHealth Statusを導出する。"""
        ...
```

```python
# reporter.py
from foundation.result import Result
from monitoring.models import HealthStatus, Metrics, MonitoringReport


class ReportGenerator:
    """3.4/3.5 report() の実処理。Health StatusとMetricsからMonitoring Reportを生成する。"""

    def generate(self, health_status: HealthStatus, metrics: Metrics) -> Result[MonitoringReport]: ...
```

### 4.3 Result[T] の扱い

- すべての公開メソッドは `Result[T]` でラップして返す(F02)。
- `health_check()` は真偽値判定APIのため `Result[bool]`(F02の`check_permission()`と同様の扱い)。
- 失敗時は `Result(success=False, value=None, error=<FoundationErrorサブクラス>)` を返し、例外を呼び出し元へ送出しない(モジュール境界では例外を捕捉し `Result` に変換する)。

---

## 5. エラー処理

Foundationのエラー階層(`FoundationError` 基底: `ValidationError` / `NotFoundError` / `PermissionDeniedError` / `StateTransitionError` / `ConfigurationError` / `ExternalServiceError`)をそのまま利用し、Monitoring固有の新しい基底例外は追加しない(設計書に記載のないエラー体系を持ち込まない)。

```python
# errors.py
from foundation.errors import ExternalServiceError, NotFoundError, ValidationError


class UnknownMonitoredModuleError(NotFoundError):
    """health_check()/check_module() に未知の MonitoredModuleName が渡された場合。"""


class MetricsCollectionError(ExternalServiceError):
    """監視対象Moduleからの状態取得に失敗した場合(モジュール境界を越えた取得の失敗)。"""


class InvalidSystemStatusError(ValidationError):
    """collect() へ渡された SystemStatus が不正な場合(必須項目欠落等)。"""
```

適用方針:

| ケース | 例外 |
|---|---|
| `collect()` の `system_status` が `None` または必須フィールド欠落 | `InvalidSystemStatusError`(`validation.require_not_none` 等を利用) |
| `health_check(module=...)` に `MonitoredModuleName` 以外の未知値 | `UnknownMonitoredModuleError` |
| 監視対象Moduleの状態取得(heartbeat等)がタイムアウト・失敗 | `MetricsCollectionError` |
| `ConfigurationClient.get()`(閾値取得)が失敗 | Configuration Manager側が返す `ConfigurationError` をそのまま `Result.error` に伝播 |

いずれも `MonitoringModule` の各公開メソッド内で捕捉し、`Result(success=False, error=...)` として返す。Monitoring自体はRead Onlyであり、`StateTransitionError` / `PermissionDeniedError` を能動的に送出するケースは想定しない。

---

## 6. ロギング仕様

Foundation `get_logger(module_name)` を用いる。

```python
from foundation.logger import get_logger

logger = get_logger("Monitoring")
```

設計書4.5の記録項目に従い、`collect()` / `analyze()` / `health_check()` の各処理完了時に以下をログ出力する(出力形式は Foundation規約: `timestamp | module_name | level | message`)。

| 項目 | 内容 |
|---|---|
| `timestamp` | ログ出力時刻(loggingが自動付与) |
| `workflow_id` | 対象Workflow ID(Workflow単位の処理時) |
| `module` | 監視対象Module名(Module単位の処理時) |
| `health_status` | Healthy/Unhealthy |
| `execution_time` | 実行時間(秒) |
| `failure_rate` | 失敗率 |
| `warning_count` | 警告件数 |

- 正常収集・正常判定は `INFO` レベル。
- 閾値超過(4.4: Execution Time > 10min, Failure Rate > 20%, Retry Count > 3 等)検知時は `WARNING` レベル。
- `health_check()` で Unhealthy 判定・収集失敗時は `ERROR` レベル。
- Secret・Access Token・Credential はいかなるログにも出力しない(4.5)。`ModuleStatus.metadata` 等に機微情報が混入していないかをログ出力前に検証する。

---

## 7. Unit Testケース一覧(unittest)

設計書に明示的な「テスト観点」節は存在しないため、3章(公開インターフェース)・4章(Constraints)を根拠にテストケースを導出する。`unittest.TestCase` ベースでメソッド名を列挙する。

### `tests/test_models.py`
- `test_workflow_status_holds_common_attributes` — id/created_at/updated_at/metadataが保持されること
- `test_metrics_aggregates_workflow_and_module_metrics`
- `test_module_health_is_healthy_true_when_all_checks_pass`
- `test_module_health_is_healthy_false_when_any_check_fails`
- `test_monitoring_report_contains_all_required_sections`

### `tests/test_collector.py`
- `test_collect_returns_success_result_with_metrics`
- `test_collect_computes_success_rate_and_failure_rate_from_execution_log`
- `test_collect_computes_execution_time_per_workflow`
- `test_collect_returns_failure_result_when_system_status_missing_required_field`
- `test_collect_does_not_mutate_input_system_status`

### `tests/test_health_checker.py`
- `test_check_module_returns_healthy_when_alive_ready_healthy_all_true`
- `test_check_module_returns_unhealthy_when_alive_is_false`
- `test_check_module_returns_unhealthy_when_ready_is_false`
- `test_check_module_returns_unhealthy_when_healthy_is_false`
- `test_check_module_returns_failure_result_for_unknown_module`
- `test_analyze_flags_warning_when_execution_time_exceeds_threshold`
- `test_analyze_flags_warning_when_failure_rate_exceeds_threshold`
- `test_analyze_flags_warning_when_retry_count_exceeds_threshold`
- `test_analyze_reads_thresholds_via_configuration_client`
- `test_analyze_overall_healthy_false_when_any_module_unhealthy`

### `tests/test_reporter.py`
- `test_report_generates_monitoring_report_from_health_status_and_metrics`
- `test_report_includes_performance_summary_totals`
- `test_report_includes_failures_and_warnings_from_health_status`
- `test_report_returns_failure_result_when_health_status_is_none`

### `tests/test_monitoring_module.py`
- `test_name_returns_monitoring`
- `test_health_check_without_module_returns_self_health_result`
- `test_health_check_with_module_returns_module_health_result`
- `test_collect_analyze_report_end_to_end_flow`
- `test_module_does_not_modify_system_state` — Read Only制約(4.3)の確認
- `test_module_does_not_expose_notification_or_workflow_control_api` — 責務外(2.2/4.1/4.2)の確認
- `test_secret_fields_are_not_present_in_log_output` — 4.5 機密情報非出力の確認

---

## 8. MVP範囲の明記

設計書 5.3(重厚壮大化監査)にて **削除済み** と判定された以下の機能は、本実装仕様に一切含めない。

- AI異常検知
- 予兆保全
- Distributed Tracing
- OpenTelemetry統合
- Prometheus Federation
- 自動復旧
- SLA管理
- Capacity Planning

また、設計書 2.2/4.1/4.2 に基づき、以下も本モジュールの実装範囲外とする。

- Workflow制御・実行
- コード修正・Design変更
- Pull Request作成
- 通知内容・通知チャネルの決定(Notificationモジュールの責務)
- レビュー・Business判断

本モジュールは `collect()` / `analyze()` / `report()` / `health_check()` の4公開メソッドと、それを支える収集・判定・Report生成の内部実装のみを実装対象とする。
