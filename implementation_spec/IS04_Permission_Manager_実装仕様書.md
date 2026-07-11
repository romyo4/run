# IS04 Permission Manager 実装仕様書

## 0. 参照文書

| 文書 | 版 | 役割 |
|---|---|---|
| `M04 Permission Manager.txt` | Design Freeze v1.0 | 本モジュールの詳細設計書（唯一の正） |
| `M00 Foundation.txt` | Design Freeze v1.0 | F00原則 / F01 Domain Model / F02 共通Interface / F03 Configuration取得パターン / エラー階層 / ログ規約の定義元 |

本仕様書は上記2文書に明記された内容のみを実装対象とする。両文書に記載のない機能（RBAC, ABAC, OAuth, SSO等）は推測で追加しない。

---

## 1. モジュール概要

Permission Manager（M04）は、AI Development Pipeline において Planner・Designer・Executor・Reviewer・Scheduler・Knowledge Manager・Command Router の各モジュールが実行しようとする操作について、**Module × Operation の組み合わせのみ**で実行可否を判定する専用モジュールである。認証・OAuth・ログイン管理・Secret管理・業務ロジックは一切扱わず、Role/Group/User/継承/ポリシーエンジンといった高度な判定方式もMVPでは採用しない。取得すべき権限情報が得られない場合は必ず Deny 側へフェイルセーフし、許可側へ倒すことは constraints 上禁止されている。公開インターフェースは `check_permission()` / `list_permissions()` / `reload()` の3つに限定され、Foundation の `BaseModule` を継承し `Result[T]` パターンで結果を返却する。

---

## 2. ファイル構成

```text
src/permission_manager/
├── __init__.py               # 公開シンボルの再エクスポート（PermissionManager, Module, Operation, Effect, PermissionEntry）
├── models.py                 # Module / Operation / Effect の Enum、PermissionEntry dataclass の定義
├── default_permissions.py    # 設計書3.4の権限一覧をハードコードしたMVPデフォルトテーブル（DEFAULT_PERMISSIONS）
├── permission_manager.py      # PermissionManager本体（BaseModule継承。check_permission/list_permissions/reloadを実装）
└── tests/
    ├── __init__.py
    └── test_permission_manager.py   # Unit Test（unittest）
```

### 各ファイルの役割

| ファイル | 役割 | 備考 |
|---|---|---|
| `models.py` | `Module`, `Operation`, `Effect` の3つのEnumと `PermissionEntry` dataclassを定義する | Foundation `types.py` のDomain Modelは変更・追加しない（本モジュール固有の型として独立定義） |
| `default_permissions.py` | 設計書3.4の表をそのままPythonデータとして表現した `DEFAULT_PERMISSIONS: tuple[PermissionEntry, ...]` を定義する | MVPでは外部ファイル・DBを持たず、この定数がフェイルセーフ時にも使われる唯一の正規データ |
| `permission_manager.py` | `PermissionManager` クラス本体。`foundation.base_module.BaseModule` を継承し、`name()`, `health_check()`, `check_permission()`, `list_permissions()`, `reload()` を実装する | GitHub/Slack/Discord/Codex/Workflow変更/Task変更は一切呼び出さない（4.1制約） |
| `tests/test_permission_manager.py` | 許可/拒否判定・フェイルセーフ・reload・ログ出力のUnit Test | `unittest` のみ使用（`pytest`不使用） |

本モジュールはファイルシステムやOSパスへ直接アクセスしないため（権限データはPython定数、または F03 `ConfigurationClient` 経由で取得し、生ファイルは扱わない）、`pathlib` の使用箇所は原則発生しない。将来的にファイルベースの権限定義を追加する場合のみ `pathlib.Path` を使用し、`os.path` は使用しない。

---

## 3. データクラス定義

設計書 3.1〜3.2、3.4 に基づき、`Module` / `Operation` は文字列Enum、判定結果は `Effect` Enum、権限定義単位は `PermissionEntry` dataclass として表現する。

```python
# src/permission_manager/models.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Module(str, Enum):
    """権限判定の対象となる呼び出し元モジュール（設計書1. 適用対象 / 3.4）。"""

    PLANNER = "Planner"
    DESIGNER = "Designer"
    EXECUTOR = "Executor"
    REVIEWER = "Reviewer"
    SCHEDULER = "Scheduler"
    KNOWLEDGE_MANAGER = "Knowledge Manager"
    COMMAND_ROUTER = "Command Router"


class Operation(str, Enum):
    """Moduleが実行しようとする操作（設計書3.4）。"""

    EXECUTION_PLAN_CREATE = "ExecutionPlan作成"
    DESIGN_CREATE = "Design作成"
    PULL_REQUEST_CREATE = "Pull Request作成"
    REVIEW_CREATE = "Review作成"
    WORKFLOW_START = "Workflow開始"
    KNOWLEDGE_UPDATE = "Knowledge更新"
    COMMAND_DISPATCH = "Command振り分け"


class Effect(str, Enum):
    """Module × Operation の組み合わせに対する判定結果（設計書3.2）。"""

    ALLOW = "Allow"
    DENY = "Deny"


@dataclass(frozen=True)
class PermissionEntry:
    """Permissionの管理単位（設計書3.2: Module / Operation / Allow-Deny）。"""

    module: Module
    operation: Operation
    effect: Effect
```

### 3.4節 権限一覧のデータ表現

`default_permissions.py` にて、設計書3.4の表をそのまま `PermissionEntry` の集合として定義する。MVPでは「表に無い組み合わせ＝Deny」というフェイルセーフ方針（4.3）のため、テーブルには **Allow のエントリのみ** を列挙し、Denyは「該当エントリが存在しない」ことで暗黙的に表現する。

```python
# src/permission_manager/default_permissions.py
from __future__ import annotations

from .models import Effect, Module, Operation, PermissionEntry

DEFAULT_PERMISSIONS: tuple[PermissionEntry, ...] = (
    PermissionEntry(Module.PLANNER, Operation.EXECUTION_PLAN_CREATE, Effect.ALLOW),
    PermissionEntry(Module.DESIGNER, Operation.DESIGN_CREATE, Effect.ALLOW),
    PermissionEntry(Module.EXECUTOR, Operation.PULL_REQUEST_CREATE, Effect.ALLOW),
    PermissionEntry(Module.REVIEWER, Operation.REVIEW_CREATE, Effect.ALLOW),
    PermissionEntry(Module.SCHEDULER, Operation.WORKFLOW_START, Effect.ALLOW),
    PermissionEntry(Module.KNOWLEDGE_MANAGER, Operation.KNOWLEDGE_UPDATE, Effect.ALLOW),
    PermissionEntry(Module.COMMAND_ROUTER, Operation.COMMAND_DISPATCH, Effect.ALLOW),
)
```

この7件は設計書3.4の表と1対1で対応し、それ以外のModule×Operationの組み合わせは全てDeny判定となる。新しいModule/Operationの追加は本ファイルの改訂によってのみ行い、Role/Group/User等の概念は追加しない（4.2）。

---

## 4. クラス・関数シグネチャ

`PermissionManager` は Foundation の `BaseModule`（F02）を継承する。公開インターフェースの名称・シグネチャは設計書3.3と完全一致させる。

```python
# src/permission_manager/permission_manager.py
from __future__ import annotations

from foundation.base_module import BaseModule
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result

from .default_permissions import DEFAULT_PERMISSIONS
from .models import Effect, Module, Operation, PermissionEntry

MODULE_NAME = "permission_manager"


class PermissionManager(BaseModule):
    """Module × Operation のみで実行可否を判定する。認証・業務ロジックは扱わない。"""

    def __init__(self, config_client: ConfigurationClient | None = None) -> None:
        """
        Args:
            config_client: F03 ConfigurationClient実装。Noneの場合はDEFAULT_PERMISSIONSのみで動作する
                （MVPでは起動時にreload()を呼ばない限りDEFAULT_PERMISSIONSが唯一の定義元）。
        """
        ...

    def name(self) -> str:
        """BaseModule必須実装。'permission_manager' を返す。"""
        ...

    def health_check(self) -> Result[bool]:
        """権限テーブルがロード済み（空でない）ことを確認する。"""
        ...

    def check_permission(self, module: Module, operation: Operation) -> Result[bool]:
        """
        指定Moduleが指定Operationを実行可能か判定する（設計書3.3 check_permission）。

        Returns:
            Result[bool]:
                - value: True=Allow / False=Deny
                - success: 判定処理自体が正常に完了した場合はTrue（Denyも正常な判定結果でありsuccess=True）。
                  module/operationの型不正等、判定不能な入力エラーの場合のみsuccess=False。
                - error: Denyの場合、理由(reason)を保持する
                  `foundation.exceptions.PermissionDeniedError` を設定する（success=Trueのまま）。
                  Allowの場合はerror=None。
        """
        ...

    def list_permissions(self, module: Module) -> Result[list[Operation]]:
        """
        指定Moduleに許可されているOperation一覧を取得する（設計書3.3 list_permissions）。

        Returns:
            Result[list[Operation]]:
                - value: 許可されたOperationのリスト（許可が1件もない場合は空リスト）
                - フェイルセーフ時（権限情報取得不可）も空リストを返す（許可側へ倒さない）
        """
        ...

    def reload(self) -> Result[bool]:
        """
        Permission定義を再読込する（設計書3.3 reload。MVPではシステム起動時のみ利用）。

        - config_clientが設定されている場合、ConfigurationClient.get("permission_manager", "permissions")
          経由で最新定義の取得を試みる。
        - 取得に失敗した場合、現在保持しているテーブル（初回はDEFAULT_PERMISSIONS）を維持したまま
          Result(success=False, value=False, error=ConfigurationError(...)) を返す。
          既存テーブルを空にしてはならない（本体が保持するテーブルが空になることはcheck_permissionの
          全面Denyに直結するため、意図しない全面ロックアウトを避ける一方、フェイルセーフ方針(4.3)は
          「情報が得られない組み合わせはDeny」を意味しており、テーブル自体の消失を正当化しない）。
        - 取得に成功した場合、内部テーブルを新しい定義で置き換え Result(success=True, value=True, error=None) を返す。
        """
        ...
```

### シグネチャ設計の根拠（F02整合性の明記）

- 設計書3.3は `check_permission()` の出力を「allowed: boolean, reason: string」としているが、Foundation F02は「真偽値のみを返す判定系API（例としてPermission Managerのcheck_permission()）はResult[bool]として扱う」と明記している。本仕様書はF02を優先し、戻り値の型は厳密に `Result[bool]` とする。
- 「reason」はResult構造から失われないよう、Deny時は `Result.error` に `PermissionDeniedError(reason)` を設定することで表現する。ただし `success` は判定処理自体の成否を表すため、Denyは正常な業務判定でありTrueのままとする（successをFalseにするのは、判定不能な技術的異常時のみ）。
- Allow時・Deny時いずれも 6章のログ仕様に従い reason を必ずログへ出力するため、reason情報はログ経由で必ず追跡可能（Traceability, F00）。

---

## 5. エラー処理

### 5.1 使用するFoundationエラー

`foundation.exceptions` / `foundation.errors` から以下を利用する。新規の基底例外は追加しない（Foundation側でのみ追加可能、4.2/M00 3.6）。

| エラークラス | 使用場面 |
|---|---|
| `PermissionDeniedError` | `check_permission()` がDenyと判定した場合、`Result.error` に設定し `reason` をmessageとして保持する |
| `ValidationError` | `module`/`operation` が `Module`/`Operation` Enum以外の値で渡された場合（`require_not_none` / `require_in` で検証） |
| `ConfigurationError` | `reload()` 時に `ConfigurationClient.get()` が失敗した場合 |

### 5.2 フェイルセーフ実装ロジック（設計書4.3）

「Permission情報が取得できない場合はDenyを返す。許可側へ倒してはならない。」を以下のロジックで実装する。

```text
check_permission(module, operation):
    1. module, operation の型検証（ValidationError発生時は Result(success=False, value=None, error=ValidationError) を返す）
    2. 内部権限テーブル(self._permissions)が空 or 未初期化の場合:
         → reason = "permission情報が取得できないためフェイルセーフとしてDenyを返す"
         → Result(success=True, value=False, error=PermissionDeniedError(reason)) を返す（ログはWARNINGレベル）
    3. self._permissions 内に (module, operation) の Allow エントリが存在する場合:
         → reason = "Module×OperationがPermissionテーブルにAllow登録されている"
         → Result(success=True, value=True, error=None) を返す（ログはINFOレベル）
    4. 存在しない場合（未定義の組み合わせ）:
         → reason = "Module×Operationの組み合わせが許可テーブルに存在しないためDeny"
         → Result(success=True, value=False, error=PermissionDeniedError(reason)) を返す（ログはINFOレベル）
```

`list_permissions()` も同様に、テーブル未取得・空の場合は例外を送出せず空リストを返す（Denyと同じ「許可側へ倒さない」方針）。

`reload()` が失敗しても、既存テーブル（初回起動時はDEFAULT_PERMISSIONS）はそのまま保持し、更新に失敗したことのみをResultとログで通知する。これにより「取得できない場合にテーブルごと消失してcheck_permissionが常時Denyになる」という過度な事故拡大を防ぎつつ、reload失敗自体はsuccess=Falseとして正直に報告する。

### 5.3 責務外操作の禁止（4.1整合）

`permission_manager.py` は GitHub API・Slack・Discord・Codex実行・Workflow変更・Task変更のいずれのクライアントもimport・呼び出ししない。依存は `foundation.*` と `default_permissions.py` / `models.py` のみに限定する。

---

## 6. ロギング仕様

### 6.1 ロガー取得

`foundation.logger.get_logger("permission_manager")` で取得したLoggerを `PermissionManager.__init__` 内で1度だけ生成し、インスタンス変数として保持する。標準ライブラリ `logging` 以外は使用しない（Foundation 3.7準拠）。

### 6.2 出力項目（設計書4.4）

判定結果は必ずログへ出力する。出力項目は以下の5点に固定し、これ以外の情報（内部設定値・ConfigurationClientの生レスポンス等）は出力しない。

```text
timestamp   # loggingのデフォルトフォーマッタが自動付与
module      # Module.value （例: "Planner"）
operation   # Operation.value （例: "ExecutionPlan作成"）
result      # "Allow" / "Deny"
reason      # 判定理由の文字列
```

### 6.3 実装方法

```python
def _log_decision(self, module: Module, operation: Operation, effect: Effect, reason: str) -> None:
    level = logging.WARNING if effect is Effect.DENY and self._is_failsafe(reason) else logging.INFO
    self._logger.log(
        level,
        "module=%s operation=%s result=%s reason=%s",
        module.value,
        operation.value,
        effect.value,
        reason,
    )
```

- ログメッセージは `module=... operation=... result=... reason=...` の固定フォーマットのみを組み立てる。`self._permissions` の全件ダンプや `ConfigurationClient.get()` の生の戻り値（`Result.value`全体）を `%s` でそのまま埋め込むことは禁止する。
- 本モジュールはSecret/Token/Credentialを一切保持しない（設計書対象外）ため、ログに機密情報が混入する経路自体が存在しない。ただし将来的な拡張を見越し、`_log_decision` に渡すのは `Module` Enum・`Operation` Enum・`Effect` Enum・`reason: str` の4値のみに限定し、任意オブジェクトの `repr()`/`__dict__` をログへ渡す実装を禁止する。
- `reload()` の失敗ログも同様に `module=permission_manager operation=reload result=Failure reason=<ConfigurationErrorのmessageのみ>` の形式とし、`ConfigurationClient` から返却された設定値そのものはログへ出力しない。

---

## 7. Unit Testケース一覧（`unittest`）

`tests/test_permission_manager.py` に以下のテストメソッドを実装する（`pytest` は使用しない）。

### 7.1 check_permission — 許可判定

- `test_check_permission_allows_planner_execution_plan_create`
- `test_check_permission_allows_designer_design_create`
- `test_check_permission_allows_executor_pull_request_create`
- `test_check_permission_allows_reviewer_review_create`
- `test_check_permission_allows_scheduler_workflow_start`
- `test_check_permission_allows_knowledge_manager_knowledge_update`
- `test_check_permission_allows_command_router_command_dispatch`
- `test_check_permission_returns_result_bool_with_value_true_on_allow`

### 7.2 check_permission — 拒否判定

- `test_check_permission_denies_undefined_module_operation_pair`（例: Planner + Design作成）
- `test_check_permission_denies_when_operation_belongs_to_other_module`
- `test_check_permission_denied_result_contains_permission_denied_error_with_reason`

### 7.3 フェイルセーフ

- `test_check_permission_denies_when_permission_table_is_empty`
- `test_check_permission_denies_when_configuration_client_fetch_fails`
- `test_check_permission_never_returns_allow_on_ambiguous_or_error_state`
- `test_list_permissions_returns_empty_list_when_permission_table_unavailable`
- `test_list_permissions_never_returns_operations_not_explicitly_allowed`

### 7.4 list_permissions

- `test_list_permissions_returns_single_operation_for_planner`
- `test_list_permissions_returns_empty_list_for_module_with_no_allowed_operations`

### 7.5 reload

- `test_reload_success_replaces_permission_table_with_configuration_client_data`
- `test_reload_failure_keeps_previous_permission_table_intact`
- `test_reload_failure_returns_result_success_false`
- `test_reload_without_configuration_client_keeps_default_permissions`

### 7.6 BaseModule / health_check

- `test_name_returns_permission_manager`
- `test_health_check_returns_true_when_permissions_loaded`
- `test_health_check_returns_false_when_permissions_table_empty`

### 7.7 入力検証

- `test_check_permission_raises_validation_error_result_for_invalid_module_type`
- `test_check_permission_raises_validation_error_result_for_invalid_operation_type`

### 7.8 ログ出力

- `test_check_permission_logs_timestamp_module_operation_result_reason`（`assertLogs`使用）
- `test_check_permission_log_message_does_not_contain_raw_configuration_payload`
- `test_reload_failure_logs_configuration_error_reason_only`

### 7.9 データ整合性

- `test_default_permissions_matches_design_section_3_4_table_exactly`（7件のPermissionEntryが設計書3.4と1対1で一致することを検証）

---

## 8. MVP範囲の明記

設計書 5.3節（重厚壮大化監査）に基づき、以下の機能は本実装の対象外とする。将来のバージョンで必要になった場合も、本モジュールの改訂ではなく新しい設計・Design Freezeバージョンの合意を経て追加すること。

- RBAC（Role Based Access Control）
- ABAC（Attribute Based Access Control）
- Policy Engine（動的ポリシー評価を含む）
- LDAP連携
- OAuth
- SSO
- Organization管理
- Attribute Based Permission

判定方式は設計書4.2の通り **Module × Operation のみ** に限定し、Role / Group / User / Inheritance は一切採用しない。またPermission Managerは4.1の通り、GitHub API呼び出し・Slack送信・Discord送信・Codex実行・Workflow変更・Task変更のいずれも行わない。ユーザー認証・ログイン管理・Secret管理も対象外である（1. 適用対象/対象外）。
