"""The dashboard's code snippets must be exact, current excerpts of the repository source."""
import json
import textwrap
import unittest

from tools import build_code_snippets as snippets


def text(line):
    return "".join(run if isinstance(run, str) else run[1] for run in line)


class CodeSnippetTests(unittest.TestCase):
    def test_saved_file_is_current(self):
        saved = (snippets.ROOT / snippets.OUT).read_text(encoding="utf-8")
        self.assertEqual(saved, snippets.render(), "run python3 -m tools.build_code_snippets")

    def test_every_excerpt_matches_its_source_lines(self):
        data = json.loads((snippets.ROOT / snippets.OUT).read_text(encoding="utf-8"))["snippets"]
        self.assertEqual(set(data), set(snippets.SNIPPETS))
        for key, entry in data.items():
            for part in entry["parts"]:
                source = (snippets.ROOT / part["path"]).read_text(encoding="utf-8").splitlines()
                expected = textwrap.dedent("\n".join(source[part["first_line"] - 1:part["last_line"]]))
                self.assertEqual("\n".join(text(line) for line in part["lines"]), expected, key)
                self.assertTrue(part["url"].endswith("%s#L%d-L%d" % (part["path"], part["first_line"], part["last_line"])))
                self.assertLessEqual(len(part["lines"]), snippets.MAX_LINES)

    def test_highlighting_marks_keywords_and_definitions(self):
        lines = snippets.build()["snippets"]["rank"]["parts"][0]["lines"]
        self.assertEqual(lines[0][:3], [["kw", "def"], " ", ["fn", "one_projection"]])

    def test_ambiguous_anchor_and_foreign_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly once"):
            snippets.cut(snippets.part("tools/scale100k_queue.py", "run_mixed", "stop_requested()"), {})
        for path in ("local/private.py", "reports/x.py", "README.md"):
            with self.assertRaisesRegex(ValueError, "only from"):
                snippets.cut(snippets.part(path, "main"), {})


if __name__ == "__main__":
    unittest.main()
