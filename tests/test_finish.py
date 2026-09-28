"""Offline checks for finish.py's filter graph; no FFmpeg needed."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import finish


class FinishFilterTests(unittest.TestCase):
    def test_blend_weights_and_size(self):
        g = finish.filter_graph(0.6, (1080, 1080))
        self.assertIn("blend=all_expr='A*0.6+B*0.40'", g)
        self.assertIn("scale=1080:1080:flags=lanczos", g)

    def test_grade_and_room_are_applied(self):
        g = finish.filter_graph(0.6, (1080, 1080))
        self.assertIn(finish.GRADE, g)
        self.assertIn(finish.ROOM, g)
        self.assertTrue(g.endswith("[a]"))


if __name__ == "__main__":
    unittest.main()
