// Section reflections: what we learned, not what the section shows. Edit the wording here.
// Every number below comes from a saved report: reports/jev-checkpoint-500.json (500-review checkpoint),
// reports/jev-rubric-v1-v2-100.json (prompt v1 against v2), or the explainer's saved record.

export const REFLECTIONS = {
  issues:
    "Most reviews are not complaints. At the 500-review checkpoint, 289 reviews landed in topic “other” and 258 had severity 1. " +
    "We rank by the sum of severities, so both volume and harm count: a frequent mild issue can outrank a rare severe one. " +
    "We kept that trade-off because the course scorer uses the same rule.",
  memo:
    "We wanted every number in the memo to be checkable. Each figure carries a claim ID. The import refuses a ranking it cannot " +
    "recompute, and it flags any memo number that differs from its saved claim, here on the page.",
  evals:
    "Two lessons shaped this section. A prompt change can move many labels without moving the ranking: rubric v2 changed " +
    "32 of 100 topics but only 1 severity. And human labels must be locked before anyone sees model output. One copy of the " +
    "golden set was revised after its author saw Jev's answers, so we score against the original.",
  example:
    "This review taught us to keep three claims apart: accepted, confident and correct. It passed every check, yet its severity " +
    "confidence was 0.27. Across the 500-review checkpoint, 387 rows fell below the 0.60 threshold, so the review flag is too " +
    "broad to triage with on its own.",
  evidence:
    "Labels were cheap; evidence was not. Jev labelled 500 reviews for about $0.016 with 384,476 input tokens. Extracting " +
    "exact quotes for the same reviews used 6,955,138 input tokens. That gap is why we benchmarked cheaper hosted extractors. " +
    "Every quote here is checked against the source text, character by character.",
}

export const NEXT_TIME = [
  { title: "Save every failed response", body: "One extractor response failed validation, and we could not say why: only the error class was saved. The runner now keeps the response and the validator's message." },
  { title: "Measure time in one process", body: "The v2 run recorded a negative wall time because start and end came from different processes. Summed request time is not stage time." },
  { title: "Keep the option probabilities", body: "Jev can return a likelihood for each option. We saved only confidence, so we cannot check calibration after the fact." },
]
