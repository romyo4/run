"""M16 Monitoring: report() の実処理(IS16 4.2)。

Health Status と Metrics から Monitoring Report(Health Status/Metrics/Failures/Warnings/
Performance Summary、3.4)を生成する。Read Onlyのため、入力を変更しない。
"""

from foundation.errors import FoundationError, ValidationError
from foundation.logger import get_logger
from foundation.result import Result
from foundation.utils import generate_id, utc_now
from monitoring.models import HealthStatus, Metrics, MonitoringReport, PerformanceSummary

logger = get_logger("Monitoring")


class ReportGenerator:
    """3.4/3.5 report() の実処理。Health StatusとMetricsからMonitoring Reportを生成する。"""

    def generate(self, health_status: HealthStatus, metrics: Metrics) -> Result[MonitoringReport]:
        try:
            self._validate(health_status, metrics)
            assert health_status is not None and metrics is not None

            performance_summary = self._build_performance_summary(metrics)

            report = MonitoringReport(
                id=generate_id(),
                created_at=utc_now(),
                updated_at=utc_now(),
                metadata={},
                health_status=health_status,
                metrics=metrics,
                failures=list(health_status.failures),
                warnings=list(health_status.warnings),
                performance_summary=performance_summary,
            )
        except FoundationError as exc:
            logger.error("report failed | error=%s", exc.message)
            return Result(success=False, error=exc)

        logger.info(
            "report completed | health_status=%s | warning_count=%d",
            "Healthy" if health_status.overall_healthy else "Unhealthy",
            len(health_status.warnings),
        )
        return Result(success=True, value=report)

    @staticmethod
    def _validate(health_status: HealthStatus | None, metrics: Metrics | None) -> None:
        if health_status is None:
            raise ValidationError("health_status must not be None")
        if metrics is None:
            raise ValidationError("metrics must not be None")

    @staticmethod
    def _build_performance_summary(metrics: Metrics) -> PerformanceSummary:
        total_workflows = len(metrics.workflow_metrics)
        if total_workflows > 0:
            average_execution_time_seconds = (
                sum(w.execution_time_seconds for w in metrics.workflow_metrics) / total_workflows
            )
        else:
            average_execution_time_seconds = 0.0

        module_count = len(metrics.module_metrics)
        if module_count > 0:
            success_rate = sum(m.success_rate for m in metrics.module_metrics) / module_count
            failure_rate = sum(m.failure_rate for m in metrics.module_metrics) / module_count
        else:
            success_rate = 0.0
            failure_rate = 0.0

        return PerformanceSummary(
            average_execution_time_seconds=average_execution_time_seconds,
            success_rate=success_rate,
            failure_rate=failure_rate,
            total_workflows=total_workflows,
        )
