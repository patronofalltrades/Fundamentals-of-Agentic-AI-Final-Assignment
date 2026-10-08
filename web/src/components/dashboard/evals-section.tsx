import { Check, Circle, ExternalLink, X } from "lucide-react"

import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, fmt, type EvalCheck, type EvalItem, type EvalMetric, type EvaluationSet, type Evals } from "@/lib/api"
import { REFLECTIONS } from "@/lib/reflections"
import { cn } from "@/lib/utils"
import { LoadError, Reflection } from "./bits"
import { useData } from "./use-data"

const REPO = "https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/blob/main/"

const STATUS: Record<string, { label: string; className: string; help: string }> = {
  measured: { label: "Measured", className: "bg-primary/15 text-primary", help: "Read from a saved run report" },
  partial: { label: "Partial", className: "bg-chart-2/15 text-chart-2", help: "Some of the sample is done" },
  estimate: { label: "Estimate", className: "bg-chart-3/15 text-chart-3", help: "Projected, not measured" },
  pending: { label: "Pending", className: "bg-tile text-muted-foreground", help: "Not run or not saved yet" },
}

function StatusChip({ status }: { status: string }) {
  const s = STATUS[status] ?? STATUS.pending
  return <span className={cn("shrink-0 rounded-full px-3 py-1 text-[12px]", s.className)}>{s.label}</span>
}

function MetricTile({ m }: { m: EvalMetric }) {
  const value = fmt.value(m.value, m.format === "count" ? "int" : m.format)
  return (
    <div className="rounded-2xl bg-tile p-4">
      <p className="text-[13px] text-muted-foreground">{m.label}</p>
      <p className="mt-1 text-[1.6rem] leading-none font-light tabular-nums">
        {value}
        {m.of !== undefined && <span className="text-[15px] text-muted-foreground"> / {fmt.int(m.of)}</span>}
      </p>
      {m.note && <p className="mt-2 text-[12px] text-muted-foreground">{m.note}</p>}
    </div>
  )
}

function Facts({ item }: { item: EvalItem }) {
  return (
    <dl className="grid gap-3 text-[14px] sm:grid-cols-2">
      <div>
        <dt className="text-[12px] tracking-[0.12em] text-muted-foreground uppercase">Sample</dt>
        <dd className="mt-1">{item.sample}</dd>
      </div>
      <div>
        <dt className="text-[12px] tracking-[0.12em] text-muted-foreground uppercase">Compared against</dt>
        <dd className="mt-1">{item.truth}</dd>
      </div>
    </dl>
  )
}

function EvalCard({ item }: { item: EvalItem }) {
  return (
    <article className="flex min-w-0 flex-col gap-5 rounded-3xl bg-card p-6">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-lg">{item.title}</h3>
          <p className="mt-1 text-[15px] text-muted-foreground">{item.question}</p>
        </div>
        <StatusChip status={item.status} />
      </header>
      <Facts item={item} />
      {item.metrics.length > 0 && (
        <div className={cn("grid gap-3", item.metrics.length === 3 ? "sm:grid-cols-3" : "grid-cols-2 lg:grid-cols-4")}>
          {item.metrics.map((m) => <MetricTile key={m.label} m={m} />)}
        </div>
      )}
      {item.compare && (
        <div className="overflow-x-auto rounded-2xl bg-tile/50">
          <Table>
            <TableHeader>
              <TableRow className="border-0 hover:bg-transparent">
                <TableHead className="text-muted-foreground">Measure</TableHead>
                {item.compare.columns.map((c) => <TableHead key={c} className="text-right text-muted-foreground">{c}</TableHead>)}
              </TableRow>
            </TableHeader>
            <TableBody>
              {item.compare.rows.map((row) => (
                <TableRow key={row.label} className="border-border/60">
                  <TableCell>
                    {row.label}
                    {row.note && <span className="block text-[12px] text-muted-foreground">{row.note}</span>}
                  </TableCell>
                  {row.values.map((v, i) => <TableCell key={i} className="text-right tabular-nums">{fmt.value(v, row.format)}</TableCell>)}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {item.decision && (
        <p className="rounded-2xl border-l-2 border-primary bg-primary/5 px-4 py-3 text-[14px]">
          <span className="text-primary">Decision · </span>{item.decision}
        </p>
      )}
      <footer className="mt-auto space-y-3">
        {item.limits.length > 0 && (
          <details className="group rounded-2xl bg-tile/50 px-4 py-3 text-[14px]">
            <summary className="cursor-pointer text-muted-foreground marker:text-track group-open:text-foreground">
              What this does not show ({item.limits.length})
            </summary>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
              {item.limits.map((l) => <li key={l}>{l}</li>)}
            </ul>
          </details>
        )}
        {item.sources.length > 0 && (
          <p className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-muted-foreground">
            Source:
            {item.sources.map((s) => (
              <a key={s} href={REPO + s} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline decoration-track underline-offset-4 hover:text-foreground">
                {s.replace(/^reports\//, "")}<ExternalLink className="size-3" aria-hidden="true" />
              </a>
            ))}
          </p>
        )}
      </footer>
    </article>
  )
}

const GOLDEN_FIELDS = [
  { key: "topic", label: "Topic" },
  { key: "intent", label: "Intent" },
  { key: "severity", label: "Severity" },
  { key: "joint", label: "All three" },
] as const

/** Prefer the original human set: the adjudicated set was revised after seeing model output. */
function chooseSet(golden: Evals["golden"]): EvaluationSet | undefined {
  if (golden.status !== "saved") return undefined
  return golden.sets["original"] ?? Object.values(golden.sets).find((s) => s.official) ?? Object.values(golden.sets)[0]
}

function GoldenCard({ golden }: { golden: Evals["golden"] }) {
  const set = chooseSet(golden)
  return (
    <article className="flex min-w-0 flex-col gap-5 rounded-3xl bg-card p-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[12px] tracking-[0.12em] text-primary uppercase">Accuracy</p>
          <h3 className="mt-1 text-lg">Human golden evaluation</h3>
          <p className="mt-1 text-[15px] text-muted-foreground">How often do the model's labels match labels written by a person?</p>
        </div>
        <StatusChip status={set ? "measured" : "pending"} />
      </header>
      <dl className="grid gap-3 text-[14px] sm:grid-cols-2">
        <div>
          <dt className="text-[12px] tracking-[0.12em] text-muted-foreground uppercase">Sample</dt>
          <dd className="mt-1">50 reviews. A person wrote every label without seeing model output.</dd>
        </div>
        <div>
          <dt className="text-[12px] tracking-[0.12em] text-muted-foreground uppercase">Scorer</dt>
          <dd className="mt-1">The course checker (<code className="text-[13px]">check_submission.py score_gold</code>), unchanged.</dd>
        </div>
      </dl>
      <div className="space-y-4">
        {GOLDEN_FIELDS.map(({ key, label }) => {
          const v = set?.agreement[key] ?? null
          return (
            <div key={key}>
              <div className="flex items-baseline justify-between text-[14px]">
                <span className={key === "joint" ? "text-foreground" : "text-muted-foreground"}>{label}</span>
                <span className="tabular-nums">{v === null ? "—" : fmt.pct(v)}</span>
              </div>
              <Progress value={v === null ? 0 : v * 100} aria-label={`${label} agreement`} className="mt-2 h-1.5 bg-track [&>div]:bg-primary" />
            </div>
          )
        })}
      </div>
      <p className="text-[13px] text-muted-foreground">
        {set
          ? <>Severity error (mean absolute): <span className="text-foreground tabular-nums">{set.severity_mae_on_valid_predictions?.toFixed(2) ?? "—"}</span> on a 1–5 scale · {set.approved_cases} of {set.total_cases} cases scored · {set.missing_or_invalid_predictions} missing or invalid</>
          : "The labels are written. The score appears here when the model's predictions for these 50 reviews are saved and scored. No sample numbers are shown."}
      </p>
    </article>
  )
}

const CHECK_ICON = {
  passed: <Check className="size-4 text-primary" aria-hidden="true" />,
  failed: <X className="size-4 text-negative" aria-hidden="true" />,
  pending: <Circle className="size-3.5 text-track" aria-hidden="true" />,
}

function ChecksCard({ checks }: { checks: EvalCheck[] }) {
  const passed = checks.filter((c) => c.status === "passed").length
  return (
    <article className="flex min-w-0 flex-col gap-5 rounded-3xl bg-card p-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[12px] tracking-[0.12em] text-primary uppercase">Integrity</p>
          <h3 className="mt-1 text-lg">Automatic checks on this page's data</h3>
          <p className="mt-1 text-[15px] text-muted-foreground">Run by the server on every request, against the live database.</p>
        </div>
        <span className="shrink-0 text-[15px] tabular-nums">{passed} of {checks.length}</span>
      </header>
      <ul className="divide-y divide-border/60">
        {checks.map((c) => (
          <li key={c.name} className="flex gap-3 py-3">
            <span className="mt-0.5 grid size-5 shrink-0 place-items-center">{CHECK_ICON[c.status]}</span>
            <div className="min-w-0">
              <p className="text-[15px]">{c.name} <span className="sr-only">: {c.status}</span></p>
              <p className="text-[13px] text-muted-foreground">{c.detail}</p>
            </div>
            <span className="ml-auto shrink-0 text-[12px] text-muted-foreground capitalize">{c.status}</span>
          </li>
        ))}
      </ul>
    </article>
  )
}

export default function EvalsSection() {
  const { data, error } = useData(api.evals)
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 rounded-3xl bg-card p-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-[62ch]">
          <h2 className="text-xl">Evaluations and benchmarks</h2>
          <Reflection className="mt-3">{REFLECTIONS.evals}</Reflection>
          <p className="mt-3 text-[12px] text-muted-foreground">Every number below is read from a saved, linked report.</p>
        </div>
        <ul className="flex flex-wrap gap-2" aria-label="Status key">
          {Object.entries(STATUS).map(([key, s]) => (
            <li key={key} title={s.help} className={cn("rounded-full px-3 py-1 text-[12px]", s.className)}>{s.label}<span className="sr-only">: {s.help}</span></li>
          ))}
        </ul>
      </div>
      {error && <LoadError message={error} />}
      {!data && !error && <Skeleton className="h-96 rounded-3xl bg-card" />}
      {data && (
        <>
          <div className="grid gap-6 xl:grid-cols-2">
            <GoldenCard golden={data.golden} />
            <ChecksCard checks={data.checks} />
          </div>
          <div className="grid gap-6 xl:grid-cols-2">
            {data.items.map((item) => <EvalCard key={item.id} item={item} />)}
          </div>
          {data.model && (
            <p className="px-2 text-[13px] text-muted-foreground">
              Labelling model: {data.model} · production prompt: {data.prompt_version} · built from {data.built_from?.length ?? 0} fingerprinted reports
            </p>
          )}
        </>
      )}
    </div>
  )
}
