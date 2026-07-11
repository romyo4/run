"""M16 Monitoring 固有の例外定義(IS16 5章)。

Foundationのエラー階層(FoundationError基底)をそのまま利用し、
Monitoring固有の新しい基底例外は追加しない。
"""

from foundation.errors import ExternalServiceError, NotFoundError, ValidationError


class UnknownMonitoredModuleError(NotFoundError):
    """health_check()/check_module() に未知の MonitoredModuleName が渡された場合。"""


class MetricsCollectionError(ExternalServiceError):
    """監視対象Moduleからの状態取得に失敗した場合(モジュール境界を越えた取得の失敗)。"""


class InvalidSystemStatusError(ValidationError):
    """collect() へ渡された SystemStatus が不正な場合(必須項目欠落等)。"""
