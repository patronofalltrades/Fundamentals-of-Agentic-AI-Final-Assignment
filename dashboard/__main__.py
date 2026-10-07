"""Offline dashboard commands."""

import argparse
import json

from .server import serve
from .store import import_analysis, import_checkpoint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    copy = sub.add_parser("import-checkpoint", help="copy a complete canonical DB into private dashboard state")
    copy.add_argument("--source", required=True)
    copy.add_argument("--db", required=True)
    analysis = sub.add_parser("import-analysis", help="save accepted issue membership and draft recommendation")
    analysis.add_argument("--input", required=True)
    analysis.add_argument("--db", required=True)
    web = sub.add_parser("serve", help="serve a local read-only API and dashboard")
    web.add_argument("--db", required=True)
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.command == "import-checkpoint":
        print(json.dumps(import_checkpoint(args.source, args.db), sort_keys=True))
    elif args.command == "import-analysis":
        with open(args.input, encoding="utf-8") as handle:
            payload = json.load(handle)
        print(json.dumps(import_analysis(args.db, payload), sort_keys=True))
    else:
        serve(args.db, args.host, args.port)


if __name__ == "__main__":
    main()
