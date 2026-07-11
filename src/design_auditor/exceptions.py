"""Design Auditor (M08) 固有の例外方針(IS08 5章)。

IS08 5章の方針により、Foundationのエラー階層(`foundation.errors`の`FoundationError`
を頂点とする階層)をそのまま利用し、本モジュール独自の新規基底例外は追加しない
(design/M08 Design Auditor.txt 4.4「監査基準固定」= 独自ルール追加禁止の趣旨に合わせ、
独自例外体系も追加しない)。

呼び出し元は本モジュールの公開関数・メソッドが送出しうる例外として
`foundation.errors.ValidationError` / `NotFoundError` / `ConfigurationError` を想定し、
必要であれば `foundation.errors` から直接importすること。本モジュールはこれらを
再エクスポートしない(実体はFoundation側に一本化する)。
"""

from __future__ import annotations
