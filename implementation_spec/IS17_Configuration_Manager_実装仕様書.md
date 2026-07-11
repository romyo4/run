# IS17 Configuration Manager 実装仕様書

本書は `M17 Configuration Manager.txt`(確定済み詳細設計書、以下「設計書」)を唯一の正とし、`M00 Foundation.txt` が定義する共通基盤(F00〜F03、Result[T]、エラー階層、ログ規約)に整合する形で、Configuration Manager の実装仕様を定める。

設計書に明記のない機能は追加しない。5.3節「重厚壮大化監査」で対象外・削除済みとされた機能はMVP実装仕様に含めない。

---

## 1. モジュール概要

Configuration Manager は、AI Development Pipeline において System・GitHub・Slack・Discord・Codex・Fable・Monitoring の各設定を一元管理し、Configuration Files・Environment Variables・Startup Parameters を読み込んで検証したうえで、他の全モジュールへ一貫した設定値を提供する単一責務のモジュールである。本モジュールは Foundation(M00)が定義する `ConfigurationClient` インターフェース(F03)の唯一の実体(Single Source of Truth)を提供する立場にあり、設定値の読込・提供・検証・デフォルト値適用・バージョン管理のみを担当する。Secret の実体管理、Workflow管理、Knowledge管理、Context生成、権限判定は明確に責務外であり、通常運用時は設定値を変更しない Read Only なモジュールとして振る舞う。

---

## 2. ファイル構成

`src/configuration_manager/` 配下に以下を配置する。Foundation は `src/foundation/` に実装済みである前提とし、本モジュールはこれに依存する(逆方向の依存は持たない)。

```text
src/configuration_manager/
├── __init__.py            # 公開シンボルの再エクスポート(ConfigurationManager等)
├── domain.py               # 設定値のdataclass定義(F01 Configuration Domainを利用した具体構造)
├── constants.py             # 必須設定キー一覧・デフォルト値・環境変数プレフィックス等の定数
├── loader.py                # Configuration Files / Environment Variables / Startup Parametersの読込・マージ処理
├── validator.py              # 必須設定の検証ロジック(ValidationResult生成)
├── manager.py                # ConfigurationManager本体(BaseModule + ConfigurationClientの実装)
└── tests/
    ├── __init__.py
    ├── test_domain.py
    ├── test_loader.py
    ├── test_validator.py
    └── test_manager.py
```

役割の要点:

- `domain.py`: 設計書3.2/3.3の管理対象(System/GitHub/Slack/Discord/Codex/Fable/Monitoring)をdataclassとして定義し、Foundation `types.py` の `Configuration` Domain(id/created_at/updated_at/metadata)の具体属性として組み込む。
- `constants.py`: 設計書4.4の必須設定項目(GitHub Repository、Slack Channel、Codex Model 等)とデフォルト値、環境変数プレフィックスを定数化する。
- `loader.py`: 設計書3.1の入力(configuration_files / environment_variables / startup_parameters)を読み込み、優先順位に従いマージして `Configuration` を構築する。
- `validator.py`: 設計書4.4の起動時必須設定検証を行い `ValidationResult` を返す。
- `manager.py`: 設計書3.5の公開インターフェース(load/get/validate/reload)を実装し、Foundationの `BaseModule` と `ConfigurationClient` を継承・実装する。

---

## 3. データクラス定義

Foundation `types.py` の `Configuration` Domain(共通属性: `id: str`, `created_at: datetime`, `updated_at: datetime`, `metadata: dict[str, Any]`)を前提に、`configuration_manager/domain.py` にてモジュール固有属性を定義する。

```python
# src/configuration_manager/domain.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SystemConfig:
    system_name: str
    environment: str
    log_level: str
    timezone: str


@dataclass(frozen=True)
class GitHubConfig:
    repository: str
    default_branch: str
    organization: str


@dataclass(frozen=True)
class SlackConfig:
    workspace: str
    channel: str
    bot_name: str


@dataclass(frozen=True)
class DiscordConfig:
    server: str
    channel: str


@dataclass(frozen=True)
class CodexConfig:
    model: str
    timeout: int
    max_retry: int


@dataclass(frozen=True)
class FableConfig:
    review_schedule: str
    review_period: str


@dataclass(frozen=True)
class MonitoringConfig:
    health_interval: int
    warning_threshold: int


@dataclass(frozen=True)
class Configuration:
    """Foundation Configuration Domain(id/created_at/updated_at/metadata)の具体構造。"""

    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    version: str
    system: SystemConfig
    github: GitHubConfig
    slack: SlackConfig
    discord: DiscordConfig
    codex: CodexConfig
    fable: FableConfig
    monitoring: MonitoringConfig


@dataclass(frozen=True)
class ConfigurationSource:
    """load()/reload()の入力(設計書3.1: configuration_files/environment_variables/startup_parameters)。"""

    config_file_paths: tuple[Path, ...] = field(default_factory=tuple)
    environment_prefix: str = "APP_"
    startup_parameters: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ConfigurationVersion:
    """設計書3.4の成果物「Configuration Version」。"""

    version: str
    loaded_at: datetime


@dataclass(frozen=True)
class ValidationResult:
    """設計書3.4の成果物「Validation Result」。"""

    is_valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
```

補足:

- 各カテゴリ(`SystemConfig` 等)は設計書3.2の項目と一対一対応させ、それ以外の属性は追加しない。
- `Configuration` は Read Only 制約(設計書4.2)に従い `frozen=True` とし、通常運用時のインスタンス変更を型レベルで禁止する。設定変更は `reload()` による再構築のみで行う。
- Secret・Access Token・Password の実体は保持しない(設計書4.3)。GitHub/Slack/Codex等の各Configには参照先を表す文字列(例: リポジトリ名、チャンネル名、モデル名)のみを持たせ、Token等のフィールドは定義しない。

---

## 4. クラス・関数シグネチャ

### 4.1 Foundationとの関係

Foundation `interfaces.py` は F03 として以下を定義する(Foundation側の責務、本モジュールは変更しない)。

```python
# src/foundation/interfaces.py (参照のみ・Foundation側で定義済み)
class ConfigurationClient(ABC):
    @abstractmethod
    def get(self, module_name: str, key: str) -> Result[Any]: ...
```

Configuration Manager は `manager.py` にて `BaseModule` と `ConfigurationClient` の両方を実装し、`ConfigurationClient.get()` の唯一の実体を提供する。

### 4.2 manager.py

```python
# src/configuration_manager/manager.py
from __future__ import annotations

from typing import Any

from foundation.base_module import BaseModule
from foundation.interfaces import ConfigurationClient
from foundation.result import Result

from configuration_manager.domain import (
    Configuration,
    ConfigurationSource,
    ValidationResult,
)


class ConfigurationManager(BaseModule, ConfigurationClient):
    """設計書3.5の公開インターフェース(load/get/validate/reload)を実装する。"""

    def __init__(self, source: ConfigurationSource) -> None: ...

    # --- BaseModule (F02) ---
    def name(self) -> str: ...
    def health_check(self) -> Result[bool]: ...

    # --- 設計書3.5 公開インターフェース ---
    def load(self, source: ConfigurationSource) -> Result[Configuration]: ...
    def validate(self, configuration: Configuration) -> Result[ValidationResult]: ...
    def reload(self) -> Result[Configuration]: ...

    # --- ConfigurationClient (F03) の実装 ---
    def get(self, module_name: str, key: str) -> Result[Any]: ...
```

シグネチャの意図:

- `load(source)`: 設計書3.5「入力: Configuration Source / 出力: Configuration」。`loader.py` を用いて Configuration Files → Environment Variables → Startup Parameters の順に読み込み・マージし、`validate()` を内部で実行したうえで `Configuration` を構築する。読込・検証に失敗した場合は `Result(success=False, value=None, error=ConfigurationError(...))` を返す。
- `get(module_name, key)`: 設計書3.5「入力: Configuration Key / 出力: Configuration Value」を、F03 `ConfigurationClient.get(module_name, key) -> Result[Any]` のシグネチャで具体化する。`module_name`(例: `"github"`)に対応するカテゴリdataclassから `key`(例: `"repository"`)属性を取得する。未読込・未知のmodule_name・未知のkeyはいずれも `NotFoundError` を `Result.error` に格納して返す(例外送出はしない)。
- `validate(configuration)`: 設計書3.5「入力: Configuration / 出力: Validation Result」。`validator.py` の検証結果を `Result[ValidationResult]` として返す。検証自体が失敗する(想定外の入力等)場合のみ `Result.error` に `ValidationError` を格納する。必須項目が不足している場合は `Result.success=True` かつ `ValidationResult.is_valid=False` として返す(検証処理自体は正常に完了しているため)。起動可否の判断(設計書4.4「起動を中止する」)は呼び出し元(起動処理)が `ValidationResult.is_valid` を見て行う。Configuration Manager自身はプロセスを終了させない。
- `reload()`: 設計書3.5「入力: None / 出力: Updated Configuration」。`__init__` で保持した直近の `ConfigurationSource` を再利用して `load()` を再実行する。

### 4.3 loader.py

```python
# src/configuration_manager/loader.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from foundation.result import Result

from configuration_manager.domain import Configuration, ConfigurationSource


def load_from_files(config_file_paths: tuple[Path, ...]) -> Result[dict[str, Any]]: ...
def load_from_environment(environment_prefix: str) -> Result[dict[str, Any]]: ...
def merge_configuration_data(
    file_data: dict[str, Any],
    environment_data: dict[str, Any],
    startup_parameters: dict[str, str],
) -> dict[str, Any]: ...
def build_configuration(merged_data: dict[str, Any], version: str) -> Result[Configuration]: ...
```

- 設定ファイルはUTF-8のJSON形式を対象とする(標準ライブラリ`json`のみを使用し、外部パーサ依存を持ち込まない)。
- マージ優先順位は `startup_parameters > environment_variables > configuration_files` とする(設計書3.1の列挙順を「後勝ち上書き」の入力源として解釈)。
- ファイル未存在・JSON不正等は `Result(success=False, error=ConfigurationError(...))` として返し、例外は呼び出し境界(`manager.py`)より内側で吸収する。

### 4.4 validator.py

```python
# src/configuration_manager/validator.py
from __future__ import annotations

from foundation.result import Result

from configuration_manager.domain import Configuration, ValidationResult


def validate_configuration(configuration: Configuration) -> Result[ValidationResult]: ...
```

- 設計書4.4の必須設定(例: GitHub Repository、Slack Channel、Codex Model)が空文字・未設定の場合、`ValidationResult.errors` にキーごとの不足メッセージを蓄積し `is_valid=False` を返す。
- 検証対象キーは `constants.py` の `REQUIRED_CONFIGURATION_KEYS` に一覧化し、設計書に明記のないキーを検証対象に追加しない。

---

## 5. エラー処理

Foundation `errors.py` のエラー階層(`FoundationError` 基底、`ConfigurationError`・`NotFoundError`・`ValidationError` 等)をそのまま利用し、本モジュール独自の例外基底は新設しない(Foundation 4.2/4.3「新しい基底例外の追加はFoundation側でのみ行う」に従う)。

| 状況 | 使用するエラー型 | 返却方法 |
|---|---|---|
| 設定ファイルが存在しない/読込不能 | `ConfigurationError` | `Result(success=False, value=None, error=...)` |
| JSON構文不正 | `ConfigurationError` | 同上 |
| `get()` で未知の `module_name`/`key` | `NotFoundError` | 同上(例外は送出しない) |
| `validate()` の処理自体が実行不能(想定外の型混入等) | `ValidationError` | 同上 |
| 必須設定項目の不足(起動時検証) | なし(例外化しない) | `ValidationResult.is_valid=False` として正常応答 |

方針:

- Configuration Manager内部では例外を送出したまま呼び出し元へ伝播させず、`try/except` で捕捉して `Result` に変換する(呼び出し元は常に `Result[T]` のみを扱えばよい)。
- 「必須設定不足による起動中止」(設計書4.4)は例外・エラーではなく、`ValidationResult.is_valid=False` という正常な検証結果として表現する。起動処理側がこの結果を見て起動継続/中止を判断する。
- Secret・Access Token・Password はConfiguration Managerが実体を保持しないため(設計書4.3)、これらに起因するエラーは扱わない。

---

## 6. ロギング仕様

Foundation `logger.py` の `get_logger(module_name: str) -> Logger` を用い、モジュール名 `"configuration_manager"` でロガーを取得する。出力形式は Foundation規約 `timestamp | module_name | level | message` に従う(独自フォーマッタは実装しない)。

設計書4.5に基づき、以下の項目のみを記録する。

| ログ項目 | 記録タイミング | レベル |
|---|---|---|
| `configuration_version` | `load()`/`reload()` 成功時 | INFO |
| `validation_result`(is_valid真偽値のみ、エラー件数含めてよい) | `validate()` 実行時 | INFO(不正時はWARNING) |
| `reload_result`(成功/失敗) | `reload()` 実行時 | INFO(失敗時はERROR) |

厳守事項:

- 設定値そのもの(System/GitHub/Slack/Discord/Codex/Fable/Monitoringの各フィールド値)、Secret・Access Token・Passwordはログへ一切出力しない(設計書4.5)。
- `get(module_name, key)` の戻り値(Configuration Value)もログへ出力しない。ログに残すのは「取得を試みた」という事実(module_name/key名のみ)に留め、値は含めない。
- 例外捕捉時のログは、例外メッセージに設定値そのものが含まれないよう、キー名のみをメッセージに含める。

---

## 7. Unit Testケース一覧

`unittest` を使用し、`tests/` 配下にテストメソッド粒度で以下を実装する(pytestは使用しない)。

### `tests/test_domain.py`

- `test_configuration_is_frozen_and_raises_on_attribute_assignment`
- `test_configuration_source_defaults_to_empty_file_paths_and_parameters`
- `test_validation_result_defaults_to_empty_errors_tuple`

### `tests/test_loader.py`

- `test_load_from_files_reads_valid_json_configuration_file`
- `test_load_from_files_returns_error_result_when_file_missing`
- `test_load_from_files_returns_error_result_when_json_is_malformed`
- `test_load_from_environment_reads_variables_with_matching_prefix`
- `test_load_from_environment_ignores_variables_without_prefix`
- `test_merge_configuration_data_startup_parameters_override_environment_variables`
- `test_merge_configuration_data_environment_variables_override_file_values`
- `test_build_configuration_sets_version_and_timestamps`
- `test_build_configuration_returns_error_result_on_missing_category_data`

### `tests/test_validator.py`

- `test_validate_configuration_returns_valid_when_all_required_keys_present`
- `test_validate_configuration_flags_missing_github_repository`
- `test_validate_configuration_flags_missing_slack_channel`
- `test_validate_configuration_flags_missing_codex_model`
- `test_validate_configuration_collects_multiple_missing_keys_in_one_result`

### `tests/test_manager.py`

- `test_name_returns_configuration_manager`
- `test_health_check_returns_success_true_after_successful_load`
- `test_health_check_returns_success_false_before_first_load`
- `test_load_returns_success_result_containing_configuration`
- `test_load_returns_error_result_when_underlying_loader_fails`
- `test_get_returns_success_result_for_known_module_and_key`
- `test_get_returns_not_found_error_for_unknown_module_name`
- `test_get_returns_not_found_error_for_unknown_key`
- `test_get_returns_not_found_error_before_configuration_is_loaded`
- `test_validate_returns_validation_result_reflecting_missing_required_keys`
- `test_reload_rebuilds_configuration_from_original_source`
- `test_reload_returns_error_result_when_source_files_removed`
- `test_manager_does_not_include_configuration_values_in_log_output`
- `test_manager_logs_configuration_version_on_successful_load`

---

## 8. MVP範囲の明記

設計書5.3「重厚壮大化監査」にて対象外・削除済みとされた以下の機能は、本実装仕様に含めない。将来検討が必要になった場合も、本書ではなく設計書の改訂(バージョン更新)を経てから実装仕様へ反映する。

- Configuration Database
- Distributed Configuration
- Dynamic Configuration Push
- Feature Flag
- Multi Environment Configuration Server
- Remote Configuration Service
- Hot Configuration Synchronization
- Configuration Version Rollback

MVPで実装するのはローカル設定ファイル(JSON)・環境変数・起動パラメータの読込、検証、デフォルト値適用、`ConfigurationVersion` によるバージョン管理、および `ConfigurationClient` インターフェースの提供のみである。Secret実体管理・Workflow管理・Knowledge管理・Context生成・権限判定は本モジュールの責務外として実装しない(設計書2.2/4.3)。
