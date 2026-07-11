"""GitHub Manager内部でのみ使用する軽量な定数(IS20仕様書2章)。

GitHub Enterprise対応(ベースURL可変化)はMVP対象外のため、ベースURLは固定値とする
(IS20仕様書4.1節・8章)。業務定数・環境設定値はここに置かない(Configuration Managerの責務)。
"""

from __future__ import annotations

GITHUB_API_BASE_URL = "https://api.github.com"
DEFAULT_TIMEOUT_SECONDS = 10.0
