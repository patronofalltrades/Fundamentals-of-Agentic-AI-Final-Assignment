"""Offline dashboard commands."""

import argparse
import json

from .backend import NeonHTTPBackend, SQLiteBackend
from .bundle import export_bundle, load_bundle
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
    analysis_target = analysis.add_mutually_exclusive_group(required=True)
    analysis_target.add_argument("--db", help="SQLite dashboard database")
    analysis_target.add_argument("--postgres-env", metavar="VAR", help="name of the env var holding the postgres:// URL")
    export = sub.add_parser("export-bundle", help="write rows.jsonl + manifest.json (no full review text)")
    export.add_argument("--db", required=True, help="dashboard SQLite copy made by import-checkpoint")
    export.add_argument("--out", required=True, help="new, empty bundle directory")
    load = sub.add_parser("load-bundle", help="idempotently load a bundle into SQLite or Postgres")
    load.add_argument("--bundle", required=True)
    target = load.add_mutually_exclusive_group(required=True)
    target.add_argument("--sqlite", help="SQLite file to create or update")
    target.add_argument("--postgres-env", metavar="VAR", help="name of the env var holding the postgres:// URL")
    grading = sub.add_parser("import-grading", help="check and load the pipeline's grading folder (ranking, claims, memo)")
    grading.add_argument("--folder", required=True, help="grading export folder")
    grading.add_argument("--issue-names", help="optional JSON file: {issue_id: display name}")
    grading.add_argument("--run-id", help="optional run ID (default: grading-<ranking.csv hash>)")
    grading_target = grading.add_mutually_exclusive_group(required=True)
    grading_target.add_argument("--db", help="SQLite dashboard database")
    grading_target.add_argument("--postgres-env", metavar="VAR", help="name of the env var holding the postgres:// URL")
    web = sub.add_parser("serve", help="serve a local read-only API and dashboard")
    web.add_argument("--db", required=True)
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.command == "import-checkpoint":
        print(json.dumps(import_checkpoint(args.source, args.db), sort_keys=True))
    elif args.command == "export-bundle":
        manifest = export_bundle(args.db, args.out)
        print(json.dumps({"counts": manifest["counts"], "rows_sha256": manifest["rows_sha256"]}, sort_keys=True))
    elif args.command == "load-bundle":
        import os
        if args.sqlite:
            backend = SQLiteBackend(args.sqlite, readonly=False)
        else:
            url = os.environ.get(args.postgres_env)
            if not url:
                parser.error("environment variable %s is not set" % args.postgres_env)
            backend = NeonHTTPBackend(url, timeout=60)
        with backend:
            print(json.dumps(load_bundle(backend, args.bundle), sort_keys=True))
    elif args.command == "import-grading":
        import os
        from .grading_import import load_grading
        names = None
        if args.issue_names:
            with open(args.issue_names, encoding="utf-8") as handle:
                names = json.load(handle)
        if args.db:
            backend = SQLiteBackend(args.db, readonly=False)
        else:
            url = os.environ.get(args.postgres_env)
            if not url:
                parser.error("environment variable %s is not set" % args.postgres_env)
            backend = NeonHTTPBackend(url, timeout=60)
        with backend:
            print(json.dumps(load_grading(backend, args.folder, names, args.run_id), sort_keys=True))
    elif args.command == "import-analysis":
        with open(args.input, encoding="utf-8") as handle:
            payload = json.load(handle)
        if args.db:
            print(json.dumps(import_analysis(args.db, payload), sort_keys=True))
        else:
            import os
            from .analysis import load_analysis
            url = os.environ.get(args.postgres_env)
            if not url:
                parser.error("environment variable %s is not set" % args.postgres_env)
            with NeonHTTPBackend(url, timeout=60) as backend:
                print(json.dumps(load_analysis(backend, payload), sort_keys=True))
    else:
        serve(args.db, args.host, args.port)


if __name__ == "__main__":
    main()
