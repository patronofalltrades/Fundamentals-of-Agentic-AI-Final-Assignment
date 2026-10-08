// Typed, read-only access to the dashboard API (dashboard/server.py).
// Islands on one page share module state, so each endpoint is fetched once.

export type Trends = {
  months: string[]
  reviews: number[]
  complaints: number[]
  mean_severity: (string | null)[]
}

export type EvaluationSet = {
  label_set: string
  benchmark_version: string
  approved_cases: number
  total_cases: number
  missing_or_invalid_predictions: number
  agreement: { topic: number | null; intent: number | null; severity: number | null; joint: number | null }
  severity_mae_on_valid_predictions: number | null
  official: boolean
  label_config: string
}

export type Summary = {
  source: { basename: string; sha256: string; config_hash: string | null }
  coverage: {
    source_rows: number
    nonempty_rows: number
    distinct_nonempty_texts: number
    completed_rows: number
    empty_rows: number
  }
  raw_labels: { topic: Record<string, number>; intent: Record<string, number>; severity: Record<string, number> }
  quality: { classifier_agreement: number | null; blind_verifier: string; human_evaluation: string }
  analysis: { grouping: string; ranking: string; recommendations: string; memo: string; run_id: string | null }
  target: { minimum_source_rows: number; is_demo: boolean }
  trends: Trends | null
  evaluation: { status: "pending" } | { status: "saved"; sets: Record<string, EvaluationSet> }
  top_issue: {
    issue_id: string
    title: string
    mean_severity: string
    priority_score: number
    complaint_count: number
  } | null
  note: string
}

export type Issue = {
  issue_id: string
  title: string
  review_count: number
  priority_score: number
  mean_severity: string
}
export type Issues = { status: string; run_id?: string; ranking_method: string; items: Issue[] }

export type Claim = { claim_id: string; issue_id: string; metric: string; value: string }
export type Claims = { status: string; run_id?: string; items: Claim[] }
export type Memo = { status: string; run_id?: string; text: string | null; sha256?: string }

export type ReviewItem = {
  row_index: number
  source_sha256: string
  topic: string
  intent: string
  severity: number
  evidence_quote: string
  needs_review: number
  is_cached: number
}
export type Reviews = { items: ReviewItem[]; total: number; limit: number; offset: number }
export type ReviewDetail = ReviewItem & {
  sentiment: number | null
  label_config: string
  model: string | null
  prompt_version: string | null
}

export type EvalMetric = { label: string; value: number | string | null; format: string; of?: number; note?: string | null }
export type EvalItem = {
  id: string
  kind: "benchmark" | "run" | "projection" | "accuracy"
  title: string
  question: string
  sample: string
  truth: string
  status: "measured" | "partial" | "estimate" | "pending"
  metrics: EvalMetric[]
  compare?: { row_header?: string; columns: string[]; rows: { label: string; format: string; values: (number | string | null)[]; note?: string | null }[] }
  decision?: string
  finding?: string
  limits: string[]
  sources: string[]
}
export type EvalCheck = { name: string; status: "passed" | "pending" | "failed"; detail: string }
export type Evals = {
  model?: string
  prompt_version?: string
  built_from?: { path: string; sha256: string }[]
  items: EvalItem[]
  golden: Summary["evaluation"]
  checks: EvalCheck[]
}

export const TOPICS = ["access", "usability", "playback", "downloads", "catalog", "billing", "support", "other"] as const

const cache = new Map<string, Promise<unknown>>()

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" } })
  if (!response.ok) throw new Error(`API ${response.status}`)
  return (await response.json()) as T
}

function once<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    const request = get<T>(path)
    request.catch(() => cache.delete(path)) // allow a retry after a failure
    cache.set(path, request)
  }
  return cache.get(path) as Promise<T>
}

export const api = {
  summary: () => once<Summary>("/api/summary"),
  issues: () => once<Issues>("/api/issues"),
  claims: () => once<Claims>("/api/claims"),
  memo: () => once<Memo>("/api/memo"),
  evals: () => once<Evals>("/api/evals"),
  reviews: (params: { topic?: string; q?: string; offset?: number; limit?: number }) => {
    const search = new URLSearchParams()
    if (params.topic) search.set("topic", params.topic)
    if (params.q) search.set("q", params.q)
    search.set("limit", String(params.limit ?? 12))
    search.set("offset", String(params.offset ?? 0))
    return get<Reviews>(`/api/reviews?${search}`)
  },
  review: (rowIndex: number) => once<ReviewDetail>(`/api/reviews/${rowIndex}`),
}

export const fmt = {
  int: (n: number) => n.toLocaleString("en-US"),
  pct: (n: number, digits = 0) => `${(n * 100).toFixed(digits)}%`,
  month: (m: string) => {
    const [y, mm] = m.split("-")
    return new Date(Number(y), Number(mm) - 1, 1).toLocaleString("en-US", { month: "short", year: "2-digit" })
  },
  label: (s: string) => s.replaceAll("_", " "),
  /** Format a saved metric. Values may arrive as decimal strings to keep their precision. */
  value: (v: number | string | null | undefined, format: string) => {
    if (v === null || v === undefined) return "—"
    const n = Number(v)
    if (!Number.isFinite(n)) return String(v)
    if (format === "usd") return n < 0.1 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`
    if (format === "seconds") return n < 60 ? `${n.toFixed(1)} s` : `${(n / 60).toFixed(1)} min`
    if (format === "hours") return `${n.toFixed(1)} h`
    if (format === "ratio") return `${(n * 100).toFixed(0)}%`
    return n.toLocaleString("en-US")
  },
}
