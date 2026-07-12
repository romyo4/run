# Phase 0: 配線層(Bootstrap Wiring)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 外部サービス(GitHub/Slack/Discord/Codex/Fable)に一切接続せずとも、21モジュールの実装コード同士を実際に接続し、1つの合成Workflow(Planner→Architect→Design Auditor→Executor→Tester→PR Creator→Reviewer)がResult成功で最後まで流れることを実証する。

**Architecture:** `src/bootstrap/`パッケージを新設し、(1) 外部サービスの末端アダプタ(CodexAdapter/HttpTransport/HttpClient/CommandExecutor/FableClient)を「常に成功するスタブ」として実装、(2) `ConfigurationManager`を`config/default.json`から構築、(3) 21モジュールを依存順に実インスタンス化する`build_application()`、(4) モジュール間の型不整合を吸収する`adapters.py`、(5) Planner→...→Reviewerを直列に呼び出す`run_workflow()`、の5層で構成する。Command Router/Scheduler経由の非同期起動は本Phaseでは扱わず、直接メソッド呼び出しによる直列実行のみを対象とする(Command Router自体の疎通確認は含むが、Workflow起動の入口としては使わない)。

**Tech Stack:** Python 3.13, 標準`unittest`, 既存の`src/*`実装一式(変更しない。導入済みの`ConfigurationManager`/`Result[T]`/`BaseModule`パターンをそのまま利用)。

**既知の型不整合(統合レビューで判明済み、本Planで解消する)**:
1. Architect `analyzer.py` が `execution_plan.plan_id` を参照するが、Planner `ExecutionPlan` の実フィールド名は `id`。
2. Design Auditor `ApprovedDesign` は `metadata` を持たないが、Executor `_validate_approval()` は `approved_design.metadata["approval_status"]`/`["design_id"]` を要求する。
3. PR Creator `CreatePullRequestInput.repository_information`/`branch_information`/`project_context`(design_document/execution_plan/audit_report/business_goal)は、Planner〜Tester間のどのモジュールも生成しない。配線層(Workflow起点)で新規に組み立てる。

---

### Task 1: 外部サービス末端アダプタのスタブ実装

**Files:**
- Create: `src/bootstrap/__init__.py`
- Create: `src/bootstrap/stub_services.py`
- Test: `tests/bootstrap/__init__.py`
- Test: `tests/bootstrap/test_stub_services.py`

- [ ] **Step 1: ディレクトリと空の`__init__.py`を作成**

```python
# src/bootstrap/__init__.py
"""AI Development Pipeline 配線層(Phase 0)。

外部サービス(GitHub/Slack/Discord/Codex/Fable)に接続せずとも、21モジュールの
実装コード同士を接続し、1つのWorkflowが最後まで流れることを実証する。
"""
```

```python
# tests/bootstrap/__init__.py
```

- [ ] **Step 2: 失敗するテストを書く(スタブが「常に成功」を返すことを検証)**

```python
# tests/bootstrap/test_stub_services.py
import unittest

from bootstrap.stub_services import (
    StubCodexAdapter,
    StubCommandExecutor,
    StubFableClient,
    StubHttpClient,
    StubHttpTransport,
)
from foundation.result import Result


class StubCodexAdapterTest(unittest.TestCase):
    def test_generate_returns_success_result(self) -> None:
        adapter = StubCodexAdapter()
        result = adapter.generate(instructions="add a function", context={})
        self.assertTrue(result.success)


class StubCommandExecutorTest(unittest.TestCase):
    def test_run_build_returns_success(self) -> None:
        executor = StubCommandExecutor()
        result = executor.run_build()
        self.assertTrue(result.success)

    def test_run_lint_returns_success(self) -> None:
        executor = StubCommandExecutor()
        result = executor.run_lint()
        self.assertTrue(result.success)

    def test_run_unit_tests_returns_success(self) -> None:
        executor = StubCommandExecutor()
        result = executor.run_unit_tests()
        self.assertTrue(result.success)


class StubHttpTransportTest(unittest.TestCase):
    def test_request_returns_success_result(self) -> None:
        transport = StubHttpTransport()
        result = transport.request("GET", "https://api.github.com/repos/example/example")
        self.assertTrue(result.success)


class StubHttpClientTest(unittest.TestCase):
    def test_post_returns_success_result(self) -> None:
        client = StubHttpClient()
        result = client.post("https://slack.com/api/chat.postMessage", json={})
        self.assertTrue(result.success)


class StubFableClientTest(unittest.TestCase):
    def test_evaluate_returns_success_result(self) -> None:
        client = StubFableClient()
        result = client.evaluate(prompt="weekly review", context={})
        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: テストを実行して失敗を確認する**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest tests.bootstrap.test_stub_services -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'bootstrap.stub_services'`)

- [ ] **Step 4: 各Protocolの実際のメソッドシグネチャに合わせてスタブを実装する**

各Protocolの正確なメソッド名は以下(いずれも既存実装から確認済み):
- `executor.codex_adapter.CodexAdapter`: `generate(self, instructions: str, context: dict) -> Result[str]` 相当(実際のProtocol定義を`src/executor/codex_adapter.py`で必ず確認し、シグネチャが異なれば本ステップでこのdocstringではなく実物に合わせること)
- `tester.models.CommandExecutor`: `run_build()`/`run_lint()`/`run_unit_tests()`/`run_integration_tests()`/`run_regression_tests()`/`run_static_analysis()` の6メソッド(`src/tester/models.py`のProtocol定義を確認)
- `github_manager.client.HttpTransport`: `request(method: str, url: str, ...) -> Result[dict]`(`src/github_manager/client.py`のProtocol定義を確認)
- `connector.http_client.HttpClient`: `post(url: str, json: dict) -> Result[dict]` 等(`src/connector/http_client.py`のProtocol定義を確認)
- `weekly_reviewer.fable_client.FableClient`: 抽象クラスの抽象メソッド一式(`src/weekly_reviewer/fable_client.py`を確認)

```python
# src/bootstrap/stub_services.py
"""外部サービス(GitHub/Slack/Discord/Codex/Fable)への実接続を伴わない、
Phase 0(配線層検証)専用のスタブ実装。

すべて「常に成功するResultを返す」ことのみを保証する。Phase 1で各スタブは
実サービス接続クラス(例: RealGitHubHttpTransport)へ個別に置き換える。
本番のShadow Mode/デモ用途にも流用できるが、実際の外部呼び出しは一切行わない。
"""

from typing import Any

from foundation.logger import get_logger
from foundation.result import Result

_logger = get_logger("bootstrap.stub_services")


class StubCodexAdapter:
    """Executor(M09)のCodexAdapter Protocolに準拠するスタブ。"""

    def generate(self, instructions: str, context: dict[str, Any]) -> Result[str]:
        _logger.info("stub_codex_generate instructions_length=%d", len(instructions))
        return Result(success=True, value="# stub generated code\n")


class StubCommandExecutor:
    """Tester(M10)のCommandExecutor Protocolに準拠するスタブ。"""

    def run_build(self) -> Result[dict[str, Any]]:
        return Result(success=True, value={"status": "success"})

    def run_lint(self) -> Result[dict[str, Any]]:
        return Result(success=True, value={"status": "no_error"})

    def run_unit_tests(self) -> Result[dict[str, Any]]:
        return Result(success=True, value={"status": "pass", "passed": 1, "failed": 0})

    def run_integration_tests(self) -> Result[dict[str, Any]]:
        return Result(success=True, value={"status": "pass", "passed": 1, "failed": 0})

    def run_regression_tests(self) -> Result[dict[str, Any]]:
        return Result(success=True, value={"status": "pass", "passed": 1, "failed": 0})

    def run_static_analysis(self) -> Result[dict[str, Any]]:
        return Result(success=True, value={"status": "no_critical_error"})


class StubHttpTransport:
    """GitHub Manager(M20)のHttpTransport Protocolに準拠するスタブ。"""

    def request(self, method: str, url: str, **kwargs: Any) -> Result[dict[str, Any]]:
        _logger.info("stub_github_request method=%s", method)
        return Result(success=True, value={"full_name": "stub/repo", "default_branch": "main"})


class StubHttpClient:
    """Connector(M21)のHttpClient Protocolに準拠するスタブ。"""

    def post(self, url: str, json: dict[str, Any]) -> Result[dict[str, Any]]:
        _logger.info("stub_http_post url=%s", url)
        return Result(success=True, value={"ok": True})


class StubFableClient:
    """Weekly Reviewer(M13)のFableClient抽象クラスに準拠するスタブ。"""

    def evaluate(self, prompt: str, context: dict[str, Any]) -> Result[dict[str, Any]]:
        _logger.info("stub_fable_evaluate prompt_length=%d", len(prompt))
        return Result(success=True, value={"business_alignment": "aligned"})
```

- [ ] **Step 5: テストを実行して通過を確認する**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest tests.bootstrap.test_stub_services -v`
Expected: PASS(全件)。もしProtocol定義と一致せず`TypeError`/`AttributeError`が出た場合、Step 4の対象Protocolファイルを再確認し、メソッド名・引数名をスタブ側に正確に合わせて修正すること(推測で新しいメソッドを増やさない)。

- [ ] **Step 6: Ruff/Blackを実行**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && python -m ruff check --fix src/bootstrap tests/bootstrap && python -m black src/bootstrap tests/bootstrap`

- [ ] **Step 7: コミット**

```bash
cd "C:\Users\user1\Downloads\AI Autonomous Development Platform"
git add src/bootstrap tests/bootstrap
git commit -m "feat(bootstrap): add stub adapters for external service Protocols"
```

---

### Task 2: Configuration Manager のブートストラップと設定ファイルの拡充

**Files:**
- Create: `src/bootstrap/config.py`
- Modify: `config/default.json`
- Test: `tests/bootstrap/test_config.py`

- [ ] **Step 1: 失敗するテストを書く(全21モジュールの必須設定キーが解決できることを検証)**

```python
# tests/bootstrap/test_config.py
import unittest

from bootstrap.config import build_configuration_manager


class BuildConfigurationManagerTest(unittest.TestCase):
    def test_load_succeeds_with_default_config_file(self) -> None:
        manager = build_configuration_manager()
        result = manager.load(manager_source := manager._source)  # noqa: SLF001 - 初回loadの動作確認のみ
        self.assertTrue(result.success, msg=result.error)

    def test_state_manager_lock_timeout_seconds_resolves(self) -> None:
        manager = build_configuration_manager()
        manager.load(manager._source)  # noqa: SLF001
        result = manager.get("state_manager", "lock_timeout_seconds")
        self.assertTrue(result.success, msg=result.error)

    def test_permission_manager_permissions_key_resolves(self) -> None:
        manager = build_configuration_manager()
        manager.load(manager._source)  # noqa: SLF001
        result = manager.get("permission_manager", "permissions")
        self.assertTrue(result.success, msg=result.error)

    def test_pr_creator_github_access_token_resolves(self) -> None:
        manager = build_configuration_manager()
        manager.load(manager._source)  # noqa: SLF001
        result = manager.get("pr_creator", "github_access_token")
        self.assertTrue(result.success, msg=result.error)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest tests.bootstrap.test_config -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: `build_configuration_manager()`を実装する**

```python
# src/bootstrap/config.py
"""Configuration Manager(M17)を`config/default.json`から構築するヘルパー。"""

from pathlib import Path

from configuration_manager.domain import ConfigurationSource
from configuration_manager.manager import ConfigurationManager

_CONFIG_FILE = Path(__file__).resolve().parents[2] / "config" / "default.json"


def build_configuration_manager() -> ConfigurationManager:
    """`config/default.json`を読み込んだ`ConfigurationManager`を返す(未load状態)。

    呼び出し側が`manager.load(source)`を実行して初めて設定値を参照できる。
    """
    source = ConfigurationSource(config_file_paths=(_CONFIG_FILE,))
    return ConfigurationManager(source)
```

- [ ] **Step 4: テストを実行し、どのキーが不足しているか確認する**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest tests.bootstrap.test_config -v`
Expected: `test_load_succeeds_with_default_config_file`はPASS(既存の7カテゴリは揃っている)。`test_state_manager_lock_timeout_seconds_resolves`等はFAIL(`extra`に該当モジュールの設定が無いため)。

- [ ] **Step 5: `config/default.json`に不足モジュールの設定を追加する**

`src/state_manager/manager.py`・`src/permission_manager/permission_manager.py`・`src/pr_creator/pr_creator.py`が実際に呼び出している`config_client.get(module_name, key)`のキー名を各ファイルで確認し(推測しない)、`config/default.json`の該当箇所に追加する。例(実際のキー名はソースコードを見て確定させること):

```json
{
  "system": { "system_name": "ai-development-pipeline", "environment": "development", "log_level": "INFO", "timezone": "UTC" },
  "github": { "repository": "", "default_branch": "main" },
  "slack": { "channel": "" },
  "discord": {},
  "codex": { "model": "" },
  "fable": {},
  "monitoring": {},
  "state_manager": { "lock_timeout_seconds": 30 },
  "permission_manager": { "permissions": [] },
  "pr_creator": { "github_access_token": "" },
  "github_manager": { "github_access_token": "" },
  "connector": { "slack_bot_token": "", "discord_bot_token": "", "discord_bot_user_id": "" },
  "reviewer": { "min_business_score": 0, "blocker_severity_blocks_approval": true }
}
```

- [ ] **Step 6: テストを再実行し、全てPASSするまでStep 5を繰り返す**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest tests.bootstrap.test_config -v`
Expected: PASS(全件)

- [ ] **Step 7: Ruff/Black + コミット**

```bash
cd "C:\Users\user1\Downloads\AI Autonomous Development Platform"
python -m ruff check --fix src/bootstrap tests/bootstrap && python -m black src/bootstrap tests/bootstrap
git add src/bootstrap/config.py config/default.json tests/bootstrap/test_config.py
git commit -m "feat(bootstrap): build ConfigurationManager from config/default.json"
```

---

### Task 3: パイプライン間の型不整合を吸収する `adapters.py`

**Files:**
- Create: `src/bootstrap/adapters.py`
- Test: `tests/bootstrap/test_adapters.py`

- [ ] **Step 1: 失敗するテストを書く(3つの既知不整合それぞれに対応するアダプタ関数を検証)**

```python
# tests/bootstrap/test_adapters.py
import unittest

from bootstrap.adapters import (
    to_architect_execution_plan,
    to_executor_approved_design,
)
from design_auditor.types import ApprovedDesign
from foundation.utils import utc_now
from planner.types import ExecutionPlan


class ToArchitectExecutionPlanTest(unittest.TestCase):
    def test_wrapped_plan_exposes_plan_id_matching_source_id(self) -> None:
        plan = ExecutionPlan(
            objective="LP改善",
            task_list=[],
            dependencies={},
            expected_output="",
        )

        wrapped = to_architect_execution_plan(plan)

        self.assertEqual(wrapped.plan_id, plan.id)
        self.assertEqual(wrapped.objective, plan.objective)
        self.assertEqual(wrapped.task_list, plan.task_list)
        self.assertEqual(wrapped.dependencies, plan.dependencies)
        self.assertEqual(wrapped.expected_output, plan.expected_output)


class ToExecutorApprovedDesignTest(unittest.TestCase):
    def test_wrapped_approved_design_exposes_approval_metadata(self) -> None:
        approved = ApprovedDesign(
            design_id="design-1",
            audit_id="audit-1",
            approved_at=utc_now(),
            comments=[],
        )

        wrapped = to_executor_approved_design(approved)

        self.assertEqual(wrapped.metadata["approval_status"], "approved")
        self.assertEqual(wrapped.metadata["design_id"], "design-1")
        self.assertIs(wrapped.source, approved)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest tests.bootstrap.test_adapters -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: `adapters.py`を実装する**

`src/architect/analyzer.py`の`execution_plan.plan_id`アクセス箇所、および`src/executor/executor.py`の`_validate_approval()`(`getattr(approved_design, "metadata", None)`)を実装前に必ず再確認し、要求される属性名と完全に一致させること。

```python
# src/bootstrap/adapters.py
"""パイプライン各モジュール間のデータ受け渡しにおける型不整合を吸収するアダプタ。

いずれも既存モジュールのソースコード(design/実装仕様書ではなく実際のsrc/実装)を
唯一の正として、実際に要求されている属性名に合わせて変換する。
2026-07 統合レビューで判明した不整合の是正(docs/CHANGELOG.md参照)。
"""

from dataclasses import dataclass, field
from typing import Any

from planner.types import ExecutionPlan


@dataclass
class ArchitectExecutionPlanView:
    """Architect `analyzer.py` が要求する`plan_id`属性を、Planner `ExecutionPlan.id`
    から補って公開するビュー。Architect側のProtocol定義(architect/models.py)に
    合わせ、`priority`は空dictを既定値として保持する。"""

    plan_id: str
    objective: str
    task_list: list[Any]
    dependencies: dict[str, Any]
    expected_output: str
    priority: dict[str, str] = field(default_factory=dict)


def to_architect_execution_plan(execution_plan: ExecutionPlan) -> ArchitectExecutionPlanView:
    """PlannerのExecutionPlanを、ArchitectがそのままAnalyzer入力として使える形へ変換する。"""
    return ArchitectExecutionPlanView(
        plan_id=execution_plan.id,
        objective=execution_plan.objective,
        task_list=execution_plan.task_list,
        dependencies=execution_plan.dependencies,
        expected_output=execution_plan.expected_output,
    )


@dataclass
class ExecutorApprovedDesignView:
    """Executor `_validate_approval()` が要求する`metadata["approval_status"]`/
    `metadata["design_id"]`を、Design Auditorの`ApprovedDesign`(metadata非保持)
    から補って公開するビュー。"""

    source: Any
    metadata: dict[str, Any]

    @property
    def design_id(self) -> str:
        return self.source.design_id


def to_executor_approved_design(approved_design: Any) -> ExecutorApprovedDesignView:
    """Design AuditorのApprovedDesignを、ExecutorがそのままLoad Design入力として
    使える形へ変換する。"""
    return ExecutorApprovedDesignView(
        source=approved_design,
        metadata={"approval_status": "approved", "design_id": approved_design.design_id},
    )
```

- [ ] **Step 4: テストを実行して通過を確認する**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest tests.bootstrap.test_adapters -v`
Expected: PASS(全件)。`ExecutionPlan`のフィールド名・必須引数がテストと異なる場合は`src/planner/types.py`を確認し、テスト側を実際の定義に合わせて修正すること。

- [ ] **Step 5: Ruff/Black + コミット**

```bash
cd "C:\Users\user1\Downloads\AI Autonomous Development Platform"
python -m ruff check --fix src/bootstrap tests/bootstrap && python -m black src/bootstrap tests/bootstrap
git add src/bootstrap/adapters.py tests/bootstrap/test_adapters.py
git commit -m "feat(bootstrap): add adapters bridging Planner/Architect/Executor type mismatches"
```

---

### Task 4: 21モジュールの実インスタンス化(`wiring.py`)

**Files:**
- Create: `src/bootstrap/wiring.py`
- Test: `tests/bootstrap/test_wiring.py`

- [ ] **Step 1: 失敗するテストを書く(Applicationが構築でき、全モジュールのhealth_check()が成功すること)**

```python
# tests/bootstrap/test_wiring.py
import unittest

from bootstrap.wiring import build_application


class BuildApplicationTest(unittest.TestCase):
    def test_build_application_succeeds(self) -> None:
        app = build_application()
        self.assertIsNotNone(app)

    def test_all_modules_report_healthy(self) -> None:
        app = build_application()
        for module in app.all_modules():
            result = module.health_check()
            self.assertTrue(result.success, msg=f"{module.name()}: {result.error}")
            self.assertTrue(result.value, msg=f"{module.name()} reported unhealthy")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest tests.bootstrap.test_wiring -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: `Application`データクラスと`build_application()`を実装する**

各モジュールのコンストラクタ引数は、事前調査で確認済みの実際のシグネチャに正確に一致させること(推測禁止)。`config`は`Task 2`で読み込み済みの`ConfigurationManager`インスタンスを共有DIとして全モジュールへ渡す。

```python
# src/bootstrap/wiring.py
"""21モジュールを依存順に実インスタンス化する配線層本体。

依存順序: Foundation(暗黙) → Configuration Manager → 他モジュール(全てconfig
経由でConfigurationClientを共有) → Cross-module依存を持つモジュール
(Context Manager, GitHub Manager経由のPR Creator/Connector等)。
"""

from dataclasses import dataclass, field

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
from context_manager.manager import ContextManager
from design_auditor.module import DesignAuditor
from executor.executor import Executor
from executor.repository_guard import RepositoryGuard
from foundation.base_module import BaseModule
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
from scheduler.scheduler_module import SchedulerModule
from state_manager.manager import StateManager
from task_queue.queue_manager import TaskQueueManager
from tester.models import TesterConfig
from tester.tester import Tester
from weekly_reviewer.weekly_reviewer import WeeklyReviewer


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
    load_result = config.load(config._source)  # noqa: SLF001 - 初回load
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

    tester_config = TesterConfig()
    tester = Tester(config=tester_config, logger=None, command_executor=StubCommandExecutor())

    github_client = GitHubClient(configuration_client=config, transport=StubHttpTransport())
    github_manager = GitHubManager(client=github_client)

    pr_creator = PRCreator(configuration_client=config, github_client=None)
    reviewer = ReviewerModule(configuration_client=config)

    weekly_reviewer_config = None  # noqa: F841 - Step 4で実際のWeeklyReviewerConfig構築方法を確認して置き換える
    weekly_reviewer = WeeklyReviewer(
        config=weekly_reviewer_config,
        logger=None,
        fable_client=StubFableClient(),
    )

    context_manager = ContextManager(
        knowledge_manager=knowledge_manager,
        github_manager=github_manager,
        configuration_client=config,
    )

    connector = SlackDiscordConnector(config_client=config)
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

    scheduler = SchedulerModule(command_router_client=None, configuration_client=config)  # noqa: E501 - Step 4でCommandRouterClient実装を確認して置き換える
    command_router = CommandRouter(handlers={}, config_client=config)

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
```

- [ ] **Step 4: テストを実行し、実際のコンストラクタ要求と食い違う箇所を1つずつ解消する**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest tests.bootstrap.test_wiring -v`

このステップで高い確率で以下の追加調査・修正が必要になる(いずれも該当ソースファイルを開いて実際の定義を確認してから直すこと。当てずっぽうで直さない):
- `logger=None`を渡している箇所(Tester, WeeklyReviewer)は、`foundation.logger.get_logger`で実Loggerを生成して渡すこと(`None`はコンストラクタの型ヒントと矛盾する可能性が高い)。
- `TesterConfig()`の必須引数を`src/tester/models.py`で確認し、`config.get("tester", ...)`で解決するか適切な既定値を埋めること。
- `WeeklyReviewerConfig`の構築方法を`src/weekly_reviewer/models.py`で確認し、必須フィールドを埋めること。
- `PRCreator(github_client=None)`は`src/pr_creator/pr_creator.py`のデフォルト分岐(Noneなら内部生成)を確認し、Noneのままで動くか、`GitHubPullRequestClient(access_token=..., transport=StubHttpTransport())`相当を明示的に渡す必要があるか確認すること。
- `SchedulerModule(command_router_client=None)`は`src/scheduler/command_router_client.py`の`CommandRouterClient` Protocolを確認し、`CommandRouter.receive()`を呼び出すアダプタ(`command_router`変数を捕捉するラムダまたは小さなクラス)を実装して渡すこと(Noneのままでは動かない可能性が高い)。

Expected(最終): PASS(全件)。全モジュールの`health_check()`が`Result(success=True, value=True)`相当を返す。

- [ ] **Step 5: Ruff/Black + コミット**

```bash
cd "C:\Users\user1\Downloads\AI Autonomous Development Platform"
python -m ruff check --fix src/bootstrap tests/bootstrap && python -m black src/bootstrap tests/bootstrap
git add src/bootstrap/wiring.py tests/bootstrap/test_wiring.py
git commit -m "feat(bootstrap): wire all 21 modules into a single Application"
```

---

### Task 5: 合成Workflowのオーケストレーション(`workflow.py`)

**Files:**
- Create: `src/bootstrap/workflow.py`
- Test: `tests/bootstrap/test_workflow.py`

- [ ] **Step 1: 失敗するテストを書く(Planner→...→Reviewerが最後まで成功で流れること)**

```python
# tests/bootstrap/test_workflow.py
import unittest

from bootstrap.wiring import build_application
from bootstrap.workflow import run_workflow
from planner.types import NormalizedRequest


class RunWorkflowTest(unittest.TestCase):
    def test_synthetic_workflow_completes_through_reviewer(self) -> None:
        app = build_application()
        request = NormalizedRequest(
            workflow_id="wf-bootstrap-1",
            instruction="LP改善",
            business_goal="LINE登録数最大化",
        )

        result = run_workflow(app, request)

        self.assertTrue(result.success, msg=result.error)
        self.assertIsNotNone(result.value)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest tests.bootstrap.test_workflow -v`
Expected: FAIL(`ModuleNotFoundError`)。`NormalizedRequest`の実際のフィールド名が異なる場合は`src/planner/types.py`を確認しテストを修正すること。

- [ ] **Step 3: `run_workflow()`を実装する**

Task 3で確認した3つの型不整合を`adapters.py`経由で解消しながら、7モジュールを直列に呼び出す。`repository_information`/`branch_information`/`project_context`はいずれの前段モジュールも生成しないため、この関数内で明示的に構築する。

```python
# src/bootstrap/workflow.py
"""Planner→Architect→Design Auditor→Executor→Tester→PR Creator→Reviewerを
直列に呼び出す合成Workflow。Phase 0では外部サービスに一切接続しない
(Executor/Tester/PR CreatorはStub実装経由)。
"""

from bootstrap.adapters import to_architect_execution_plan, to_executor_approved_design
from bootstrap.wiring import Application
from executor.models import RepositoryInfo
from foundation.result import Result
from planner.types import NormalizedRequest
from pr_creator.models import BranchInformation, CreatePullRequestInput, RepositoryInformation
from reviewer.domain import ReviewOutcome


def run_workflow(app: Application, request: NormalizedRequest) -> Result[ReviewOutcome]:
    requirement_result = app.planner.analyze(request)
    if not requirement_result.success:
        return Result(success=False, error=requirement_result.error)

    tasks_result = app.planner.create_tasks(requirement_result.value)
    if not tasks_result.success:
        return Result(success=False, error=tasks_result.error)

    prioritized_result = app.planner.prioritize(tasks_result.value)
    if not prioritized_result.success:
        return Result(success=False, error=prioritized_result.error)

    plan_result = app.planner.create_execution_plan(prioritized_result.value)
    if not plan_result.success:
        return Result(success=False, error=plan_result.error)
    execution_plan = plan_result.value

    design_requirement_result = app.architect.analyze_plan(
        workflow_id=request.workflow_id,
        execution_plan=to_architect_execution_plan(execution_plan),
    )
    if not design_requirement_result.success:
        return Result(success=False, error=design_requirement_result.error)

    design_result = app.architect.create_design(design_requirement_result.value)
    if not design_result.success:
        return Result(success=False, error=design_result.error)
    design_document = design_result.value

    validation_result = app.architect.validate_design(design_document)
    if not validation_result.success:
        return Result(success=False, error=validation_result.error)

    published_design_result = app.architect.publish_design(
        design_document=design_document,
        validation_result=validation_result.value,
    )
    if not published_design_result.success:
        return Result(success=False, error=published_design_result.error)
    published_design = published_design_result.value

    audit_report_result = app.design_auditor.audit(published_design)
    if not audit_report_result.success:
        return Result(success=False, error=audit_report_result.error)

    publish_outcome_result = app.design_auditor.publish_result(audit_report_result.value)
    if not publish_outcome_result.success:
        return Result(success=False, error=publish_outcome_result.error)
    approved_design = publish_outcome_result.value

    context_result = app.executor.load_design(
        workflow_id=request.workflow_id,
        approved_design=to_executor_approved_design(approved_design),
        design_document=published_design,
        project_context={},
        repository_information=RepositoryInfo(
            repository_id="stub/repo", root_path="/tmp/stub-repo", default_branch="main"
        ),
    )
    if not context_result.success:
        return Result(success=False, error=context_result.error)

    implementation_result = app.executor.implement(context_result.value)
    if not implementation_result.success:
        return Result(success=False, error=implementation_result.error)
    implementation = implementation_result.value

    test_result = app.tester.execute_tests(implementation.implementation)
    if not test_result.success:
        return Result(success=False, error=test_result.error)

    quality_gate_result = app.tester.validate_quality(test_result.value)
    if not quality_gate_result.success:
        return Result(success=False, error=quality_gate_result.error)

    test_report_result = app.tester.publish_report(quality_gate_result.value)
    if not test_report_result.success:
        return Result(success=False, error=test_report_result.error)

    pr_input = CreatePullRequestInput(
        workflow_id=request.workflow_id,
        implementation_result=implementation,
        test_report=test_report_result.value,
        repository_information=RepositoryInformation(owner="stub", name="repo", default_branch="main"),
        branch_information=BranchInformation(base_branch="main", head_branch=f"bootstrap/{request.workflow_id}"),
        project_context={
            "design_document": published_design,
            "execution_plan": execution_plan,
            "audit_report": audit_report_result.value,
            "business_goal": request.business_goal,
        },
    )
    pr_result = app.pr_creator.create_pr(pr_input)
    if not pr_result.success:
        return Result(success=False, error=pr_result.error)

    review_report_result = app.reviewer.review(pr_result.value)
    if not review_report_result.success:
        return Result(success=False, error=review_report_result.error)

    return app.reviewer.publish_review(review_report_result.value)
```

- [ ] **Step 4: テストを実行し、1段ずつ失敗を解消する**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest tests.bootstrap.test_workflow -v`

失敗した場合、`Result.error`のメッセージから「どのモジュールのどの必須フィールドが欠けているか」を特定し、該当モジュールの実装(`src/<module>/`)を読んで正しい値を`workflow.py`に追加すること。特に以下が典型的な追加要因になりうる:
- `Architect.publish_design()`の実引数名(`design_document`/`validation_result`のキーワード名が異なる可能性。`src/architect/module.py`で確認)
- `Executor.load_design()`の`approved_design`/`design_document`のうち、`design_document.metadata["workflow_id"]`が実際に設定されているか(Task 4の`Application`構築時点でArchitectの`build_metadata()`が正しく動作していることが前提)
- `Reviewer.review()`が`project_context`から読み出す追加の必須キーの有無

- [ ] **Step 5: 全てPASSすることを確認する**

Expected: PASS。`result.value`(ReviewOutcome)が取得できる。

- [ ] **Step 6: Ruff/Black + コミット**

```bash
cd "C:\Users\user1\Downloads\AI Autonomous Development Platform"
python -m ruff check --fix src/bootstrap tests/bootstrap && python -m black src/bootstrap tests/bootstrap
git add src/bootstrap/workflow.py tests/bootstrap/test_workflow.py
git commit -m "feat(bootstrap): orchestrate Planner-to-Reviewer synthetic workflow"
```

---

### Task 6: CLIエントリポイント

**Files:**
- Create: `src/bootstrap/run.py`
- Test: `tests/bootstrap/test_run.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/bootstrap/test_run.py
import io
import unittest
from contextlib import redirect_stdout

from bootstrap.run import main


class MainTest(unittest.TestCase):
    def test_main_prints_review_outcome_for_valid_instruction(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["LP改善", "--business-goal", "LINE登録数最大化"])

        self.assertEqual(exit_code, 0)
        self.assertIn("next_module", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest tests.bootstrap.test_run -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: `run.py`を実装する**

```python
# src/bootstrap/run.py
"""配線層(Phase 0)のCLIエントリポイント。

外部サービスに一切接続せず、1つの合成Workflowを最後まで実行して結果を表示する。
"""

import argparse
import sys

from bootstrap.wiring import build_application
from bootstrap.workflow import run_workflow
from foundation.utils import generate_id
from planner.types import NormalizedRequest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Development Pipeline bootstrap runner")
    parser.add_argument("instruction", help="自然言語の実行指示(例: 'LP改善')")
    parser.add_argument("--business-goal", default="", help="事業目的(例: 'LINE登録数最大化')")
    args = parser.parse_args(argv)

    app = build_application()
    request = NormalizedRequest(
        workflow_id=generate_id(),
        instruction=args.instruction,
        business_goal=args.business_goal,
    )

    result = run_workflow(app, request)
    if not result.success:
        print(f"workflow failed: {result.error}", file=sys.stderr)
        return 1

    print(result.value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: テストを実行して通過を確認する**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest tests.bootstrap.test_run -v`
Expected: PASS。`NormalizedRequest`の実フィールド名・`ReviewOutcome`の文字列表現に`next_module`が含まれない場合は、実際の`__str__`/`__repr__`または`dataclasses.asdict()`表示に合わせてテストのアサーションを調整すること。

- [ ] **Step 5: 手動での疎通確認**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m bootstrap.run "LP改善" --business-goal "LINE登録数最大化"`
Expected: 例外なく終了し、ReviewOutcomeの内容が標準出力に表示される。

- [ ] **Step 6: 全体テストスイートを実行し、既存793+件に影響が無いことを確認**

Run: `cd "C:\Users\user1\Downloads\AI Autonomous Development Platform" && PYTHONPATH=src python -m unittest discover -s tests -t . -v 2>&1 | tail -20`
Expected: 既存モジュールのテスト件数がすべて維持されたまま、`tests/bootstrap/`分(約15〜20件)が追加されてPASSする。

- [ ] **Step 7: Ruff/Black + コミット**

```bash
cd "C:\Users\user1\Downloads\AI Autonomous Development Platform"
python -m ruff check --fix src tests && python -m black src tests
python -m ruff check src tests
git add src/bootstrap/run.py tests/bootstrap/test_run.py
git commit -m "feat(bootstrap): add CLI entry point for the synthetic end-to-end workflow"
```

- [ ] **Step 8: CHANGELOG.mdへの追記**

`docs/CHANGELOG.md`に`## v1.1.0 (Phase 0: 配線層)`セクションを追加し、本Task群で実施した内容(スタブ外部アダプタ・Configuration Manager配線・型不整合アダプタ・21モジュール結線・合成Workflow実行確認)を記録する。

---

## Self-Review メモ(作成者による事前チェック済み事項)

- **Spec coverage**: ROADMAP_v1.1.mdのPhase 0記述(配線層構築・合成Workflow実証・既知の未解決事項の解消)を全てTaskとして反映済み。
- **Placeholder scan**: `None`を暫定的に渡している箇所(Task 4 Step 3の`weekly_reviewer_config`, `github_client=None`, `command_router_client=None`)は、Step 4で実際のソースを確認して具体的な実装に置き換える明示的な指示を付けており、「後で実装」を放置する記述ではない。
- **Type consistency**: `ExecutionPlan`/`ApprovedDesign`/`CreatePullRequestInput`等のフィールド名は、事前のコード調査(Explore agent 2件)で実ファイルから直接確認した名称を使用している。ただし`Planner.NormalizedRequest`・`WeeklyReviewerConfig`・`Tester.CommandExecutor`の正確なフィールド/メソッド名は本計画作成時点で全項目を実ファイル突合できていないため、各Taskの実行時に該当ソースファイルを必ず開いて確認するよう明記した(Task 1 Step 4, Task 4 Step 4, Task 5 Step 2/4, Task 6 Step 4)。
