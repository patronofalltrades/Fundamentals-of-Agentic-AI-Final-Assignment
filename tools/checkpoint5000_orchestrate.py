"""One foreground, resumable command for the approved 5,000-review checkpoint.

It has no daemon or startup hook. The paid --run mode uses the existing queue,
two-worker dispatcher and shared budget. It never prints or persists keys.
"""

import argparse
import html
import json
import re
import urllib.request

from spotify_pipeline import deepinfra_batch
from tools import deepinfra_batch10_canary as canary
from tools.checkpoint5000_dispatch import open_checkpoint, run_evidence, run_labels
from tools.checkpoint5000_qa import audit
from tools.checkpoint5000_qa_bundle import make_bundle

JEV_SERVICE = "spotify-review-jev"
JEV_ACCOUNT = "hanif-spotify-project"
JEV_MODELS_URL = "https://docs.typesafe.ai/models"


def verify_jev_price(fetch=urllib.request.urlopen):
    """Fail closed if the official pinned Jev price or model changes."""
    try:
        with fetch(JEV_MODELS_URL, timeout=10) as response:
            raw = response.read().decode("utf-8")
        plain = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw)).split())
    except Exception:
        raise ValueError("official Jev price page unavailable; no paid call") from None
    required = (r"Current models\s+Jev 1\.13\s+jev-1\.13\.0\s+"
                r"Price \(per Btok / per Mtok\)\s+\$42 / \$0\.042")
    if re.search(required, plain) is None:
        raise ValueError("pinned Jev price or model changed; no paid call")
    return {"model": "jev-1.13.0", "input_usd_per_million": "0.042",
            "source": JEV_MODELS_URL}


def qa_status(manifest_path, budget_path):
    bundle = make_bundle(manifest_path, budget_path)
    report, _ = audit(bundle, evidence_prompt=deepinfra_batch.PROMPT_VERSION,
                      sample_size=0)
    if not report["structurally_clean"]:
        raise ValueError("checkpoint QA found structural failures; no paid call")
    return {"accepted_rows": report["accepted_rows"],
            "quarantined_rows": report["counts_by_state"].get("quarantined", 0),
            "pending_rows": report["counts_by_state"].get("pending", 0),
            "uncertain_rows": report["counts_by_state"].get("uncertain", 0),
            "in_flight_rows": report["counts_by_state"].get("in_flight", 0)}


def run(args):
    budget, queue = open_checkpoint(args)
    try:
        first100 = queue.db.execute("""SELECT COUNT(*),
            SUM(l.review_id IS NOT NULL),SUM(e.review_id IS NOT NULL),
            SUM(q.review_id IS NOT NULL) FROM checkpoint_rows r
            LEFT JOIN checkpoint_labels l USING(review_id)
            LEFT JOIN checkpoint_evidence e USING(review_id)
            LEFT JOIN checkpoint_quarantines q USING(review_id)
            WHERE r.position<=100""").fetchone()
        if first100[0] != 100 or first100[1] != 100 or first100[2] + first100[3] != 100:
            raise ValueError("first-100 quality gate is not fully accounted")
        qa_status(args.manifest, args.budget)
        queue.assert_resume_safe("evidence", defer_uncertain_evidence=args.defer_uncertain_evidence)
        stages = []
        if queue.next_jev() is not None:
            queue.assert_resume_safe("jev")
            verified = verify_jev_price()
            key = canary.keychain_secret(timeout_seconds=90, service=JEV_SERVICE,
                                         account=JEV_ACCOUNT)
            try:
                label_result = run_labels(queue, key)
            finally:
                key = None
            stages.append({"stage": "jev", "admitted": label_result["admitted"],
                           "paused": label_result["paused"],
                           "halt_reason": label_result["halt_reason"],
                           "verified_price": verified})
            if label_result["paused"]:
                return {"status": "paused_after_jev", "stages": stages,
                        "qa": qa_status(args.manifest, args.budget), **queue.summary()}
        if queue.next_evidence(50):
            queue.assert_resume_safe("evidence", defer_uncertain_evidence=args.defer_uncertain_evidence)
            key = canary.keychain_secret(timeout_seconds=90)
            try:
                evidence_result = run_evidence(queue, key, 50,
                    defer_uncertain_evidence=args.defer_uncertain_evidence)
            finally:
                key = None
            stages.append({"stage": "deepinfra", "admitted": evidence_result["admitted"],
                           "paused": evidence_result["paused"],
                           "halt_reason": evidence_result["halt_reason"]})
            if evidence_result["paused"]:
                return {"status": "paused_after_evidence", "stages": stages,
                        "qa": qa_status(args.manifest, args.budget), **queue.summary()}
        qa = qa_status(args.manifest, args.budget)
        status = ("checkpoint_complete" if qa["accepted_rows"] == 5000 else
                  "checkpoint_accounted_with_quarantines" if
                  qa["pending_rows"] == qa["uncertain_rows"] == qa["in_flight_rows"] == 0 else
                  "checkpoint_accounted_with_unresolved" if
                  qa["pending_rows"] == qa["in_flight_rows"] == 0 else
                  "checkpoint_incomplete")
        result = {"status": status, "stages": stages, "qa": qa, **queue.summary()}
        return result
    finally:
        budget.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="local/checkpoint5000_manifest.json")
    parser.add_argument("--budget", default="local/project_budget.db")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--defer-uncertain-evidence", action="store_true",
                        help="keep full uncertain evidence holds and skip their source texts")
    args = parser.parse_args()
    if args.defer_uncertain_evidence and not args.run:
        parser.error("uncertain evidence deferral applies only to --run")
    if args.status:
        budget, queue = open_checkpoint(args)
        try:
            output = {"status": "offline_status", "qa": qa_status(args.manifest, args.budget),
                      **queue.summary()}
        finally:
            budget.close()
    else:
        output = run(args)
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, ConnectionError) as error:
        raise SystemExit(str(error)) from None
