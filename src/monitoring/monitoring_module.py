"""M16 Monitoring: 公開インターフェース本体(IS16 4.1)。

`BaseModule`(F02)を継承し、`collect()` / `analyze()` / `report()` / `health_check()` を
設計書3.5のシグネチャ通りに公開する。監視・状態収集・Report生成のみを担当し、
Workflow制御・コード修正・Pull Request作成・通知文生成・レビュー・Business判断は
一切行わない(設計書2.2/4.1/4.2)。システム状態を変更しないRead Onlyモジュールである(4.3)。

`BaseModule.health_check(self) -> Result[bool]` はMonitoring自身の稼働確認を意味するF02契約だが、
M16 3.5の `health_check()` は監視対象Moduleの健全性を確認するMonitoring固有の公開APIであり、
対象を表す引数を持つ。両者は責務が異なるため、`module` 引数の有無で分岐する単一メソッドとして
統合する(メソッド名を分けて新規APIを追加することはしない)。
"""

from foundation.base_module import BaseModule
from foundation.errors import FoundationError
from foundation.logger import get_logger
from foundation.result import Result
from monitoring.collector import MetricsCollector
from monitoring.constants import MonitoredModuleName
from monitoring.errors import UnknownMonitoredModuleError
from monitoring.health_checker import HealthChecker
from monitoring.models import HealthStatus, Metrics, ModuleStatus, MonitoringReport, SystemStatus
from monitoring.reporter import ReportGenerator

logger = get_logger("Monitoring")

MODULE_NAME = "Monitoring"


class MonitoringModule(BaseModule):
    """M16 Monitoring の公開インターフェース本体。Read Only。"""

    def __init__(
        self,
        collector: MetricsCollector,
        health_checker: HealthChecker,
        reporter: ReportGenerator,
    ) -> None:
        self._collector = collector
        self._health_checker = health_checker
        self._reporter = reporter
        # 直近の collect() 呼び出しで観測した監視対象Moduleごとの最新状態(3.5 health_check()の
        # 対象参照に利用する)。Read Onlyのため、外部から渡されたSystemStatusそのものは変更しない。
        self._latest_module_statuses: dict[MonitoredModuleName, ModuleStatus] = {}

    def name(self) -> str:
        """F02 BaseModule契約。'Monitoring' を返す。"""
        return MODULE_NAME

    def health_check(self, module: MonitoredModuleName | None = None) -> Result[bool]:
        """
        module=None: F02 BaseModule契約(Monitoring自身のAlive/Ready/Healthy確認)。
        module指定時: 3.5 health_check()(指定Moduleの Healthy/Unhealthy 判定)。
        """
        if module is None:
            # Monitoring自体はRead Only・外部依存を持たない収集/判定処理のみのため、常に稼働可能。
            return Result(success=True, value=True)

        try:
            if not isinstance(module, MonitoredModuleName):
                raise UnknownMonitoredModuleError(f"Unknown monitored module: {module!r}")

            module_status = self._latest_module_statuses.get(module)
            if module_status is None:
                raise UnknownMonitoredModuleError(f"no observed status for monitored module: {module.value}")
        except FoundationError as exc:
            logger.error("health_check failed | module=%s | error=%s", module, exc.message)
            return Result(success=False, error=exc)

        check_result = self._health_checker.check_module(module, module_status)
        if not check_result.success:
            return Result(success=False, error=check_result.error)

        assert check_result.value is not None
        return Result(success=True, value=check_result.value.is_healthy)

    def collect(self, system_status: SystemStatus) -> Result[Metrics]:
        """3.5 collect(): System Status -> Metrics"""
        result = self._collector.collect(system_status)
        if result.success and system_status is not None and system_status.modules:
            for module_status in system_status.modules:
                self._latest_module_statuses[module_status.module] = module_status
        return result

    def analyze(self, metrics: Metrics) -> Result[HealthStatus]:
        """3.5 analyze(): Metrics -> Health Status(Performance Analysisを含む)"""
        return self._health_checker.analyze(metrics)

    def report(self, health_status: HealthStatus, metrics: Metrics) -> Result[MonitoringReport]:
        """
        3.5 report(): Health Status -> Monitoring Report。
        Monitoring Reportは Metrics も構成要素として含む(3.4)ため、
        直前の collect() で得た Metrics を併せて受け取る。
        """
        return self._reporter.generate(health_status, metrics)
