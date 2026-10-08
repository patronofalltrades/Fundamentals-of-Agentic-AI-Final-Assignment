"""Recover uniquely identified exact-span rows from saved, charged malformed batches.

This command performs no provider request and never changes reservation charges.
Only run it after every in-flight request has settled.
"""

import argparse
from collections import Counter
import json

from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.errors import ValidationError
from spotify_pipeline.project_budget import ProjectBudget
from tools import deepinfra_recheck100 as recheck
from tools.checkpoint5000_dispatch import legacy_paths
from tools.next5000_checkpoint import BUDGET, aliases, canonical, evidence_config


def recover(db):
    if db.execute("SELECT 1 FROM reservations WHERE status='reserved' LIMIT 1").fetchone():
        raise ValueError("active request; offline recovery deferred")
    total = {"batches": 0, "new_accepted": 0, "remaining_quarantined": 0}
    batches = list(db.execute("""SELECT q.request_key,q.response_json,q.config_sha,
        r.charged_nusd,r.status FROM next5000_requests q JOIN reservations r
        USING(request_key) WHERE q.status='quarantined_metered'"""))
    for key, raw, config, charged, reservation_status in batches:
        if not raw or reservation_status != "quarantined_metered" or charged is None:
            raise ValueError("metered malformed batch lacks saved response or charge")
        rows = {rid: (text, source_sha) for rid, text, source_sha in db.execute("""SELECT
            r.review_id,r.review_text,r.source_sha FROM next5000_rows r JOIN
            next5000_members m USING(review_id) WHERE m.request_key=?""", (key,))}
        if len(rows) != recheck.BATCH_SIZE or config != evidence_config(list(rows)):
            raise ValueError("saved malformed batch membership or config differs")
        response = json.loads(raw)
        if recheck.measured_usage(response)[-1] != charged:
            raise ValueError("saved response charge differs from settled ledger")
        if response["choices"][0].get("finish_reason") != "stop":
            raise ValueError("saved malformed batch did not finish normally")
        body = json.loads(response["choices"][0]["message"]["content"])
        items = body.get("results") if isinstance(body, dict) else None
        if not isinstance(items, list) or len(items) != recheck.BATCH_SIZE:
            raise ValueError("saved malformed result count differs")
        counts = Counter(item.get("review_id") for item in items if isinstance(item, dict))
        accepted = {}
        for item in items:
            if not isinstance(item, dict) or set(item) != {"review_id", "entities", "evidence_quote"}:
                continue
            rid = item["review_id"]
            if not isinstance(rid, str) or rid not in rows or counts[rid] != 1:
                continue
            try:
                accepted[rid] = validate_evidence(rows[rid][0],
                    {"entities": item["entities"], "evidence_quote": item["evidence_quote"]})
            except ValidationError:
                continue
        with db:
            for rid, value in accepted.items():
                if db.execute("SELECT 1 FROM next5000_evidence WHERE review_id=?", (rid,)).fetchone():
                    continue
                if db.execute("DELETE FROM next5000_quarantines WHERE review_id=? AND request_key=?",
                        (rid, key)).rowcount != 1:
                    raise ValueError("recoverable row is not directly quarantined")
                db.execute("INSERT INTO next5000_evidence VALUES (?,?,?,?,?,?,?)",
                    (rid, canonical(value["entities"]), value["evidence_quote"], config,
                     "deepinfra_offline_recovery", None, key))
                aliases(db, "evidence", rows[rid][0], value, rid, config)
                total["new_accepted"] += 1
        total["batches"] += 1
        total["remaining_quarantined"] += db.execute("""SELECT COUNT(*) FROM
            next5000_quarantines WHERE request_key=?""", (key,)).fetchone()[0]
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.parse_args()
    with ProjectBudget(BUDGET, legacy_paths()) as budget:
        print(canonical(recover(budget.db)))


if __name__ == "__main__":
    main()
