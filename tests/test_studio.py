from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import studio


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)
        self.record = {"title": "Test", "url": "https://example.com/a", "published_at": self.now.isoformat()}

    def test_recency_future_invalid_and_deduplication(self):
        records = [self.record, {**self.record, "url": self.record["url"] + "#section"}]
        for delta in (-25, 1):
            records.append({**self.record, "url": f"https://example.com/{delta}",
                            "published_at": (self.now + timedelta(hours=delta)).isoformat()})
        records.append({**self.record, "published_at": "bad"})
        self.assertEqual(len(studio.select(records, self.now)), 1)

    def test_rss_and_atom(self):
        rss = b'<rss><channel><item><title>A</title><link>https://example.com/a</link><pubDate>Thu, 24 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>'
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>A</title><link href="https://example.com/a"/><published>2026-09-24T10:00:00Z</published></entry></feed>'
        for raw in (rss, atom):
            self.assertEqual(len(studio.select(studio.parse_feed(raw), self.now)), 1)

    def test_api_graph_rejects_ui_export(self):
        with self.assertRaises(ValueError):
            studio.validate_graph({"nodes": []})
        studio.validate_graph({"1": {"class_type": "Test", "inputs": {}}})

    def test_demo_has_no_network_and_marks_artifacts(self):
        with tempfile.TemporaryDirectory() as temp, patch("studio.request", side_effect=AssertionError("Network forbidden")):
            folder = Path(temp)
            studio.draft(studio.select([self.record], self.now), folder, demo=True)
            self.assertIn("FICTIONAL", (folder / "script.md").read_text())
            self.assertEqual(json.loads((folder / "youtube-draft.json").read_text())["upload_status"], "not_implemented")

    def test_empty_draft_fails(self):
        with self.assertRaises(ValueError):
            studio.draft([], Path("unused"))

    def test_provider_parsing_and_truncation(self):
        with patch.dict("os.environ", {"AI_MODEL": "test", "OPENAI_API_KEY": "dummy"}), patch("studio.request") as req:
            req.return_value = json.dumps({"status": "completed", "output": [{"content": [{"type": "output_text", "text": "Draft"}]}]}).encode()
            self.assertEqual(studio.generate([self.record], "openai"), "Draft")
            req.return_value = b'{"status":"incomplete"}'
            with self.assertRaises(ValueError):
                studio.generate([self.record], "openai")
        with patch.dict("os.environ", {"AI_MODEL": "test", "ANTHROPIC_API_KEY": "dummy"}), patch("studio.request", return_value=b'{"stop_reason":"end_turn","content":[{"type":"text","text":"Draft"}]}'):
            self.assertEqual(studio.generate([self.record], "claude"), "Draft")


if __name__ == "__main__":
    unittest.main()
