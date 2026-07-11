"""F01 共通Domain Model(設計書3.3節)。

Foundationが保証するのは各Domainの共通属性(id/created_at/updated_at/metadata)の
型・命名規約のみであり、モジュール固有の属性はここに追加しない(各モジュールの
実装仕様書側でこれらを継承・拡張する)。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from foundation.utils import generate_id, utc_now


@dataclass
class _DomainBase:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task(_DomainBase):
    pass


@dataclass
class SubTask(_DomainBase):
    pass


@dataclass
class Workflow(_DomainBase):
    pass


@dataclass
class Design(_DomainBase):
    pass


@dataclass
class Implementation(_DomainBase):
    pass


@dataclass
class TestResult(_DomainBase):
    pass


@dataclass
class PullRequest(_DomainBase):
    pass


@dataclass
class Review(_DomainBase):
    pass


@dataclass
class Knowledge(_DomainBase):
    pass


@dataclass
class Context(_DomainBase):
    pass


@dataclass
class Configuration(_DomainBase):
    pass


@dataclass
class Notification(_DomainBase):
    pass


@dataclass
class CommunicationMessage(_DomainBase):
    pass


@dataclass
class Repository(_DomainBase):
    pass
