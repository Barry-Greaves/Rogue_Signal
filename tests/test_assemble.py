"""Offline checks for assemble.py; builds commands without running FFmpeg."""
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assemble


class ScheduleTests(unittest.TestCase):
    def test_panels_spread_evenly_without_times(self):
        s = assemble.panel_schedule(["a.png", "b.png", "c.png"], 45.0)
        self.assertEqual([(p, st, en) for p, st, en in s],
                         [("a.png", 0.0, 15.0), ("b.png", 15.0, 30.0), ("c.png", 30.0, 45.0)])

    def test_explicit_times_and_windows_paths(self):
        s = assemble.panel_schedule([r"C:\x\a.png@0", "b.png@7.5", "c.png@30"], 45.0)
        self.assertEqual(s[0][0], r"C:\x\a.png")
        self.assertEqual([(st, en) for _, st, en in s], [(0.0, 7.5), (7.5, 30.0), (30.0, 45.0)])

    def test_bad_schedules_are_rejected(self):
        for specs in (["a@5"], ["a@0", "b@20", "c@10"], ["a@0", "b@50"]):
            with self.assertRaises(ValueError):
                assemble.panel_schedule(specs, 45.0)


class BuildTests(unittest.TestCase):
    def args(self, tmp, layout, n, **extra):
        clips = []
        for i in range(n):
            p = Path(tmp) / f"c{i}.mp4"
            p.write_bytes(b"")
            clips.append(str(p))
        base = dict(layout=layout, clips=clips, out=str(Path(tmp) / "out.mp4"), clip_seconds=15.0,
                    crop_y=0, panels=None, top_height=1080, panel_scale=0.85, panel_x=0,
                    panel_top=40, bg="0x101517")
        base.update(extra)
        return SimpleNamespace(**base)

    def test_three_clips_make_45_seconds_full_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmd, _, total = assemble.build(self.args(tmp, "full", 3))
            graph = cmd[cmd.index("-filter_complex") + 1]
            self.assertEqual(total, 45.0)
            self.assertIn("concat=n=3:v=1:a=1", graph)
            self.assertIn("scale=1080:1920", graph)

    def test_split_stacks_presenter_over_panels(self):
        with tempfile.TemporaryDirectory() as tmp:
            panels = [str(Path(tmp) / f"p{i}.png") for i in range(6)]
            cmd, _, total = assemble.build(self.args(tmp, "split", 3, panels=panels))
            graph = cmd[cmd.index("-filter_complex") + 1]
            self.assertEqual(total, 45.0)
            self.assertIn("scale=1080:1080", graph)      # presenter panel
            self.assertIn("pad=1080:840", graph)         # article panel
            self.assertIn("concat=n=6:v=1:a=0[art]", graph)
            self.assertIn("vstack", graph)
            self.assertEqual(cmd.count("-loop"), 6)


if __name__ == "__main__":
    unittest.main()
