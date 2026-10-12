"""Export private corrected grouping results for offline dashboard/grade checks.

The export is not a full-corpus checker pass or permission to publish data.
"""

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from tools.issue_grouping_handoff import LOCAL_DIR, sha256


HASHES = {
    "handoff": "01d3f466e86f3d6a010f5e9b28b2c1347e683d925228591ff6fa36a2bb75c39c",
    "corrections": "0411331243627624e46c1bc78decd3613fe348a64290171a7a1b5bae810bafa5",
    "frame": "afa34a49dca3e80188d85bdb86607d234b628275b62ed2be6b8a9d60e0865787",
    "membership": "e7ce3bc5f1349c24c7e086843e49a162406b92d30f2ce5e7d915c984929a60fe",
    "ranking": "87c67b07f6ac9d7abdbfa2b36f506dba44c1dec2223e29e9d7367b045582575f",
    "catalog": "8c73e62059e86aea48b94da0d4b0bf86df048e0d83442e1ce4bf7b44dc105111",
    "map_report": "82db52159d1b44108e457fe8bb88acd697b7216025517730561d9e90daac1f60",
}
RANKING_FIELDS = ("rank", "issue_id", "complaint_count", "severity_sum",
                  "mean_severity", "priority_score")
CLAIM_FIELDS = ("claim_id", "issue_id", "metric", "value")
METRICS = ("complaint_count", "severity_sum", "mean_severity", "priority_score")


def _read_json(path, digest):
    if sha256(path) != digest:
        raise ValueError("frozen input digest differs: " + path.name)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path, fields, rows):
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fields})


def _write_json(path, value):
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True,
                  separators=(",", ":"))
        stream.write("\n")


def _write_text(path, value):
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(value)


def _rank_rows(rows):
    return [{key: str(row[key]) for key in RANKING_FIELDS} for row in rows]


def _claims(ranking):
    return [{"claim_id": "claim-%04d-%s" % (int(row["rank"]), metric),
        "issue_id": row["issue_id"], "metric": metric, "value": row[metric]}
        for row in ranking for metric in METRICS]


def _memo(ranking, claims, report):
    top = ranking[0]
    lines = ["# provisional product priority memo", "",
        "This issue map is model-derived with 51 pilot and 40 blind human overrides. Before those overrides, the grouping agents agreed with a separate model verifier on 511 of 600 cases (85.2%). They agreed with the reviewed human pilot on 39 of 51 (76.5%) and with the blind human review on 16 of 40 (40.0%). Those human cases are no longer untouched holdouts for the final membership. These checks do not validate individual memberships or prove population accuracy.",
        "", "## provisional finding", "",
        "The leading mapped issue is %s. It has %s mapped complaint or cancellation records and a severity sum of %s in the corrected baseline. The public projection excludes 23 known flagged candidates. These counts follow saved model-derived membership and should be checked against human review before a product decision." %
        (top["issue_id"], top["complaint_count"], top["severity_sum"]),
        "", "## recommended next action", "",
        "Review a targeted sample of the leading issue and the catalog gaps, then decide whether the ad experience warrants a product change. Keep the current ranking advisory until that review is complete.",
        "", "## catalog gaps", "",
        "The approved catalog has no separate app-install issue. The handoff also notes free-tier limits, blank saved collections, a disappearing playback control bar, unwanted autoplay or auto-start, songs added to playlists, ads reported by premium users, regional availability, battery or data use, removed features, and lossless audio. These boundaries require review before changing the frozen catalog.",
        "", "## checked claim ledger", ""]
    for claim in claims:
        lines.append("- %s: %s %s = %s" % (claim["claim_id"],
            claim["issue_id"], claim["metric"], claim["value"]))
    return "\n".join(lines) + "\n"


def _claim_check(memo, claims):
    lines = memo.splitlines()
    known = {claim["claim_id"] for claim in claims}
    if not memo.strip() or any(not any(claim["claim_id"] in line and
            claim["value"] in line for line in lines) for claim in claims):
        return "failed"
    if any(cid not in known for cid in re.findall(
            r"\bclaim-[A-Za-z0-9_.:-]*[A-Za-z0-9_]", memo)):
        return "failed"
    return "passed"


def export(root, handoff, corrections, frame, membership, ranking, catalog, report):
    if root.exists():
        raise FileExistsError("grading output already exists")
    if report["frame_sha256"] != "e9d5b4c1f82d3498228ad0ef67f452061023c45b81477403cfe9e533827fe1bf" or \
            report["catalog_sha256"] != "f612276e5224a260bb4cd866bccab7290c7e9dee938e741017bbf228e3436d7b" or \
            frame["baseline_candidates"] != 30400 or frame["public_candidates"] != 30377 or \
            ranking["baseline_denominator"] != 30400 or \
            ranking["public_denominator"] != 30377 or len(membership) != 30400:
        raise ValueError("grouping provenance or coverage differs")
    changed = {row["review_id"]: row for row in corrections["rows"]}
    if len(changed) != 7 or {row["pilot_index"] for row in changed.values()} != \
            {18, 43, 61, 80, 89, 94, 97}:
        raise ValueError("seven correction identities differ")
    if len(handoff["records"]) != 100229 or len(handoff["excluded"]) != 9771:
        raise ValueError("accepted handoff partition differs")
    ranks = _rank_rows(ranking["baseline"])
    public = _rank_rows(ranking["public_advisory"])
    claims = _claims(ranks)
    memo = _memo(ranks, claims, report)
    if len(ranks) != 41 or len(claims) != 164 or _claim_check(memo, claims) != "passed":
        raise ValueError("claims or memo check differs")

    temp = Path(tempfile.mkdtemp(prefix=".grading-v4-", dir=str(root.parent)))
    os.chmod(temp, 0o700)
    try:
        run = {"version": "spotify-grouping-v4-20261012",
            "analysis_sha256": handoff["source_file_sha256"],
            "accepted_handoff_sha256": HASHES["handoff"],
            "catalog_sha256": HASHES["catalog"],
            "corrections_sha256": HASHES["corrections"],
            "membership_sha256": HASHES["membership"],
            "allow_multi_issue": False,
            "human_label_corrections": sorted(changed),
            "grouping_status": "model_derived_human_accuracy_unverified",
            "ranking_baseline_denominator": 30400,
            "ranking_public_denominator": 30377,
            "known_flagged_excluded_from_public": 23,
            "scope_note": "100229 structurally accepted IDs; not the unchanged full-corpus grading checker"}
        _write_json(temp / "run.json", run)
        _write_csv(temp / "membership.csv", ("issue_id", "review_id"), membership)
        _write_csv(temp / "ranking.csv", RANKING_FIELDS, ranks)
        _write_csv(temp / "ranking_public.csv", RANKING_FIELDS, public)
        _write_csv(temp / "claims.csv", CLAIM_FIELDS, claims)
        _write_text(temp / "memo.md", memo)
        _write_json(temp / "claim_check.json", {"status": "passed",
            "claims_checked": len(claims), "memo_sha256": hashlib.sha256(
                memo.encode("utf-8")).hexdigest(),
            "ranking_sha256": sha256(temp / "ranking.csv")})
        _write_json(temp / "grouping_usage.json", {
            "schema_version": "spotify-grouping-usage-availability-v1",
            "source_report_sha256": HASHES["map_report"],
            "group": {"provider": "Claude subscription agents", "workers_reported": 8,
                "per_call_log_available": False, "call_count": None,
                "input_tokens": None, "output_tokens": None, "cost_usd": None,
                "usage_status": "unavailable"},
            "verify": {"provider": "Claude subscription verifier",
                "workers_reported": 1, "per_call_log_available": False,
                "call_count": None, "input_tokens": None, "output_tokens": None,
                "cost_usd": None, "usage_status": "unavailable"}})
        fd = os.open(str(temp / "records.jsonl.gz"),
                     os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        accepted_seen = set()
        with os.fdopen(fd, "wb") as binary:
            with gzip.GzipFile(fileobj=binary, mode="wb", mtime=0) as packed:
                for source in handoff["records"]:
                    rid = source["review_id"]
                    if rid in accepted_seen:
                        raise ValueError("accepted source ID repeats")
                    accepted_seen.add(rid)
                    lab = source["labels"]
                    row = {"review_id": rid,
                        "source_sha256": source["source_sha256"],
                        "status": "completed", "topic": lab["topic"],
                        "intent": lab["intent"], "severity": lab["severity"],
                        "evidence_quote": source["evidence"]["evidence_quote"]}
                    change = changed.get(rid)
                    if change:
                        for key, value in change["changes"].items():
                            row[key] = value
                        if row["evidence_quote"] not in \
                                source["source"]["review_text"]:
                            raise ValueError("corrected quote is not source-exact")
                    packed.write((json.dumps(row, ensure_ascii=False,
                        sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
                if not set(changed) <= accepted_seen:
                    raise ValueError("human correction ID is not accepted")
                excluded_seen = set()
                for source in handoff["excluded"]:
                    rid = source["review_id"]
                    if rid in accepted_seen or rid in excluded_seen:
                        raise ValueError("excluded source ID repeats")
                    excluded_seen.add(rid)
                    row = {"review_id": rid,
                        "source_sha256": source["source_sha256"],
                        "status": source["status"]}
                    packed.write((json.dumps(row, ensure_ascii=False,
                        sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
        if len(accepted_seen) != 100229 or len(excluded_seen) != 9771:
            raise ValueError("selected source partition differs")
        manifest = {"schema_version": "spotify-grouping-grading-export-v4",
            "selected_rows": 110000, "completed_rows": 100229,
            "nonaccepted_rows": 9771, "human_label_corrections": 7,
            "baseline_memberships": 30400, "public_projection_memberships": 30377,
            "claims": 164, "memo_claim_check": "passed",
            "input_sha256": HASHES,
            "file_sha256": {p.name: sha256(p) for p in temp.iterdir() if p.is_file()}}
        _write_json(temp / "manifest.json", manifest)
        os.replace(temp, root)
    finally:
        if temp.exists(): shutil.rmtree(temp)
    return {"selected": 110000, "accepted": 100229,
        "memberships": 30400, "public_candidates": 30377,
        "claims": 164, "memo_claim_check": "passed",
        "manifest_sha256": sha256(root / "manifest.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.resolve().parent != LOCAL_DIR:
        raise ValueError("grading output must stay under local/")
    paths = {"handoff": args.handoff,
        "corrections": LOCAL_DIR / "issue_grouping_corrections_v4.json",
        "frame": LOCAL_DIR / "accepted100k_issue_grouping_frame_v4.json",
        "membership": LOCAL_DIR / "issue_membership_v4.csv",
        "ranking": LOCAL_DIR / "issue_ranking_v4.json",
        "catalog": Path("docs/issue-catalog-v1.json"),
        "report": LOCAL_DIR / "claude_issue_map_v1/report_v1.json"}
    inputs = {key: _read_json(path, HASHES["map_report" if key == "report" else key])
              for key, path in paths.items()
              if key not in {"membership"}}
    if sha256(paths["membership"]) != HASHES["membership"]:
        raise ValueError("corrected membership digest differs")
    with paths["membership"].open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["issue_id", "review_id"]:
            raise ValueError("corrected membership columns differ")
        inputs["membership"] = list(reader)
    print(json.dumps(export(args.out, **inputs), sort_keys=True))


if __name__ == "__main__":
    main()
