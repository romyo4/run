"""M16 Monitoring 定数/Enum定義(IS16 2. ファイル構成 / 3章)。

監視対象モジュール名・Workflow状態・Health Check項目・Configurationキー名を定義する。
"""

from enum import Enum


class MonitoredModuleName(str, Enum):
    """3.2 監視対象 Module 一覧。"""

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
    """3.2 監視対象 Workflow 状態。"""

    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    WAITING = "Waiting"


class HealthCheckItem(str, Enum):
    """3.3 Health Check 確認項目。"""

    ALIVE = "Alive"
    READY = "Ready"
    HEALTHY = "Healthy"


# Configuration Manager(M17)から取得する閾値キー(F03 ConfigurationClient経由、4.4)
CONFIG_KEY_EXECUTION_TIME_THRESHOLD_MINUTES = "execution_time_threshold_minutes"
CONFIG_KEY_FAILURE_RATE_THRESHOLD_PERCENT = "failure_rate_threshold_percent"
CONFIG_KEY_RETRY_COUNT_THRESHOLD = "retry_count_threshold"
CONFIG_KEY_HEARTBEAT_FRESHNESS_SECONDS = "heartbeat_freshness_seconds"
