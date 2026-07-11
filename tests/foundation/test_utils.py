import unittest
from datetime import datetime

from foundation.utils import generate_id, utc_now


class UtilsTest(unittest.TestCase):
    def test_generate_id_returns_unique_string(self) -> None:
        self.assertIsInstance(generate_id(), str)
        self.assertNotEqual(generate_id(), generate_id())

    def test_utc_now_returns_timezone_aware_datetime(self) -> None:
        now = utc_now()
        self.assertIsInstance(now, datetime)
        self.assertIsNotNone(now.tzinfo)


if __name__ == "__main__":
    unittest.main()
