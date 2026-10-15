"""Recover the saved trail of the 11 October grouping handoff. Offline; prints aggregates.

The grouping agents and the blind verifier ran as a chat handoff with no API
usage log. Their input batches, outputs and reference key were saved in the
handoff directory. This tool reads those files only. It checks that each file
is the one the handoff report hashed, that the verifier's inputs held no
grouping output, and that the reported 511 of 600 agreement follows from the
saved rows. It never prints or publishes review text, evidence quotes or IDs.

    python3 -m tools.recover_grouping_trail --handoff DIR --publish reports/grouping-trail-recovery-2026-10-16
"""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(review_id):
    """Published case files name a review by the SHA-256 of its ID, not the ID itself."""
    return hashlib.sha256(review_id.encode()).hexdigest()


def labels(path, prefix):
    rows = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r.get("ref") or "").strip()
            if key.startswith(prefix):
                if key in rows:
                    raise ValueError("repeated ref in " + path.name)
                rows[key] = ((r.get("issue_id") or "").strip(), (r.get("confidence") or "").strip())
    return rows


def batch_inputs(folder):
    """Header, row count and hash of each saved input batch. Text is not kept."""
    out = []
    for path in sorted(folder.glob("batch_*.tsv")):
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)
            refs = [row[0] for row in reader if row]
        out.append({"file": path.parent.name + "/" + path.name, "sha256": sha(path), "columns": header,
                    "rows": len(refs), "refs": refs})
    return out


def recover(handoff):
    d = Path(handoff)
    report = json.loads((d / "report_v1.json").read_text())
    key = json.loads((d / "private/key.json").read_text())
    hashed = {name: sha(d / name) == digest for name, digest in report["files_sha256"].items()}
    if not all(hashed.values()):
        raise ValueError("a handoff file differs from the hash in report_v1.json")

    grouping = {}
    files = []
    for i in range(1, 9):
        folder = d / "work" / ("chunk%d" % i)
        batches = batch_inputs(folder)
        out = labels(d / "work" / ("out_chunk%d.csv" % i), "M")
        sent = [r for b in batches for r in b["refs"]]
        files.append({"chunk": i, "input_batches": len(batches), "input_rows": len(sent),
                      "input_columns": sorted({tuple(b["columns"]) for b in batches}),
                      "output_rows": len(out), "output_sha256": sha(d / "work" / ("out_chunk%d.csv" % i)),
                      "every_input_has_one_output": set(sent) == set(out) and len(sent) == len(set(sent)),
                      "input_sha256": [b["sha256"] for b in batches]})
        for r, v in out.items():
            if r in grouping:
                raise ValueError("ref labelled in two chunks")
            grouping[r] = v
    agent = {key["map"][r]: v for r, v in grouping.items()}

    with open(d / "agent_labels_v1.csv", newline="", encoding="utf-8") as f:
        saved = {r["review_id"]: (r["agent_issue_id"], r["confidence"]) for r in csv.DictReader(f)}
    assembled_matches = sum(saved.get(rid) == v for rid, v in agent.items())

    vbatches = batch_inputs(d / "work" / "verify")
    vsent = [r for b in vbatches for r in b["refs"]]
    ver_raw = labels(d / "work" / "verify" / "labels.csv", "V")
    ver = {key["verify"][r]: v for r, v in ver_raw.items()}
    pairs = [(ver[rid][0], agent[rid][0]) for rid in ver if rid in agent]
    high = [(a, b) for rid, (a, b) in zip(ver, pairs) if ver[rid][1] == "high" and agent[rid][1] == "high"]
    blind_columns = sorted({c for b in vbatches for c in b["columns"]})

    result = {
        "handoff_date": "2026-10-11",
        "source_report_files_match_their_hashes": hashed,
        "frame_sha256": key["frame_sha256"],
        "catalog_sha256": report["catalog_sha256"],
        "grouping": {"chunks": files, "records": len(grouping),
                     "outputs_match_assembled_agent_labels": "%d of %d" % (assembled_matches, len(agent)),
                     "usage": "unavailable: subscription agents wrote no per-call API usage log"},
        "verifier": {
            "input_batches": [{k: b[k] for k in ("file", "sha256", "columns", "rows")} for b in vbatches],
            "input_columns": blind_columns,
            "inputs_hold_no_grouping_output": not ({"issue_id", "agent_issue_id", "confidence"} & set(blind_columns)),
            "refs_separate_from_grouping_refs": not (set(vsent) & set(grouping)),
            "outputs": len(ver_raw), "outputs_sha256": sha(d / "work" / "verify" / "labels.csv"),
            "every_input_has_one_output": set(vsent) == set(ver_raw),
            "agreed": sum(a == b for a, b in pairs), "cases": len(pairs),
            "both_high_confidence": {"agreed": sum(a == b for a, b in high), "cases": len(high)},
            "matches_reported_511_of_600": (sum(a == b for a, b in pairs), len(pairs)) ==
                (report["verifier"]["agreed"], report["verifier"]["cases"]),
            "top_disagreements": [{"verifier": a, "agent": b, "n": n} for (a, b), n in
                                  Counter(p for p in pairs if p[0] != p[1]).most_common(5)],
            "usage": "unavailable: the verifier ran in a chat session with no API usage log"},
    }
    cases = [[ref(rid), agent[rid][0], agent[rid][1], ver[rid][0], ver[rid][1]] for rid in sorted(ver, key=ref)]
    return result, cases


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--handoff", required=True)
    ap.add_argument("--publish")
    args = ap.parse_args(argv)
    result, cases = recover(args.handoff)
    if args.publish:
        dest = Path(args.publish)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        with open(dest / "verifier_600_cases.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["review_ref", "agent_issue", "agent_confidence", "verifier_issue", "verifier_confidence"])
            w.writerows(cases)
    v = result["verifier"]
    print(json.dumps({"verifier": "%d of %d" % (v["agreed"], v["cases"]), "matches_report": v["matches_reported_511_of_600"],
                      "blind": v["inputs_hold_no_grouping_output"], "grouping_records": result["grouping"]["records"]}))


if __name__ == "__main__":
    main()
