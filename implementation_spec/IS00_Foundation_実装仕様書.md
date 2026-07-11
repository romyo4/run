# IS00 Foundation 実装仕様書

- 対象設計書: `M00 Foundation.txt`（Design Freeze v1.0）
- 対象バージョン: `DESIGN_VERSION = "v1.0"`
- 実装言語: Python 3.13
- 配置先: `src/foundation/`

本書は M00 Foundation の詳細設計書を実装可能な粒度に具体化したものであり、設計書に記載のない機能・APIを追加しない。設計書の記述と本書が矛盾する場合は設計書を正とする。

---

## 1. モジュール概要

Foundation は AI Development Pipeline を構成する全22モジュールが共通で参照する基盤ライブラリであり、F00（設計原則カタログ）・F01（共通Domain Model）・F02（共通Interface: `BaseModule`, `Result[T]`）・F03（Configuration取得パターン: `ConfigurationClient`）に加え、共通エラー階層（`FoundationError`系）・共通ログ初期化（`get_logger`）・共通バリデーション・バージョン定数を提供する。Foundation自身は業務ロジック・Workflow制御・外部サービス連携・Task/Configuration/Knowledgeの実体管理を一切行わず、他のいかなるモジュールにも依存しない依存グラフの最下層として実装する。

---

## 2. ファイル構成

`src/foundation/` 配下は設計書 3.1節のディレクトリ構成と一致させる。

| ファイル | 役割 |
|---|---|
| `__init__.py` | パッケージの公開API（Domain Model、`BaseModule`、`Result`、`ConfigurationClient`、`get_logger`、validation関数群、例外クラス、`DESIGN_VERSION`）を re-export する。新規ロジックは持たない。 |
| `result.py` | `Result[T]` dataclass（F02）を定義する。 |
| `errors.py` | `FoundationError` を頂点とする例外クラス階層の実体を定義する（3章参照）。 |
| `exceptions.py` | `errors.py` で定義した例外クラスを re-export する薄いモジュール。設計書 3.6節が `errors.py` / `exceptions.py` を並記していることに対応し、例外の実体は `errors.py` に一本化した上で、既存コード・他モジュールが `foundation.exceptions` からimportする経路も提供する（クラスの二重定義はしない）。 |
| `constants.py` | 他ファイルの実装で使う軽量な定数値（ログフォーマット文字列 `LOG_FORMAT` など）を集約する。業務定数・設定値は置かない（それはConfiguration Managerの責務）。 |
| `base_module.py` | `BaseModule` 抽象基底クラス（F02）を定義する。 |
| `interfaces.py` | `ConfigurationClient` 抽象インターフェース（F03）を定義する。 |
| `logger.py` | `get_logger(module_name)` を定義する（3.7節）。 |
| `types.py` | F01 共通Domain Model（13種類）の dataclass を定義する（3章参照）。 |
| `version.py` | `DESIGN_VERSION = "v1.0"` を定義する（3.9節）。 |
| `utils.py` | Domain Model の共通属性（`id` / `created_at` / `updated_at`）を生成するための最小限のヘルパー関数（`generate_id()`, `utc_now()`）のみを置く。業務ロジックは持たない。 |
| `validation.py` | `require_not_none` / `require_non_empty` / `require_in` および公開インターフェース `validate(value, rule)` を定義する（3.8, 3.10節）。 |
| `tests/` | unittest によるテスト一式（7章参照）。 |

---

## 3. データクラス定義（F01 共通Domain Model）

設計書 3.3節の通り、Foundationが保証するのは**各Domainの共通属性の型・命名規約のみ**であり、モジュール固有の属性は各モジュールの詳細設計書側で追加する（Foundationの`types.py`には含めない）。したがって`types.py`では、下記13種類それぞれを共通属性のみを持つ独立したdataclassとして定義する。

共通属性（全Domain共通）:

```python
id: str                          # generate_id() により UUID4 文字列を既定生成
created_at: datetime              # utc_now() により生成時刻(UTC)を既定生成
updated_at: datetime               # utc_now() により生成時刻(UTC)を既定生成
metadata: dict[str, Any]           # 既定値は空dict
```

実装（13クラス共通パターン。以下 `Task` を例示、他12種も同一構造）:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from foundation.utils import generate_id, utc_now


@dataclass
class Task:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubTask:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Design:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Implementation:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PullRequest:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Review:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Knowledge:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Context:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Configuration:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Notification:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommunicationMessage:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)
```

補足（実装上の前提・要確認事項）:
- 各モジュール固有フィールド（例: `Task.title`, `Task.status` 等）は本書の対象外であり、各モジュールの実装仕様書（IS01〜IS21）側で `Task` を継承またはモジュール側dataclassとして拡張定義する。Foundation側の13クラスにフィールドを追加してはならない（4.3節の制約）。
- `id`/`created_at`/`updated_at` のデフォルト生成方法（`generate_id`/`utc_now`）は設計書に明記がないため、dataclassの実務上の必要性から本書で最小限に補完した実装判断である。生成ロジックを持たせず必須引数化する方針も選択肢としてあり得るが、13種のDomain全てで生成規則が同一である以上、`utils.py` に集約する方が重複実装を避けられるためこちらを採用する。

---

## 4. クラス・関数シグネチャ

### 4.1 `result.py`

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

from foundation.errors import FoundationError

T = TypeVar("T")


@dataclass
class Result(Generic[T]):
    success: bool
    value: T | None = None
    error: FoundationError | None = None
```

- 生成は dataclass の通常コンストラクタで行う（`Result(success=True, value=x)` / `Result(success=False, error=err)`）。設計書に定義のない `Result.ok()` / `Result.fail()` 等の便宜コンストラクタは追加しない。
- 真偽値のみを返す判定系API（例: Permission Managerの`check_permission()`）は `Result[bool]` として扱う（設計書3.4節）。

### 4.2 `base_module.py`

```python
from abc import ABC, abstractmethod

from foundation.result import Result


class BaseModule(ABC):
    @abstractmethod
    def name(self) -> str:
        """モジュール名を返す。"""

    @abstractmethod
    def health_check(self) -> Result[bool]:
        """モジュールの健全性を判定する。"""
```

### 4.3 `interfaces.py`

```python
from abc import ABC, abstractmethod
from typing import Any

from foundation.result import Result


class ConfigurationClient(ABC):
    @staticmethod
    @abstractmethod
    def get(module_name: str, key: str) -> Result[Any]:
        """指定モジュール・キーの設定値を取得する。実装はConfiguration Manager(M17)が提供する。"""
```

### 4.4 `logger.py`

```python
import logging

from foundation.constants import LOG_FORMAT


def get_logger(module_name: str) -> logging.Logger:
    """module_name に対応するLoggerを返す。出力フォーマットは
    'timestamp | module_name | level | message' に統一する。"""
```

### 4.5 `validation.py`

```python
from typing import Any, Callable, Iterable

from foundation.errors import ValidationError
from foundation.result import Result


def require_not_none(value: Any, field_name: str) -> None:
    """value が None の場合 ValidationError を送出する。"""


def require_non_empty(value: Any, field_name: str) -> None:
    """value が空（空文字列・空コレクション等）の場合 ValidationError を送出する。"""


def require_in(value: Any, allowed_values: Iterable[Any], field_name: str) -> None:
    """value が allowed_values に含まれない場合 ValidationError を送出する。"""


def validate(value: Any, rule: Callable[[Any], bool]) -> Result[bool]:
    """rule(value) を評価し、結果を Result[bool] として返す。
    rule 実行時の例外は ValidationError にラップして Result[bool](success=False, error=...) を返す。"""
```

補足（要確認事項）: 設計書3.10節に記載の `validate(value, rule) -> Result[bool]` は、`rule` の型・意味が設計書内で明文化されていない。本書では `rule` を「valueを受け取りbool を返す述語関数」と解釈し、`require_*` 系（例外送出型）とは異なる「例外を送出しない判定API」として位置づけた。この解釈は実装前提の補完であり、設計書の明文規定ではない点に留意すること。

### 4.6 `version.py`

```python
DESIGN_VERSION: str = "v1.0"
```

### 4.7 `utils.py`

```python
import uuid
from datetime import datetime, timezone


def generate_id() -> str:
    """UUID4文字列を生成する。"""


def utc_now() -> datetime:
    """UTC現在時刻を返す。"""
```

---

## 5. エラー処理

`errors.py` にて、設計書3.6節の例外階層を標準 `Exception` のサブクラスとして実装する。

```python
class FoundationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(FoundationError):
    pass


class NotFoundError(FoundationError):
    pass


class PermissionDeniedError(FoundationError):
    pass


class StateTransitionError(FoundationError):
    pass


class ConfigurationError(FoundationError):
    pass


class ExternalServiceError(FoundationError):
    pass
```

- 各モジュールは必要に応じてこれらを継承し、モジュール固有の例外を定義できる（例: `class TaskNotFoundError(NotFoundError)`）。新しい基底例外（`FoundationError`の直下の兄弟クラス）の追加はFoundation側でのみ行い、他モジュールが基底例外を追加することは禁止する（設計書3.6節）。
- `exceptions.py` は `errors.py` の全クラスを re-export するのみとし、クラス定義を重複させない。

```python
# exceptions.py
from foundation.errors import (
    ConfigurationError,
    ExternalServiceError,
    FoundationError,
    NotFoundError,
    PermissionDeniedError,
    StateTransitionError,
    ValidationError,
)

__all__ = [
    "ConfigurationError",
    "ExternalServiceError",
    "FoundationError",
    "NotFoundError",
    "PermissionDeniedError",
    "StateTransitionError",
    "ValidationError",
]
```

---

## 6. ロギング仕様

### 6.1 `get_logger(module_name)` の実装方針

- 標準ライブラリ `logging` のみを使用する（外部ロギングライブラリは導入しない）。
- `logging.getLogger(module_name)` を返し、未設定の場合のみ `logging.StreamHandler` と `logging.Formatter` を1つだけ addHandler する（多重初期化・重複ハンドラを防止するため、既にハンドラが設定済みの場合は追加しない）。
- 出力フォーマットは設計書3.7節の通り固定する。

```python
LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
```

- ログレベルはCallerが `logger.info()` / `logger.warning()` 等で制御し、`get_logger()` 自体はデフォルトレベル（`logging.INFO`）のみを設定する。
- Secret・Token・Credential・Knowledge本文などの機密情報をログ出力しない責務は各モジュール側にあり、`get_logger()` 自体はマスキング処理を行わない（設計書3.7節の通り、Foundationはロガー初期化のみを提供する）。

### 6.2 Foundation内部動作ログ（設計書4.4節）

Foundation自身の内部動作（Logger初期化失敗等、Foundation自身のバグ調査用途）に限り、以下の項目を記録する。業務データや他モジュールの動作は記録しない。

```text
timestamp
module_name
event
result
```

この内部ログは `logger.py` が自身のフォールバック処理（例: Formatter設定失敗時の標準エラー出力）でのみ使用し、汎用の構造化ログ基盤としては実装しない（重厚壮大化の回避）。

---

## 7. Unit Testケース一覧（unittest）

`foundation/tests/` にファイル単位でテストモジュールを配置する。

### 7.1 `test_types.py`（Domain Model共通属性テスト、13クラス共通の観点を各クラスに適用）

- `test_task_default_fields_are_generated`
- `test_task_id_is_unique_across_instances`
- `test_task_metadata_defaults_to_empty_dict`
- `test_subtask_default_fields_are_generated`
- `test_workflow_default_fields_are_generated`
- `test_design_default_fields_are_generated`
- `test_implementation_default_fields_are_generated`
- `test_testresult_default_fields_are_generated`
- `test_pullrequest_default_fields_are_generated`
- `test_review_default_fields_are_generated`
- `test_knowledge_default_fields_are_generated`
- `test_context_default_fields_are_generated`
- `test_configuration_default_fields_are_generated`
- `test_notification_default_fields_are_generated`
- `test_communicationmessage_default_fields_are_generated`
- `test_all_domain_models_share_common_field_names_and_types`（id: str, created_at/updated_at: datetime, metadata: dict であることをリフレクションで一括検証）

### 7.2 `test_result.py`

- `test_result_success_holds_value`
- `test_result_failure_holds_error`
- `test_result_value_defaults_to_none`
- `test_result_error_defaults_to_none`
- `test_result_is_generic_and_accepts_any_value_type`

### 7.3 `test_base_module.py`

- `test_base_module_cannot_be_instantiated_directly`
- `test_concrete_subclass_must_implement_name`
- `test_concrete_subclass_must_implement_health_check`
- `test_concrete_subclass_health_check_returns_result_bool`

### 7.4 `test_interfaces.py`

- `test_configuration_client_cannot_be_instantiated_directly`
- `test_configuration_client_subclass_get_returns_result`

### 7.5 `test_errors.py` / `test_exceptions.py`

- `test_foundation_error_is_exception_subclass`
- `test_validation_error_is_foundation_error_subclass`
- `test_not_found_error_is_foundation_error_subclass`
- `test_permission_denied_error_is_foundation_error_subclass`
- `test_state_transition_error_is_foundation_error_subclass`
- `test_configuration_error_is_foundation_error_subclass`
- `test_external_service_error_is_foundation_error_subclass`
- `test_foundation_error_message_is_accessible`
- `test_exceptions_module_reexports_same_classes_as_errors_module`

### 7.6 `test_logger.py`

- `test_get_logger_returns_logger_named_after_module`
- `test_get_logger_output_format_matches_convention`
- `test_get_logger_does_not_duplicate_handlers_on_repeated_calls`
- `test_get_logger_default_level_is_info`

### 7.7 `test_validation.py`

- `test_require_not_none_passes_for_non_none_value`
- `test_require_not_none_raises_validation_error_for_none`
- `test_require_non_empty_passes_for_non_empty_value`
- `test_require_non_empty_raises_validation_error_for_empty_string`
- `test_require_non_empty_raises_validation_error_for_empty_collection`
- `test_require_in_passes_for_allowed_value`
- `test_require_in_raises_validation_error_for_disallowed_value`
- `test_validate_returns_success_result_when_rule_passes`
- `test_validate_returns_failure_result_when_rule_fails`
- `test_validate_wraps_rule_exception_into_validation_error`

### 7.8 `test_version.py`

- `test_design_version_equals_v1_0`

### 7.9 `test_utils.py`

- `test_generate_id_returns_unique_string`
- `test_utc_now_returns_timezone_aware_datetime`

---

## 8. MVP範囲の明記

設計書 5.3節（重厚壮大化監査）にて対象外・削除済みとされた以下の機能は、本実装仕様の対象外とし、Foundationには実装しない。

- プラグインアーキテクチャ
- 動的Domain Model生成
- スキーマレジストリ
- 分散トレーシング基盤
- イベントソーシング基盤
- 汎用DIコンテナ

また、以下もFoundationの責務外（設計書2.2節・4.1節）であり、本仕様書の実装対象に含めない。

- Task状態の実管理（State Manager）
- Configuration値の実管理（Configuration Manager, M17）
- Knowledge本文の実管理（Knowledge Manager, M03）
- Workflow実行制御
- 外部サービスとの通信

Foundationは13種のDomain Model・`BaseModule`・`Result[T]`・`ConfigurationClient`・エラー階層・`get_logger`・バリデーション関数・`DESIGN_VERSION` の提供のみを実装範囲とする。
