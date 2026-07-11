"""M16 Monitoring: collect() の実処理(IS16 4.2)。

System Status(workflow_status/module_status/system_metrics/execution_log)から
Metrics(Execution Time/Success Rate/Failure Rate/Retry Count/Queue Length)を集計する。
Read Onlyのため、入力SystemStatusを変更しない。
"""

from foundation.errors import FoundationError
from foundation.logger import get_logger
from foundation.result import Result
from foundation.utils import generate_id, utc_now
from monitoring.constants import WorkflowState
from monitoring.errors import InvalidSystemStatusError
from monitoring.models import (
    ExecutionLogEntry,
    Metrics,
    ModuleMetrics,
    ModuleStatus,
    SystemStatus,
    WorkflowMetrics,
    WorkflowStatus,
)

logger = get_logger("Monitoring")


class MetricsCollector:
    """3.5 collect() の実処理。System Status から Metrics を集計する。"""

    def collect(self, system_status: SystemStatus) -> Result[Metrics]:
        try:
            self._validate(system_status)
            assert system_status is not None  # for type-checkers; validated above

            workflow_metrics = self._build_workflow_metrics(system_status)
            module_metrics = self._build_module_metrics(system_status)

            metrics = Metrics(
                id=generate_id(),
                created_at=utc_now(),
                updated_at=utc_now(),
                metadata={},
                collected_at=utc_now(),
                system_resources=system_status.system_resources,
                workflow_metrics=workflow_metrics,
                module_metrics=module_metrics,
            )
        except FoundationError as exc:
            logger.error(
                "collect failed | error=%s",
                exc.message,
            )
            return Result(success=False, error=exc)

        logger.info(
            "collect completed | workflow_count=%d | module_count=%d",
            len(workflow_metrics),
            len(module_metrics),
        )
        return Result(success=True, value=metrics)

    @staticmethod
    def _validate(system_status: SystemStatus | None) -> None:
        if system_status is None:
            raise InvalidSystemStatusError("system_status must not be None")
        if system_status.workflows is None:
            raise InvalidSystemStatusError("system_status.workflows must not be None")
        if system_status.modules is None:
            raise InvalidSystemStatusError("system_status.modules must not be None")
        if system_status.system_resources is None:
            raise InvalidSystemStatusError("system_status.system_resources must not be None")
        if system_status.execution_log is None:
            raise InvalidSystemStatusError("system_status.execution_log must not be None")

    @staticmethod
    def _build_workflow_metrics(system_status: SystemStatus) -> list[WorkflowMetrics]:
        result: list[WorkflowMetrics] = []
        for workflow in system_status.workflows:
            execution_time = MetricsCollector._sum_execution_time_for_workflow(system_status.execution_log, workflow)
            result.append(
                WorkflowMetrics(
                    workflow_id=workflow.workflow_id,
                    state=workflow.state,
                    execution_time_seconds=execution_time,
                )
            )
        return result

    @staticmethod
    def _sum_execution_time_for_workflow(execution_log: list[ExecutionLogEntry], workflow: WorkflowStatus) -> float:
        return sum(entry.execution_time_seconds for entry in execution_log if entry.workflow_id == workflow.workflow_id)

    @staticmethod
    def _build_module_metrics(system_status: SystemStatus) -> list[ModuleMetrics]:
        # Queue Length: 現時点でシステム全体としてWaiting状態にあるWorkflow数を採用する。
        # (入力モデルにModule別のキュー情報が存在しないため、システム全体の待機件数を
        #  各Moduleの Queue Length として扱う。)
        queue_length = sum(1 for workflow in system_status.workflows if workflow.state == WorkflowState.WAITING)

        result: list[ModuleMetrics] = []
        for module_status in system_status.modules:
            result.append(
                MetricsCollector._build_single_module_metrics(module_status, system_status.execution_log, queue_length)
            )
        return result

    @staticmethod
    def _build_single_module_metrics(
        module_status: ModuleStatus,
        execution_log: list[ExecutionLogEntry],
        queue_length: int,
    ) -> ModuleMetrics:
        entries = [entry for entry in execution_log if entry.module == module_status.module]
        total = len(entries)

        if total == 0:
            execution_time_seconds = 0.0
            success_rate = 0.0
            failure_rate = 0.0
            retry_count = 0
        else:
            execution_time_seconds = sum(entry.execution_time_seconds for entry in entries) / total
            failure_count = sum(1 for entry in entries if entry.is_failure)
            failure_rate = (failure_count / total) * 100
            success_rate = 100.0 - failure_rate
            # Retry Count: 入力モデルに明示的なリトライ件数が存在しないため、
            # 失敗として記録されたexecution_log件数を近似値として採用する。
            retry_count = failure_count

        return ModuleMetrics(
            module=module_status.module,
            execution_time_seconds=execution_time_seconds,
            success_rate=success_rate,
            failure_rate=failure_rate,
            retry_count=retry_count,
            queue_length=queue_length,
        )
