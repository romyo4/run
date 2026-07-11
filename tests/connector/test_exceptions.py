"""exceptions.py(IS21 5節)に対するテスト(IS21 7.5)。"""

import unittest

from connector.exceptions import (
    DiscordApiError,
    EventParseError,
    SlackApiError,
    UnsupportedPlatformError,
)
from foundation.errors import ExternalServiceError, ValidationError


class ConnectorExceptionsTest(unittest.TestCase):
    def test_slack_api_error_is_external_service_error_subclass(self) -> None:
        self.assertTrue(issubclass(SlackApiError, ExternalServiceError))
        error = SlackApiError("boom")
        self.assertEqual(error.message, "boom")

    def test_discord_api_error_is_external_service_error_subclass(self) -> None:
        self.assertTrue(issubclass(DiscordApiError, ExternalServiceError))
        error = DiscordApiError("boom")
        self.assertEqual(error.message, "boom")

    def test_unsupported_platform_error_is_validation_error_subclass(self) -> None:
        self.assertTrue(issubclass(UnsupportedPlatformError, ValidationError))
        error = UnsupportedPlatformError("unsupported")
        self.assertEqual(error.message, "unsupported")

    def test_event_parse_error_is_validation_error_subclass(self) -> None:
        self.assertTrue(issubclass(EventParseError, ValidationError))
        error = EventParseError("cannot parse")
        self.assertEqual(error.message, "cannot parse")


if __name__ == "__main__":
    unittest.main()
