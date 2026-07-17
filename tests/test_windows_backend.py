import sys
import unittest
from unittest.mock import patch

from vitapad.backends.windows import WindowsGamepad, _axis


class WindowsAxisTests(unittest.TestCase):
    def test_constructor_reports_missing_vgamepad(self) -> None:
        with patch.dict(sys.modules, {"vgamepad": None}):
            with self.assertRaisesRegex(RuntimeError, "需要 vgamepad"):
                WindowsGamepad()

    def test_normal_axis_endpoints(self) -> None:
        self.assertEqual(_axis(0), -32768)
        self.assertEqual(_axis(128), 0)
        self.assertEqual(_axis(255), 32767)

    def test_inverted_axis_endpoints_do_not_overflow(self) -> None:
        self.assertEqual(_axis(0, invert=True), 32767)
        self.assertEqual(_axis(128, invert=True), 0)
        self.assertEqual(_axis(255, invert=True), -32768)

    def test_all_axis_values_stay_in_xinput_range(self) -> None:
        for value in range(256):
            self.assertGreaterEqual(_axis(value, invert=True), -32768)
            self.assertLessEqual(_axis(value, invert=True), 32767)


if __name__ == "__main__":
    unittest.main()
