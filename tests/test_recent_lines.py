import tempfile
import unittest
from pathlib import Path

from poly_strategy.recent_lines import read_recent_lines


class RecentLinesTests(unittest.TestCase):
    def test_read_recent_lines_returns_tail_without_trailing_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.ndjson"
            path.write_text("a\nb\nc")

            self.assertEqual(read_recent_lines(path, max_lines=2, chunk_size=2), ["b", "c"])

    def test_read_recent_lines_validates_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.ndjson"
            path.write_text("a\n")

            with self.assertRaises(ValueError):
                read_recent_lines(path, max_lines=0)
            with self.assertRaises(ValueError):
                read_recent_lines(path, chunk_size=0)
