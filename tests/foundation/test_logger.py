import logging
import unittest

from foundation.constants import LOG_FORMAT
from foundation.logger import get_logger


class LoggerTest(unittest.TestCase):
    def test_get_logger_returns_logger_named_after_module(self) -> None:
        logger = get_logger("test_module_name")
        self.assertEqual(logger.name, "test_module_name")

    def test_get_logger_output_format_matches_convention(self) -> None:
        logger = get_logger("test_module_format")
        formatter = logger.handlers[0].formatter
        self.assertEqual(formatter._fmt, LOG_FORMAT)

    def test_get_logger_does_not_duplicate_handlers_on_repeated_calls(self) -> None:
        logger_first = get_logger("test_module_dup")
        logger_second = get_logger("test_module_dup")
        self.assertIs(logger_first, logger_second)
        self.assertEqual(len(logger_second.handlers), 1)

    def test_get_logger_default_level_is_info(self) -> None:
        logger = get_logger("test_module_level")
        self.assertEqual(logger.level, logging.INFO)


if __name__ == "__main__":
    unittest.main()
