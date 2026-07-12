"""21モジュールを依存順に実インスタンス化する配線層本体。

依存順序: Foundation(暗黙) → Configuration Manager → 他モジュール(全てconfig
経由でConfigurationClientを共有) → Cross-module依存を持つモジュール
(Context Manager, GitHub Manager経由のPR Creator/Connector、Command Router経由の
Scheduler等)。

各コンストラクタ引数は、事前調査(各モジュールの`__init__`実読)に基づき実際の
シグネチャに一致させている。詳細は`.superpowers/sdd/task-4-report.md`を参照。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from architect.module import ArchitectModule
from bootstrap.config import build_configuration_manager
from bootstrap.stub_services import (
    StubCodexAdapter,
    StubCommandExecutor,
    StubFableClient,
    StubHttpClient,
    StubHttpTransport,
)
from command_router.router import CommandRouter
from configuration_manager.manager import ConfigurationManager
from connector.connector import SlackDiscordConnector
from connector.discord_adapter import DiscordAdapter
from connector.slack_adapter import SlackAdapter
from context_manager.manager import ContextManager
from design_auditor.module import DesignAuditor
from executor.executor import Executor
from executor.repository_guard import RepositoryGuard
from foundation.base_module import BaseModule
from foundation.logger import get_logger
from foundation.result import Result
from github_manager.client import GitHubClient
from github_manager.github_manager import GitHubManager
from knowledge_manager.knowledge_manager import KnowledgeManager
from knowledge_manager.store import KnowledgeStore
from monitoring.collector import MetricsCollector
from monitoring.health_checker import HealthChecker
from monitoring.monitoring_module import MonitoringModule
from monitoring.reporter import ReportGenerator
from notification.history import NotificationHistoryStore
from notification.service import NotificationModule
from permission_manager.permission_manager import PermissionManager
from planner.planner import Planner
from pr_creator.pr_creator import PRCreator
from reviewer.reviewer import ReviewerModule
from scheduler.command_router_client import RawCommand
from scheduler.scheduler_module import SchedulerModule
from state_manager.manager import StateManager
from task_queue.queue_manager import TaskQueueManager
from tester.models import TesterConfig
from tester.tester import Tester
from weekly_reviewer.models import WeeklyReviewerConfig
from weekly_reviewer.weekly_reviewer import WeeklyReviewer


class _CommandRouterClientAdapter:
    """SchedulerModule(M14)が要求する`CommandRouterClient` Protocolの実装。

    Scheduler→Command Routerの一方向依存のみを持つ(設計書M05/M14の循環依存解消方針)。
    実体は`CommandRouter.receive()`をそのまま呼び出す薄いアダプタであり、`classify`/
    `route`/`dispatch`等の他インターフェースは呼び出さない。
    """

    def __init__(self, command_router: CommandRouter) -> None:
        self._command_router = command_router

    def receive(self, raw_command: RawCommand) -> Result[Any]:
        return self._command_router.receive(raw_command)


@dataclass
class Application:
    """21モジュール全ての実インスタンスを束ねる。"""

    configuration_manager: ConfigurationManager
    state_manager: StateManager
    task_queue: TaskQueueManager
    knowledge_manager: KnowledgeManager
    permission_manager: PermissionManager
    planner: Planner
    architect: ArchitectModule
    design_auditor: DesignAuditor
    executor: Executor
    tester: Tester
    pr_creator: PRCreator
    reviewer: ReviewerModule
    weekly_reviewer: WeeklyReviewer
    github_manager: GitHubManager
    context_manager: ContextManager
    connector: SlackDiscordConnector
    notification: NotificationModule
    monitoring: MonitoringModule
    scheduler: SchedulerModule
    command_router: CommandRouter

    def all_modules(self) -> list[BaseModule]:
        return [
            self.configuration_manager,
            self.state_manager,
            self.task_queue,
            self.knowledge_manager,
            self.permission_manager,
            self.planner,
            self.architect,
            self.design_auditor,
            self.executor,
            self.tester,
            self.pr_creator,
            self.reviewer,
            self.weekly_reviewer,
            self.github_manager,
            self.context_manager,
            self.connector,
            self.notification,
            self.monitoring,
            self.scheduler,
            self.command_router,
        ]


def build_application() -> Application:
    config = build_configuration_manager()
    load_result = config.load(
        config._source
    )  # noqa: SLF001 - 初回load(build_configuration_manager()はunloaded状態で返す仕様)
    if not load_result.success:
        raise RuntimeError(f"configuration load failed: {load_result.error}")

    state_manager = StateManager(config_client=config)
    task_queue = TaskQueueManager(config_client=config)
    knowledge_manager = KnowledgeManager(store=KnowledgeStore())
    permission_manager = PermissionManager(config_client=config)
    planner = Planner(config_client=config)
    architect = ArchitectModule(config_client=config)
    design_auditor = DesignAuditor(config_client=config)
    executor = Executor(codex_adapter=StubCodexAdapter(), repository_guard=RepositoryGuard())

    # TesterConfig(src/tester/models.py)は全フィールド必須(既定値なし)。config/default.jsonに
    # "tester"セクションは存在しないため、StubCommandExecutorが実行内容を無視することを踏まえた
    # プレースホルダのコマンド列を明示的に埋める(新規configキーは追加しない)。
    tester_config = TesterConfig(
        build_command=["stub-build"],
        lint_command=["stub-lint"],
        unit_test_command=["stub-unit-test"],
        integration_test_command=["stub-integration-test"],
        regression_test_command=["stub-regression-test"],
        static_analysis_command=["stub-static-analysis"],
        command_timeout_seconds=60,
    )
    tester = Tester(config=tester_config, logger=get_logger("tester"), command_executor=StubCommandExecutor())

    github_client = GitHubClient(configuration_client=config, transport=StubHttpTransport())
    github_manager = GitHubManager(client=github_client)

    # PRCreator.github_client=Noneは型ヒント上のOptionalかつ意図された既定分岐(遅延解決)。
    # _resolve_client()はgithub_client未設定時のみconfigからgithub_access_tokenを取得するが、
    # これはcreate_pr()等の呼び出し時にのみ実行され、construction/health_check()では一切
    # 参照されない(health_check()は常にResult(True, True)を返す)。よってNoneのままで
    # 安全に動作する(明示的なGitHubPullRequestClient構築は不要)。
    pr_creator = PRCreator(configuration_client=config, github_client=None)
    reviewer = ReviewerModule(configuration_client=config)

    # WeeklyReviewerConfig(src/weekly_reviewer/models.py)は全フィールドに既定値
    # (review_period_days=7, business_goal=None)を持つため、引数なしで構築できる。
    weekly_reviewer_config = WeeklyReviewerConfig()
    weekly_reviewer = WeeklyReviewer(
        config=weekly_reviewer_config,
        logger=get_logger("weekly_reviewer"),
        fable_client=StubFableClient(),
    )

    context_manager = ContextManager(
        knowledge_manager=knowledge_manager,
        github_manager=github_manager,
        configuration_client=config,
    )

    # SlackDiscordConnector.health_check()は内部でAdapter.check_connection()経由の
    # HTTPリクエストを実行する。Adapterの既定http_client(UrllibHttpClient)のまま構築すると
    # Phase 0環境(実ネットワーク接続・実トークンなし)ではhealth_check()がFalseを返すため、
    # StubHttpClient(Connector(M21)向けスタブ)を明示的に注入したAdapterを使う。
    connector = SlackDiscordConnector(
        config_client=config,
        slack_adapter=SlackAdapter(config_client=config, http_client=StubHttpClient()),
        discord_adapter=DiscordAdapter(config_client=config, http_client=StubHttpClient()),
    )

    notification = NotificationModule(
        config_client=config,
        channel_connectors={},
        history_store=NotificationHistoryStore(),
    )

    monitoring = MonitoringModule(
        collector=MetricsCollector(),
        health_checker=HealthChecker(configuration_client=config),
        reporter=ReportGenerator(),
    )

    # SchedulerModuleはCommand Routerを直接importしない一方向依存(設計書M05/M14)を要求する。
    # command_routerは先に構築し、CommandRouterClient Protocolを満たす薄いアダプタ経由で渡す。
    command_router = CommandRouter(handlers={}, config_client=config)
    scheduler = SchedulerModule(
        command_router_client=_CommandRouterClientAdapter(command_router),
        configuration_client=config,
    )

    return Application(
        configuration_manager=config,
        state_manager=state_manager,
        task_queue=task_queue,
        knowledge_manager=knowledge_manager,
        permission_manager=permission_manager,
        planner=planner,
        architect=architect,
        design_auditor=design_auditor,
        executor=executor,
        tester=tester,
        pr_creator=pr_creator,
        reviewer=reviewer,
        weekly_reviewer=weekly_reviewer,
        github_manager=github_manager,
        context_manager=context_manager,
        connector=connector,
        notification=notification,
        monitoring=monitoring,
        scheduler=scheduler,
        command_router=command_router,
    )
