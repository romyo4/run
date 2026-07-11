"""M16 Monitoring 固有のdataclass定義(IS16 3章)。

F01のDomain Model共通属性規約(id/created_at/updated_at/metadata)に従う、
Monitoring自身の監視対象・成果物を表現するモジュール固有dataclass群である。
Foundation `types.py` の共通Domain一覧を再定義するものではない。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from monitoring.constants import MonitoredModuleName, WorkflowState

# --- 3.1 入力側(collect()の入力を構成する要素) ---


@dataclass
class WorkflowStatus:
    """入力: workflow_status の1件分。"""

    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    workflow_id: str
    state: WorkflowState


@dataclass
class ModuleStatus:
    """入力: module_status の1件分。"""

    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    module: MonitoredModuleName
    last_heartbeat_at: datetime | None
    is_responding: bool


@dataclass
class SystemResourceStatus:
    """入力: system_metrics(CPU/Memory/Disk/Network)。"""

    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io_bytes_per_sec: float


@dataclass
class ExecutionLogEntry:
    """入力: execution_log の1件分(4.5 Logging項目に準拠)。"""

    timestamp: datetime
    workflow_id: str
    module: MonitoredModuleName
    execution_time_seconds: float
    is_failure: bool


@dataclass
class SystemStatus:
    """collect() の入力(3.5)。workflow_status/module_status/system_metrics/execution_log の集約。"""

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
    """3.2 Metrics(Execution Time/Success Rate/Failure Rate/Retry Count/Queue Length)。"""

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
    """3.3 Health Check(Alive/Ready/Healthy)の1モジュール分の結果。"""

    module: MonitoredModuleName
    alive: bool
    ready: bool
    healthy: bool

    @property
    def is_healthy(self) -> bool:
        """3.5 health_check() 出力(Healthy/Unhealthy)の判定。"""
        return self.alive and self.ready and self.healthy


# --- 3.5 analyze() の出力 / report() の入力 ---


@dataclass
class HealthStatus:
    """3.4 Monitoring Report の構成要素: Health Status。"""

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
    """3.4 Monitoring Report の構成要素: Performance Summary。"""

    average_execution_time_seconds: float
    success_rate: float
    failure_rate: float
    total_workflows: int


@dataclass
class MonitoringReport:
    """3.4 Monitoring Report(Health Status/Metrics/Failures/Warnings/Performance Summary)。"""

    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    health_status: HealthStatus
    metrics: Metrics
    failures: list[str]
    warnings: list[str]
    performance_summary: PerformanceSummary
