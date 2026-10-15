import type { ReactNode } from "react"
import { ArrowDown, CornerDownRight } from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"
import { api, fmt, type Summary } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Reflection } from "./bits"
import { useData } from "./use-data"

// The two flowcharts in docs/pipeline-extraction.mmd and docs/pipeline-analysis.mmd, drawn in the dashboard's
// own style. Counts come from /api/summary where the database holds them; the rest are the saved source values.

type Kind = "data" | "code" | "model" | "store" | "handoff" | "result"
type Branch = { label: string; to: string; tone?: "warn" | "gap" | "skip" }
type Step = { kind: Kind; title: string; detail?: ReactNode; branches?: Branch[] }

const KIND: Record<Kind, { name: string; box: string; chip: string }> = {
  data: { name: "Data", box: "bg-tile", chip: "bg-canvas text-muted-foreground" },
  code: { name: "Code", box: "bg-tile", chip: "bg-primary/15 text-primary" },
  model: { name: "Model", box: "bg-tile", chip: "bg-chart-2/15 text-chart-2" },
  store: { name: "Store", box: "bg-tile", chip: "bg-chart-3/15 text-chart-3" },
  handoff: { name: "Agent handoff", box: "border border-dashed border-chart-2/60 bg-transparent", chip: "bg-chart-2/15 text-chart-2" },
  result: { name: "Result", box: "bg-primary/10 ring-1 ring-primary/40", chip: "bg-primary text-primary-foreground" },
}

const TONE: Record<NonNullable<Branch["tone"]>, string> = {
  warn: "text-chart-2",
  gap: "text-negative",
  skip: "text-chart-3",
}

function Flow({ steps }: { steps: Step[] }) {
  return (
    <ol className="space-y-0">
      {steps.map((step, i) => (
        <li key={step.title}>
          {i > 0 && <ArrowDown className="mx-auto my-1 size-4 text-track" aria-hidden="true" />}
          <div className={cn("rounded-2xl px-4 py-3", KIND[step.kind].box)}>
            <div className="flex items-start justify-between gap-3">
              <p className="text-[15px] text-foreground">{step.title}</p>
              <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[11px]", KIND[step.kind].chip)}>{KIND[step.kind].name}</span>
            </div>
            {step.detail && <p className="mt-0.5 text-[13px] text-muted-foreground">{step.detail}</p>}
            {step.branches && (
              <ul className="mt-2 space-y-1 border-t border-dashed border-track/60 pt-2 text-[13px]">
                {step.branches.map((b) => (
                  <li key={b.label} className="flex gap-1.5">
                    <CornerDownRight className={cn("mt-0.5 size-3.5 shrink-0", b.tone ? TONE[b.tone] : "text-muted-foreground")} aria-hidden="true" />
                    <span><span className="text-muted-foreground">{b.label}:</span> <span className={b.tone ? TONE[b.tone] : "text-foreground"}>{b.to}</span></span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}

function Controls({ items }: { items: { title: string; detail: string; acts: string }[] }) {
  return (
    <ul className="mt-4 grid gap-3 sm:grid-cols-2">
      {items.map((c) => (
        <li key={c.title} className="rounded-2xl border border-dashed border-track px-4 py-3">
          <p className="text-[14px] text-foreground">{c.title}</p>
          <p className="mt-0.5 text-[13px] text-muted-foreground">{c.detail}</p>
          <p className="mt-1 text-[12px] text-muted-foreground">Acts on: <span className="text-foreground">{c.acts}</span></p>
        </li>
      ))}
    </ul>
  )
}

function extraction(s: Summary): Step[] {
  const selected = s.import?.selected_rows ?? s.coverage.source_rows
  const accepted = s.import?.accepted_rows ?? s.coverage.completed_rows
  return [
    { kind: "data", title: "Immutable source CSV", detail: "660,622 original review IDs" },
    { kind: "code", title: "Parse and hash the exact fields", detail: <>Freeze {fmt.int(selected)} selected IDs</> },
    { kind: "store", title: "Durable SQLite queue", detail: "Configuration-safe exact-text cache",
      branches: [{ label: "Valid label or evidence in the cache", to: "skips the model call", tone: "skip" }] },
    { kind: "model", title: "Jev classifier", detail: "Topic, intent and severity · one review per request",
      branches: [{ label: "Unknown delivery", to: "uncertain request; full reservation kept until reconciled", tone: "warn" }] },
    { kind: "code", title: "Validate and save the labels" },
    { kind: "model", title: "DeepInfra evidence extractor", detail: "An exact quote per review · up to 25 distinct texts per request",
      branches: [{ label: "Unknown delivery", to: "uncertain request; full reservation kept until reconciled", tone: "warn" }] },
    { kind: "code", title: "Check IDs, schema and source spans", detail: "Save per-ID evidence and its provenance",
      branches: [{ label: "Invalid evidence", to: "quarantined with a reason", tone: "warn" }] },
    { kind: "result", title: `${fmt.int(accepted)} accepted source IDs`, detail: "Semantic flags stay separate" },
  ]
}

function analysis(s: Summary): Step[] {
  const cand = s.import?.issue_candidates
  const issues = s.import?.issue_import?.issues
  const corrections = s.import?.issue_import?.human_label_corrections
  return [
    { kind: "data", title: "Accepted labels and evidence" },
    { kind: "code", title: "Build the complaint and cancellation frame",
      detail: corrections ? `With ${corrections} declared human label corrections` : undefined },
    { kind: "handoff", title: "Grouping-agent handoff", detail: <>Historical: saved assignments to a {issues ?? 41}-issue catalog. Not a program stage.</>,
      branches: [
        { label: "Blind verifier handoff", to: "511 of 600 assignments agreed (85.2%)", tone: "warn" },
        { label: "Gap", to: "case-level verifier trail and usage are incomplete; the aggregate is not a full audit", tone: "gap" },
      ] },
    { kind: "code", title: "Validate membership", detail: "Apply reviewed corrections and overrides" },
    { kind: "result", title: `${fmt.int(cand?.contract_baseline ?? 30400)} baseline members`, detail: "One issue per review",
      branches: [{ label: `Exclude ${fmt.int(cand?.flagged_excluded ?? 23)} flagged members`, to: `${fmt.int(cand?.public_projection ?? 30377)} public members` }] },
    { kind: "code", title: "Rank by severity sum", detail: "Descending, then issue ID ascending" },
    { kind: "code", title: "Saved memo and recommendations", detail: "Code checks every numeric claim" },
    { kind: "store", title: "Sanitized release database", detail: "Local SQLite · deployed Neon Postgres" },
    { kind: "code", title: "Read-only Python backend", detail: "Serves stored results; makes no model call" },
    { kind: "result", title: "This dashboard and the memo page", detail: "Astro on Vercel" },
  ]
}

const EVALUATION: Step[] = [
  { kind: "data", title: "Human-only answers + accepted labels" },
  { kind: "code", title: "Isolated offline evaluator", detail: "50 source-only predictions, frozen before scoring" },
  { kind: "result", title: "Aggregate diagnostic scores", detail: "Answers never enter a model prompt" },
]

export default function PipelineDiagram() {
  const { data: s } = useData(api.summary)
  if (!s) return <Skeleton className="h-[40rem] rounded-3xl bg-card" />
  return (
    <div data-testid="pipeline-diagram">
      <h2 className="text-xl">How the pipeline runs</h2>
      <Reflection className="mt-2">
        Code owns every ID, hash, count and check; the models only answer bounded questions. Dashed boxes mark what is not
        a program stage: the issue grouping and the blind verifier were agent handoffs, saved and audited after the fact.
      </Reflection>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="min-w-0">
          <h3 className="mb-3 text-[13px] tracking-[0.14em] text-muted-foreground uppercase">1 · Extraction and controls</h3>
          <Flow steps={extraction(s)} />
          <Controls items={[
            { title: "Atomic shared ledger", detail: "Reserves the worst-case cost before dispatch, then settles the real usage", acts: "both model stages" },
            { title: "Bounded workers and graceful stop", detail: "Saved queue state; a reviewed resume never resends a settled ID", acts: "the queue" },
          ]} />
        </div>
        <div className="min-w-0">
          <h3 className="mb-3 text-[13px] tracking-[0.14em] text-muted-foreground uppercase">2 · Grouping, publication and evaluation</h3>
          <Flow steps={analysis(s)} />
          <h3 className="mt-6 mb-3 text-[13px] tracking-[0.14em] text-muted-foreground uppercase">Evaluation, kept apart</h3>
          <Flow steps={EVALUATION} />
        </div>
      </div>
      <p className="mt-4 text-[13px] text-muted-foreground">
        Sources: <code className="text-foreground">docs/pipeline-extraction.mmd</code> and <code className="text-foreground">docs/pipeline-analysis.mmd</code>.
        The unchanged course checker still returns <code className="text-foreground">review_required</code> for the full-corpus scope.
      </p>
    </div>
  )
}
