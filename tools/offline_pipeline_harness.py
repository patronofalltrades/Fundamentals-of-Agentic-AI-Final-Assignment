"""No-network synthetic cold/warm orchestration check, not a business result."""

import json
import os
import tempfile
import time
from decimal import Decimal

from spotify_pipeline.db import Database
from spotify_pipeline.config import config_hash
from spotify_pipeline.ingest import ingest
from spotify_pipeline.jev_import import completed_items
from spotify_pipeline.jev import label_config
from spotify_pipeline.jev_pilot import PilotLedger, run_reviews
from tests.helpers import manifest_entry, write_csv, write_manifest
from tests.test_jev import fixture_response


def run_harness():
    rows = [
        ["synthetic-a", "Synthetic playback failure", "2", "0", "1.0", "2022-05-17 00:01:07"],
        ["synthetic-b", "Synthetic playback failure", "2", "0", "1.0", "2022-05-17 00:01:08"],
    ]
    calls = {"classify": 0, "evidence": 0, "verify": 0, "group": 0, "memo": 0}
    saved_handoffs = {}
    clock = time.monotonic

    def transport(_request, _key):
        calls["classify"] += 1
        return fixture_response()

    def evidence(text):
        calls["evidence"] += 1
        return {"entities": ["playback"], "evidence_quote": "playback failure"}

    def verify_blind(text):
        # This stub accepts only original text. It has no prediction argument.
        calls["verify"] += 1
        return "playback" if "playback" in text else "other"

    def group(items):
        calls["group"] += 1
        return {"issue-playback": [item for item in items if item["topic"] == "playback"]}

    def memo(ranked):
        calls["memo"] += 1
        return {"top_issue": ranked[0][0], "severity_sum": ranked[0][1]}

    with tempfile.TemporaryDirectory(prefix="spotify-synthetic-harness-") as folder:
        source = os.path.join(folder, "synthetic.csv")
        manifest = os.path.join(folder, "manifest.json")
        state = os.path.join(folder, "state.db")
        ledger_path = os.path.join(folder, "labels.db")
        write_csv(source, rows)
        write_manifest(manifest, {"synthetic.csv": manifest_entry(source)})
        phases = {}
        for phase in ("cold", "warm"):
            phase_start = clock()
            stage_times = {}
            before = dict(calls)

            def stage(name, action):
                started = clock()
                value = action()
                stage_times[name] = clock() - started
                return value

            if phase == "cold":
                stage("ingest", lambda: ingest(source, manifest, state,
                                               os.path.join(folder, "ingest-report.json")))
            else:
                stage_times["ingest"] = None  # Existing source state is reused.
            with Database(state) as db, PilotLedger(
                    ledger_path, db.get_meta("file_sha256"), Decimal("0.60")) as ledger:
                records = [db.get_record_by_review_id(row[0]) for row in rows]
                requests = [{"review_id": record["review_id"],
                             "review_text": record["review_text"],
                             "source_sha256": record["row_sha256"]} for record in records]
                stage("classify", lambda: run_reviews(requests, ledger, "synthetic-key",
                                                      transport=transport))

                def save_evidence():
                    for request in requests:
                        rid = request["review_id"]
                        if ledger.get_evidence(rid) is not None:
                            continue
                        result = ledger.conn.execute(
                            "SELECT cache_source_id FROM results WHERE review_id=?", (rid,)).fetchone()
                        origin = result["cache_source_id"]
                        if origin is None:
                            item = evidence(request["review_text"])
                        else:
                            saved = ledger.get_evidence(origin)
                            item = {"entities": json.loads(saved["entities_json"]),
                                    "evidence_quote": saved["evidence_quote"]}
                        ledger.save_evidence(rid, item, "synthetic-stub", "synthetic-v1", 0.0,
                                             cache_source_id=origin)

                stage("evidence", save_evidence)
                items = stage("handoff", lambda: completed_items(ledger, db, expected_count=2))
                def import_items():
                    direct = db.save_completed_batch([item for item in items if not item["is_cached"]])
                    cached = db.save_completed_batch([item for item in items if item["is_cached"]])
                    return direct, cached

                stage("import", import_items)
                verification = stage("verify", lambda: [verify_blind(row["review_text"])
                                                        for row in records] if phase == "cold"
                                     else saved_handoffs["verify"])
                if phase == "cold" and verification != [item["topic"] for item in items]:
                    raise AssertionError("synthetic verifier disagrees")
                groups = stage("group", lambda: group(items) if phase == "cold"
                               else saved_handoffs["group"])
                ranked = stage("rank", lambda: sorted(
                    ((issue, sum(item["severity"] for item in members))
                     for issue, members in groups.items()), key=lambda pair: (-pair[1], pair[0]))
                    if phase == "cold" else saved_handoffs["rank"])
                memo_result = stage("memo", lambda: memo(ranked) if phase == "cold"
                                    else saved_handoffs["memo"])
                if phase == "cold":
                    saved_handoffs.update({"verify": verification, "group": groups,
                                           "rank": ranked, "memo": memo_result})
                counts = db.status_counts(config_hash(label_config()))
            phases[phase] = {"wall_seconds": clock() - phase_start,
                             "stage_seconds": stage_times,
                             "stub_calls": {name: calls[name] - before[name] for name in calls},
                             "classifications": counts["completed"]}
        if any(phases["warm"]["stub_calls"].values()):
            raise AssertionError("warm pass made a stub inference call")
        return {"provenance": "synthetic_fixture", "network_calls": 0,
                "source_rows": 2, "phases": phases}


if __name__ == "__main__":
    print(json.dumps(run_harness(), indent=2))
