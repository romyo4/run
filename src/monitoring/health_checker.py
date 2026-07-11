"""M16 Monitoring: health_check()/analyze() の実処理(IS16 4.2)。

- check_module(): 3.3 Health Check(Alive/Ready/Healthy)の1モジュール分の判定。
  ModuleStatusのheartbeat情報(last_heartbeat_at/is_responding)から判定する。
- analyze(): 3.5 analyze()。MetricsとConfigurationClient経由の閾値(4.4)から
  Health Status(Performance Analysisを含む)を導出する。
"""

import logging

from foundation.errors import FoundationError
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result
from foundation.utils import generate_id, utc_now
from monitoring.constants import (
    CONFIG_KEY_EXECUTION_TIME_THRESHOLD_MINUTES,
    CONFIG_KEY_FAILURE_RATE_THRESHOLD_PERCENT,
    CONFIG_KEY_HEARTBEAT_FRESHNESS_SECONDS,
    CONFIG_KEY_RETRY_COUNT_THRESHOLD,
    MonitoredModuleName,
    WorkflowState,
)
from monitoring.errors import UnknownMonitoredModuleError
from monitoring.models import HealthStatus, Metrics, ModuleHealth, ModuleStatus

logger = get_logger("Monitoring")


class HealthChecker:
    """3.3 Health Check(Alive/Ready/Healthy)と 3.5 analyze() の実処理。閾値はConfigurationClient経由(F03/4.4)。"""

    def __init__(self, configuration_client: ConfigurationClient) -> None:
        self._configuration_client = configuration_client

    def check_module(self, module: MonitoredModuleName, module_status: ModuleStatus) -> Result[ModuleHealth]:
        """1モジュール分の Alive/Ready/Healthy を判定する。"""
        try:
            if not isinstance(module, MonitoredModuleName):
                raise UnknownMonitoredModuleError(f"Unknown monitored module: {module!r}")
            if module_status is None:
                raise UnknownMonitoredModuleError("module_status must not be None")

            alive = module_status.last_heartbeat_at is not None
            ready = module_status.is_responding
            healthy = False
            if alive and ready:
                freshness_threshold = self._get_threshold_result(CONFIG_KEY_HEARTBEAT_FRESHNESS_SECONDS)
                if not freshness_threshold.success:
                    return Result(success=False, error=freshness_threshold.error)
                staleness_seconds = (utc_now() - module_status.last_heartbeat_at).total_seconds()  # type: ignore[operator]
                healthy = staleness_seconds <= float(freshness_threshold.value)

            module_health = ModuleHealth(module=module, alive=alive, ready=ready, healthy=healthy)
        except FoundationError as exc:
            logger.error("check_module failed | module=%s | error=%s", module, exc.message)
            return Result(success=False, error=exc)

        level = logging.INFO if module_health.is_healthy else logging.ERROR
        logger.log(
            level,
            "check_module completed | module=%s | health_status=%s",
            module.value,
            "Healthy" if module_health.is_healthy else "Unhealthy",
        )
        return Result(success=True, value=module_health)

    def analyze(self, metrics: Metrics) -> Result[HealthStatus]:
        """Metricsと閾値(Execution Time/Failure Rate/Retry Count)からHealth Statusを導出する。"""
        try:
            if metrics is None:
                raise UnknownMonitoredModuleError("metrics must not be None")

            execution_time_threshold_seconds = self._get_threshold_result(CONFIG_KEY_EXECUTION_TIME_THRESHOLD_MINUTES)
            if not execution_time_threshold_seconds.success:
                return Result(success=False, error=execution_time_threshold_seconds.error)

            failure_rate_threshold = self._get_threshold_result(CONFIG_KEY_FAILURE_RATE_THRESHOLD_PERCENT)
            if not failure_rate_threshold.success:
                return Result(success=False, error=failure_rate_threshold.error)

            retry_count_threshold = self._get_threshold_result(CONFIG_KEY_RETRY_COUNT_THRESHOLD)
            if not retry_count_threshold.success:
                return Result(success=False, error=retry_count_threshold.error)

            execution_time_threshold_secs = float(execution_time_threshold_seconds.value) * 60
            failure_rate_threshold_pct = float(failure_rate_threshold.value)
            retry_threshold = float(retry_count_threshold.value)

            warnings: list[str] = []
            module_health_list: list[ModuleHealth] = []

            for module_metrics in metrics.module_metrics:
                exceeded = False
                if module_metrics.execution_time_seconds > execution_time_threshold_secs:
                    warnings.append(
                        f"{module_metrics.module.value}: execution time "
                        f"{module_metrics.execution_time_seconds}s exceeds threshold "
                        f"{execution_time_threshold_secs}s"
                    )
                    exceeded = True
                if module_metrics.failure_rate > failure_rate_threshold_pct:
                    warnings.append(
                        f"{module_metrics.module.value}: failure rate "
                        f"{module_metrics.failure_rate}% exceeds threshold "
                        f"{failure_rate_threshold_pct}%"
                    )
                    exceeded = True
                if module_metrics.retry_count > retry_threshold:
                    warnings.append(
                        f"{module_metrics.module.value}: retry count "
                        f"{module_metrics.retry_count} exceeds threshold {retry_threshold}"
                    )
                    exceeded = True

                module_health_list.append(
                    ModuleHealth(
                        module=module_metrics.module,
                        alive=True,
                        ready=True,
                        healthy=not exceeded,
                    )
                )

            failures = [
                f"workflow {workflow_metrics.workflow_id} failed"
                for workflow_metrics in metrics.workflow_metrics
                if workflow_metrics.state == WorkflowState.FAILED
            ]

            overall_healthy = all(module_health.is_healthy for module_health in module_health_list)

            health_status = HealthStatus(
                id=generate_id(),
                created_at=utc_now(),
                updated_at=utc_now(),
                metadata={},
                evaluated_at=utc_now(),
                overall_healthy=overall_healthy,
                module_health=module_health_list,
                warnings=warnings,
                failures=failures,
            )
        except FoundationError as exc:
            logger.error("analyze failed | error=%s", exc.message)
            return Result(success=False, error=exc)

        level = logging.INFO if overall_healthy else logging.WARNING
        logger.log(
            level,
            "analyze completed | health_status=%s | warning_count=%d",
            "Healthy" if overall_healthy else "Unhealthy",
            len(warnings),
        )
        return Result(success=True, value=health_status)

    def _get_threshold_result(self, key: str) -> Result:
        return self._configuration_client.get("Monitoring", key)
