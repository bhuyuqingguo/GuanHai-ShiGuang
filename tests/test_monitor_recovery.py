import unittest

from optical_desk.monitor_utils import primary_rect, window_has_visible_monitor


class MonitorRecoveryTests(unittest.TestCase):
    def test_negative_secondary_monitor_is_valid(self):
        rects = [(-1920, 0, 0, 1080), (0, 0, 2560, 1440)]
        self.assertTrue(window_has_visible_monitor(rects, -1500, 200, 420, 800))

    def test_unplugged_secondary_becomes_invisible(self):
        primary = [(0, 0, 2560, 1440)]
        self.assertFalse(window_has_visible_monitor(primary, -1500, 200, 420, 800))
        self.assertEqual(primary_rect(primary), primary[0])

    def test_partially_visible_window_keeps_position(self):
        rects = [(0, 0, 1920, 1080), (1920, 0, 3840, 1080)]
        self.assertTrue(window_has_visible_monitor(rects, 1800, 50, 420, 800))


if __name__ == "__main__":
    unittest.main()
