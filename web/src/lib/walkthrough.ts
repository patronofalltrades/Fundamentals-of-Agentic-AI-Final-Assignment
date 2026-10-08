// One saved review, end to end. Source: the "Jev explainer" handoff (snapshot 8 October 2026, commit 1eb3345),
// read from saved project records of the 5,000-review development checkpoint. No model call happens here.
//
// Public-data exception (Hanif, 8 October 2026): this one public Google Play review is shown in full so the
// walkthrough can highlight its evidence. Its review ID is omitted. No other page or API shows full texts.

export const REVIEW = {
  before:
    "I would love to hear any songs for free and download them with a subscription.. To be honest this is a great music app but the only fault that i noticed is that ",
  quote: "the lyrics of some songs in Tamizh language is wrong",
  after:
    " and I think that'll create a very bad image on the app itself.. So, I request Spotify to update the lyrics of Tamizh songs and many other language songs in their own language..",
  row: 75,
  of: 5000,
  entities: ["lyrics", "Tamizh language"],
}

export const POLICY_THRESHOLD = 0.6
export const SAVED_NEEDS_REVIEW = true

export type FieldKey = "topic" | "intent" | "severity" | "sentiment"
export type SavedField = {
  name: string
  type: "Choice" | "Score"
  value: string
  confidence: number
  copy: string
  probabilityCopy: string
}

export const FIELDS: Record<FieldKey, SavedField> = {
  topic: {
    name: "Topic", type: "Choice", value: "catalog", confidence: 0.95,
    copy: "Jev put this Tamizh-lyrics review under the catalog topic. This is the saved selection, not an independent judgment that the label is correct.",
    probabilityCopy: "The other topic probabilities were not saved. The 0.95 is confidence, not a 95% probability for catalog.",
  },
  intent: {
    name: "Intent", type: "Choice", value: "request", confidence: 0.65,
    copy: "Jev labelled the intent as request. The review asks Spotify to update lyrics; that text is visible above.",
    probabilityCopy: "The probabilities for request and the other intent options were not saved. The 0.65 is native confidence.",
  },
  severity: {
    name: "Severity", type: "Choice", value: "2", confidence: 0.27,
    copy: "Jev selected severity 2 for this review. Its confidence is low enough to trigger the project's review policy.",
    probabilityCopy: "The probabilities for the other severity labels were not saved. The 0.27 is confidence, not the probability that severity 2 is correct.",
  },
  sentiment: {
    name: "Sentiment", type: "Score", value: "+0.325", confidence: 0.68,
    copy: "The saved sentiment is +0.325 on the project's −1 to +1 scale, rescaled from Jev's 0–4 Score scale. It is a rating, not a likelihood.",
    probabilityCopy: "The distribution across sentiment levels was not saved. Its native confidence is 0.68, which is separate from the +0.325 rating.",
  },
}

export const CONFIDENCE_COPY = {
  Choice: "Choice confidence summarises the leading option against an even split. It is copied unchanged into the project record.",
  Score: "Score confidence summarises how concentrated the answer is around one rating, given that ratings are ordered. It is copied unchanged; only the rating is rescaled.",
}

/** The project's review rule, applied to this one record at a hypothetical threshold. */
export function reviewAt(threshold: number) {
  const low = (Object.values(FIELDS) as SavedField[]).filter((f) => f.confidence < threshold)
  const special = FIELDS.topic.value === "other" || FIELDS.intent.value === "unclear"
  return { needsReview: low.length > 0 || special, low, special }
}

export const STEPS = [
  {
    owner: "Source", label: "Source text",
    title: "Keep the original review.",
    copy: "This is row 75 of the 5,000-review development checkpoint. The unchanged text is the reference for every label and quote shown here.",
    example: "Source → row 75 of 5,000, development checkpoint",
  },
  {
    owner: "TypeSafe · Jev", label: "Jev labels",
    title: "Return four typed judgments.",
    copy: "The Jev request succeeded. Topic, intent and severity use Choice; sentiment uses Score. Confidence values were checked and copied unchanged. Option distributions and the raw response were not saved.",
    example: "catalog (0.95) · request (0.65) · severity 2 (0.27) · sentiment +0.325 (0.68)\nParentheses hold confidence, not class probabilities.",
  },
  {
    owner: "DeepInfra · separate model", label: "DeepInfra evidence",
    title: "Extract the words a reader can check.",
    copy: "The extraction step returned this exact quote and the entities “lyrics” and “Tamizh language”. It is supporting source text, not a trace of Jev's reasoning.",
    example: "“the lyrics of some songs in Tamizh language is wrong”",
  },
  {
    owner: "Application code", label: "Validate and store",
    title: "Accept the row. Keep the review flag.",
    copy: "The exact-source check passed and the source hashes matched. No human correction or quarantine was recorded. The evidence batch partly succeeded, but this row was accepted. Severity confidence below 0.60 sets the review flag.",
    example: "accepted = true\nneeds_review = true, because severity confidence 0.27 < 0.60",
  },
  {
    owner: "Dashboard", label: "Inspect results",
    title: "Show the result with its caveat.",
    copy: "Read the labels with their quote and status. For this record, accepted and needs_review are both true. A saved model output is not a human-verified conclusion.",
    example: "This record → accepted + flagged for review",
  },
]

export const CONCEPTS = [
  { eyebrow: "Choice", title: "catalog, request and severity 2",
    body: "Three bounded judgments about the same review. The model picks from the options in each question. A valid label does not by itself prove the classification is right." },
  { eyebrow: "Score", title: "Sentiment is +0.325",
    body: "A rating, not a probability. The pipeline maps the 0–4 scale onto −1 to +1. The separate 0.68 confidence uses TypeSafe's Score definition, which accounts for ordered levels." },
  { eyebrow: "Probabilities", title: "The part this record does not have",
    body: "Jev's API can return a likelihood for each option. Those were not saved here. So we cannot call catalog “95% likely”, or rebuild the missing probabilities from these values." },
  { eyebrow: "Evidence", title: "Why highlight the lyrics phrase?",
    body: "DeepInfra's extraction step returned that exact phrase, and the source-span check passed. It ties the output to the review; it does not measure each word's influence on Jev." },
]

export const SOURCES = [
  { href: "https://docs.typesafe.ai/primitives/choice", label: "Choice: typed answers and response structure" },
  { href: "https://docs.typesafe.ai/primitives/score", label: "Score: ordered ratings and response structure" },
  { href: "https://docs.typesafe.ai/confidence", label: "Confidence: exact calculation and threshold guidance" },
  { href: "https://docs.typesafe.ai/introduction/machine-learning-primer", label: "AI primer: RLCD and calibration claims" },
  { href: "https://docs.typesafe.ai/introduction", label: "Introduction: typed questions and independent evaluations" },
  { href: "https://typesafe.ai/blog/introducing-system-one-models-and-jev", label: "Launch article: architecture and training claims" },
]
