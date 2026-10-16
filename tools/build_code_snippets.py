"""Cut the dashboard's code snippets from the real source files.

Each snippet names a file, a function and, optionally, the first and last line
of an excerpt (by text, not by number), so the excerpt follows the code when
lines move. Highlight classes come from Python's own tokenizer.

Offline only. Reads repository source files; never reads data, local/ or answers.

    python3 -m tools.build_code_snippets          # write web/src/lib/code-snippets.json
    python3 -m tools.build_code_snippets --check  # fail if the file is out of date
"""
import argparse
import ast
import io
import json
import keyword
from pathlib import Path
import token
import tokenize

ROOT = Path(__file__).resolve().parents[1]
OUT = "web/src/lib/code-snippets.json"
REPO = "https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/blob/main/"
ALLOWED = ("spotify_pipeline/", "tools/", "dashboard/")
MAX_LINES = 40


def part(path, symbol, start=None, end=None, lead=0):
    """``start``/``end``: text of the excerpt's first and last lines. ``lead``: lines to show before ``start``."""
    return {"path": path, "symbol": symbol, "start": start, "end": end, "lead": lead}


# One entry per place on the site that says "code" does something.
SNIPPETS = {
    "parse-hash": {
        "title": "Parse and hash the exact fields",
        "caption": "Each selected row is read with a strict CSV reader. Its exact fields are hashed, and a repeated ID stops the run.",
        "parts": [part("tools/scale100k_manifest.py", "build", 'with source.open(encoding="utf-8-sig"', '"text_sha256": text_sha256')],
    },
    "exact-cache": {
        "title": "Configuration-safe exact-text cache",
        "caption": "A saved label or quote is reused only for byte-identical text under the same model, prompt and schema "
                   "hash. Every review ID keeps its own row.",
        "parts": [part("tools/scale100k_queue.py", "materialize_caches", "with db:")],
    },
    "label-validate": {
        "title": "Validate the labels",
        "caption": "Jev's answer is rejected if the model version, the question set, a label or the token usage is not exactly as expected.",
        "parts": [part("spotify_pipeline/jev.py", "parse_response")],
    },
    "evidence-check": {
        "title": "Check IDs, schema and source spans",
        "caption": "Every returned ID must be one that was sent, once. The quote must be an exact substring of the review; "
                   "a row that fails is quarantined with the reason.",
        "parts": [part("tools/scale100k_batch25.py", "inspect"),
                  part("spotify_pipeline/codex_evidence.py", "validate_evidence")],
    },
    "ledger": {
        "title": "Atomic shared ledger",
        "caption": "Before a call, the worst-case cost is reserved in one SQLite transaction. A repeated request key or a "
                   "cap breach stops the call. After the call, the measured charge settles the reservation.",
        "parts": [part("spotify_pipeline/project_budget.py", "ProjectBudget.reserve"),
                  part("spotify_pipeline/project_budget.py", "ProjectBudget.settle")],
    },
    "graceful-stop": {
        "title": "Bounded workers and graceful stop",
        "caption": "SIGINT or SIGTERM only sets a flag. Unsent requests are cancelled in the ledger, in-flight ones finish, "
                   "and a resume selects only IDs with no settled result.",
        "parts": [part("tools/scale100k_supervisor.py", "main", 'stop = {"requested": False}', "old_term = signal.signal"),
                  part("tools/scale100k_queue.py", "run_mixed", "# No transport worker owns this request yet",
                       "stop, halt = True", lead=1),
                  part("tools/scale100k_queue.py", "pending")],
    },
    "complaint-frame": {
        "title": "Build the complaint and cancellation frame",
        "caption": "The seven declared human corrections are applied and checked. Only complaints and cancellations stay, "
                   "and the frame must hold exactly 30,400 rows.",
        "parts": [part("tools/grouping_v4.py", "build", 'for original in frame["rows"]:', 'raise ValueError("corrected frame denominator differs")')],
    },
    "membership": {
        "title": "Validate membership",
        "caption": "Every saved assignment must name a catalog issue, and each review may appear once. The membership "
                   "must match the corrected frame exactly.",
        "parts": [part("tools/rebase_issue_membership_v4.py", "rebase")],
    },
    "rank": {
        "title": "Rank by severity sum",
        "caption": "priority_score is the severity sum. Issues sort by score, descending, then by issue ID.",
        "parts": [part("tools/issue_grouping_v4_rank.py", "rank.one_projection")],
    },
    "claim-check": {
        "title": "Check every numeric claim",
        "caption": "The export stops unless each claim ID appears in the memo with its saved value, and the memo cites no "
                   "unknown claim. The dashboard repeats the check before it shows the memo.",
        "parts": [part("tools/export_grouping_v4.py", "_claim_check"),
                  part("dashboard/grading_import.py", "memo_claim_check")],
    },
    "read-only-backend": {
        "title": "Read-only Python backend",
        "caption": "One handler serves both Vercel and the local server. Any method other than GET or HEAD gets HTTP 405.",
        "parts": [part("dashboard/server.py", "route", None, "return _api(conn, path, query)")],
    },
    "evaluator": {
        "title": "Isolated offline evaluator",
        "caption": "The evaluator runs offline after the predictions are frozen. It returns only aggregate scores, and "
                   "it refuses to overwrite an existing report.",
        "parts": [part("tools/evaluate_human_labels.py", "evaluate", "completed = {key: row", "sentiment_errors = ["),
                  part("tools/evaluate_human_labels.py", "main", "paths = [os.path.realpath", 'parser.exit(2,')],
    },
}


def find_symbol(tree, dotted):
    """The def or class node for a dotted name such as ``ProjectBudget.reserve`` or ``rank.one_projection``."""
    nodes = tree.body
    found = None
    for name in dotted.split("."):
        matches = [n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name]
        if len(matches) != 1:
            raise ValueError("expected one definition of %s" % dotted)
        found = matches[0]
        nodes = found.body
    return found


def _line_of(lines, first, last, text, unique):
    hits = [i for i in range(first, last + 1) if text in lines[i - 1]]
    if not hits or unique and len(hits) > 1:
        raise ValueError("anchor must match exactly once: %r" % text)
    return hits[0]


def classify(source):
    """Map (row, column) to a highlight class for keywords, names after def/class, strings, comments and numbers."""
    marks = {}
    previous = None
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        kind = None
        if tok.type == token.NAME and keyword.iskeyword(tok.string):
            kind = "const" if tok.string in ("True", "False", "None") else "kw"
        elif tok.type == token.NAME and previous is not None and previous.string in ("def", "class"):
            kind = "fn"
        elif tok.type == token.STRING:
            kind = "str"
        elif tok.type == token.COMMENT:
            kind = "com"
        elif tok.type == token.NUMBER:
            kind = "num"
        if kind:
            marks[tok.start] = (tok.end, kind)
        if tok.type not in (token.NL, token.NEWLINE, token.INDENT, token.DEDENT, tokenize.COMMENT):
            previous = tok
    return marks


def segments(lines, marks, first, last, indent):
    """Each line as a list of runs: a plain string, or [class, text]. Common indentation is removed."""
    per_line = {row: [""] * len(lines[row - 1]) for row in range(first, last + 1)}
    for (row, col), ((end_row, end_col), kind) in marks.items():
        for r in range(row, end_row + 1):
            if r in per_line:
                start = col if r == row else 0
                stop = end_col if r == end_row else len(lines[r - 1])
                for c in range(start, stop):
                    per_line[r][c] = kind
    out = []
    for row in range(first, last + 1):
        text, kinds = lines[row - 1][indent:], per_line[row][indent:]
        runs = []
        for ch, kind in zip(text, kinds):
            if runs and runs[-1][0] == kind:
                runs[-1][1] += ch
            else:
                runs.append([kind, ch])
        out.append([text if not kind else [kind, text] for kind, text in runs])
    return out


def cut(spec, cache):
    path = spec["path"]
    if not path.startswith(ALLOWED) or not path.endswith(".py"):
        raise ValueError("snippets come only from pipeline, tool and dashboard source: " + path)
    if path not in cache:
        source = (ROOT / path).read_text(encoding="utf-8")
        cache[path] = (source, source.splitlines(), ast.parse(source), classify(source))
    source, lines, tree, marks = cache[path]
    node = find_symbol(tree, spec["symbol"])
    first, last = node.lineno, node.end_lineno
    if spec["start"]:
        first = _line_of(lines, first, last, spec["start"], True) - spec["lead"]
    if spec["end"]:
        last = _line_of(lines, first, last, spec["end"], False)
    while last > first and not lines[last - 1].strip():
        last -= 1
    if last - first + 1 > MAX_LINES:
        raise ValueError("snippet longer than %d lines: %s %s" % (MAX_LINES, path, spec["symbol"]))
    body = [lines[i - 1] for i in range(first, last + 1)]
    indent = min(len(l) - len(l.lstrip(" ")) for l in body if l.strip())
    return {"path": path, "symbol": spec["symbol"], "first_line": first, "last_line": last,
            "url": "%s%s#L%d-L%d" % (REPO, path, first, last),
            "lines": segments(lines, marks, first, last, indent)}


def build():
    cache = {}
    snippets = {}
    for key, entry in SNIPPETS.items():
        snippets[key] = {"title": entry["title"], "caption": entry["caption"],
                         "parts": [cut(p, cache) for p in entry["parts"]]}
    return {"version": 1, "note": "Generated by tools/build_code_snippets.py from the repository source. Do not edit.",
            "snippets": snippets}


def render():
    """One compact line per snippet, so a code change shows as a one-line diff."""
    data = build()
    rows = ",\n".join("  %s: %s" % (json.dumps(k), json.dumps(v, ensure_ascii=False, separators=(",", ":")))
                      for k, v in data["snippets"].items())
    return '{"version": %d, "note": %s, "snippets": {\n%s\n}}\n' % (data["version"], json.dumps(data["note"]), rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="fail if the saved snippets differ from the source")
    args = parser.parse_args(argv)
    target = ROOT / OUT
    rendered = render()
    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != rendered:
            raise SystemExit("code snippets are out of date; run python3 -m tools.build_code_snippets")
        print(OUT + " is current")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    print("wrote %s (%d snippets)" % (OUT, len(SNIPPETS)))
    return 0


if __name__ == "__main__":
    main()
