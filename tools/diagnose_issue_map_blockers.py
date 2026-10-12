"""Offline aggregate diagnostics for blind-human issue grouping.

Only this scoring code reads the frozen blind answers. Stdout and its saved
private diagnostic contain aggregates and file hashes, never answer rows.
"""

import json

from tools.validate_claude_issue_map import (AGENT, BASE, BLIND_ANSWERS,
                                             BLIND_MANIFEST, CATALOG, EXPECTED,
                                             digest, read_csv, write_private)


def score_blind_rows(manifest_rows, answer_rows, agent_rows, valid_issue_ids):
    sources = {row["case_ref"]: row for row in manifest_rows}
    agents = {row["review_id"]: row for row in agent_rows}
    if len(sources) != len(manifest_rows) or len(agents) != len(agent_rows) or \
            len(answer_rows) != len(sources) or \
            {row["case_ref"] for row in answer_rows} != set(sources):
        raise ValueError("blind coverage differs")
    overall = {"cases": 0, "exact": 0, "family": 0}
    by_confidence = {}
    by_saved_topic = {}
    uncertain = 0
    for answer in answer_rows:
        source = sources[answer["case_ref"]]
        agent = agents.get(source["review_id"])
        if agent is None or answer["source_text"] != source["source_text"] or \
                not answer["evidence_rationale"].strip():
            raise ValueError("source identity differs")
        human_issue = answer["independent_issue_id"].strip()
        agent_issue = agent["agent_issue_id"].strip()
        confidence = agent["confidence"]
        if human_issue not in valid_issue_ids or agent_issue not in valid_issue_ids or \
                confidence not in {"high", "medium", "low"}:
            raise ValueError("invalid issue or confidence")
        exact = int(human_issue == agent_issue)
        family = int(human_issue.split("-", 1)[0] == agent_issue.split("-", 1)[0])
        for group in (overall,
                      by_confidence.setdefault(confidence, {"cases": 0, "exact": 0, "family": 0}),
                      by_saved_topic.setdefault(source["saved_topic"],
                                                {"cases": 0, "exact": 0, "family": 0})):
            group["cases"] += 1
            group["exact"] += exact
            group["family"] += family
        uncertain += bool(answer["uncertainty_notes"].strip())
    return {"overall": overall, "by_confidence": dict(sorted(by_confidence.items())),
            "by_saved_topic": dict(sorted(by_saved_topic.items())),
            "uncertain_answers": uncertain}


if __name__ == "__main__":
    paths = (BLIND_MANIFEST, BLIND_ANSWERS, AGENT, CATALOG)
    if any(digest(path) != EXPECTED[path] for path in paths):
        raise ValueError("frozen diagnostic input hash differs")
    manifest = json.loads(BLIND_MANIFEST.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if manifest["schema_version"] != "spotify-grouping-independent40-v1" or \
            len(manifest["rows"]) != 40:
        raise ValueError("blind manifest shape differs")
    answers = read_csv(BLIND_ANSWERS,
        ["case_ref", "source_text", "independent_issue_id", "evidence_rationale", "uncertainty_notes"])
    agents = read_csv(AGENT, ["review_id", "agent_issue_id", "confidence"])
    result = score_blind_rows(manifest["rows"], answers, agents,
                              {row["issue_id"] for row in catalog["issues"]})
    if result["overall"]["cases"] != 40 or result["overall"]["exact"] != 16:
        raise ValueError("frozen blind scoring totals differ")
    result.update({"schema_version": "spotify-issue-map-blind-diagnostic-v1",
                   "status": "aggregate_diagnostic_not_population_accuracy",
                   "input_sha256": {path.name: digest(path) for path in paths}})
    output = BASE / "blind_diagnostic_v1.json"
    write_private(output, result)
    print(json.dumps({"overall": result["overall"],
                      "by_confidence": result["by_confidence"],
                      "by_saved_topic": result["by_saved_topic"],
                      "uncertain_answers": result["uncertain_answers"],
                      "diagnostic_sha256": digest(output)}, sort_keys=True))
