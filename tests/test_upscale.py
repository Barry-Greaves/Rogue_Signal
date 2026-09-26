"""Offline checks for upscale.py's graph; no ComfyUI needed."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import upscale


class UpscaleGraphTests(unittest.TestCase):
    def test_graph_is_connected_and_scales_by_multiplier(self):
        g = upscale.build_graph("src.mp4", 1.6875, 1, "lab", "ep-up")
        for node in g.values():
            for value in node["inputs"].values():
                if isinstance(value, list):
                    self.assertIn(value[0], g)
        self.assertEqual(g["resize"]["inputs"]["resize_type"], "scale by multiplier")
        self.assertEqual(g["resize"]["inputs"]["resize_type.multiplier"], 1.6875)
        self.assertEqual(g["save"]["inputs"]["filename_prefix"], "rogue_signal/ep-up")
        # Audio and fps come from the source clip, so the approved performance is kept.
        self.assertEqual(g["video"]["inputs"]["audio"], ["parts", 1])
        self.assertEqual(g["video"]["inputs"]["fps"], ["parts", 2])


if __name__ == "__main__":
    unittest.main()
