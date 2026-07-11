import unittest

from foundation.version import DESIGN_VERSION


class VersionTest(unittest.TestCase):
    def test_design_version_equals_v1_0(self) -> None:
        self.assertEqual(DESIGN_VERSION, "v1.0")


if __name__ == "__main__":
    unittest.main()
