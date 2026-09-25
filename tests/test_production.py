"""Offline checks for presenter.py and verify_speech.py; no ComfyUI or Whisper needed."""
from pathlib import Path
import array
import math
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import presenter
import verify_speech


class PresenterGraphTests(unittest.TestCase):
    def spec(self, **extra):
        return {**presenter.DEFAULTS, "name": "t", "seconds": 15, "prompt": "Say: \"{line}\"", "line": "Hi.", **extra}

    def test_frames_follow_h3_grid_and_never_shorten(self):
        for seconds in (1, 5, 8, 15):
            frames = presenter.frames_for(seconds)
            self.assertEqual((frames - 5) % 17, 0)
            self.assertGreaterEqual(frames, seconds * presenter.FPS)
        self.assertEqual(presenter.frames_for(15), 362)
        self.assertEqual(presenter.frames_for(8), 192)

    def test_route_a_graph_anchors_image_without_audio(self):
        graph, length = presenter.build_graph(self.spec(), "img.png")
        self.assertEqual(length, 362)
        self.assertEqual(graph["r2v"]["inputs"]["prompt"], "Say: \"Hi.\"")
        self.assertEqual(graph["guide"]["inputs"]["image"], ["img", 0])
        self.assertNotIn("audio", graph["guide"]["inputs"])
        self.assertNotIn("ref_audios.ref_audio_0", graph["r2v"]["inputs"])
        self.assertEqual(graph["sigmas"]["inputs"]["steps"], 4)
        self.assertEqual(graph["guider"]["inputs"]["model"], ["lora", 0])

    def test_spoken_respelling_only_changes_the_prompt(self):
        spec = self.spec(line="Anthropic calls it ART.", spoken="Anthropic calls it Art.")
        graph, _ = presenter.build_graph(spec, "img.png")
        self.assertEqual(graph["r2v"]["inputs"]["prompt"], "Say: \"Anthropic calls it Art.\"")
        self.assertEqual(spec["line"], "Anthropic calls it ART.")

    def test_narration_and_voice_reference_are_wired_separately(self):
        graph, _ = presenter.build_graph(self.spec(turbo=False), "img.png", "narr.wav", "voice.wav")
        self.assertEqual(graph["guide"]["inputs"]["audio"], ["narr", 0])
        self.assertEqual(graph["r2v"]["inputs"]["ref_audios.ref_audio_0"], ["voice", 0])
        self.assertNotIn("lora", graph)
        self.assertEqual(graph["sigmas"]["inputs"]["steps"], 20)

    def test_every_link_points_to_an_existing_node(self):
        graph, _ = presenter.build_graph(self.spec(), "img.png", "narr.wav", "voice.wav")
        for node in graph.values():
            for value in node["inputs"].values():
                if isinstance(value, list):
                    self.assertIn(value[0], graph)


class SpeechCheckTests(unittest.TestCase):
    def test_numbers_compare_as_words(self):
        self.assertEqual(verify_speech.words("30 seconds"), verify_speech.words("thirty seconds"))
        self.assertEqual(verify_speech.words("I'm 21"), ["i'm", "twenty", "one"])

    def test_repeat_and_substitution_are_reported(self):
        expected = verify_speech.words("This is a test.")
        edits, rate = verify_speech.compare(expected, verify_speech.words("This is a test. This is a test."))
        self.assertEqual(edits[0]["op"], "insert")
        self.assertEqual(rate, 1.0)
        edits, _ = verify_speech.compare(expected, verify_speech.words("This is the test"))
        self.assertEqual(edits, [{"op": "replace", "expected": "a", "heard": "the"}])

    def test_loud_audio_after_last_word_is_flagged(self):
        rate = 16000
        tone = [int(12000 * math.sin(2 * math.pi * 220 * i / rate)) for i in range(rate)]
        samples = array.array("h", [0] * rate * 2 + tone)  # 2 s silence, then 1 s of loud audio
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.wav"
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(samples.tobytes())
            self.assertTrue(verify_speech.loud_after(path, 0.5))
            self.assertFalse(verify_speech.loud_after(path, 3.0))


if __name__ == "__main__":
    unittest.main()
