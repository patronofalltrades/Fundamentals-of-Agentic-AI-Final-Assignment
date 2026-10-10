import { Skeleton } from "@/components/ui/skeleton"
import { api, fmt, REASON_LABELS, ROW_STATES } from "@/lib/api"
import { cn } from "@/lib/utils"
import { STATE_TONE } from "./review-detail"
import { useData } from "./use-data"

const BAR: Record<string, string> = {
  accepted: "bg-primary", quarantined: "bg-negative", unresolved: "bg-chart-2", empty: "bg-muted-foreground", pending: "bg-chart-3",
}

/** Every selected review in exactly one state. Nonaccepted reviews appear only as category counts. */
export default function RowStates() {
  const { data: s } = useData(api.summary)
  if (!s) return <Skeleton className="h-40 rounded-3xl bg-card" />
  if (!s.states) return null
  const total = Object.values(s.states).reduce((a, b) => a + b, 0)
  const candidates = s.import?.issue_candidates
  return (
    <section className="rounded-3xl bg-card p-6" aria-labelledby="row-states-title">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="row-states-title" className="text-xl">Review states</h2>
        <p className="text-[15px] tabular-nums">{fmt.int(total)} <span className="text-muted-foreground">selected reviews</span></p>
      </div>
      <p className="mt-1 text-[15px] text-muted-foreground">Only accepted reviews enter the labels and trends. Pending reviews await a label; they are not failures.</p>
      <div className="mt-5 flex h-2.5 w-full overflow-hidden rounded-full bg-track" role="img"
        aria-label={ROW_STATES.map((x) => `${x.label} ${fmt.int(s.states![x.key])}`).join(", ")}>
        {ROW_STATES.map((x) => s.states![x.key] > 0 && (
          <span key={x.key} className={cn("h-full min-w-[3px]", BAR[x.key])} style={{ width: `${(s.states![x.key] / total) * 100}%` }} />
        ))}
      </div>
      <ul className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-5" data-testid="state-counts">
        {ROW_STATES.map((x) => {
          const categories = Object.entries(s.reason_categories?.[x.key] ?? {}).sort((a, b) => b[1] - a[1])
          return (
            <li key={x.key} className="rounded-2xl bg-tile p-3" data-state={x.key}>
              <span className={cn("rounded-full px-2 py-0.5 text-[12px]", STATE_TONE[x.key])}>{x.label}</span>
              <p className="mt-2 text-[1.35rem] leading-none font-light tabular-nums">{fmt.int(s.states![x.key])}</p>
              <p className="mt-1 text-[12px] text-muted-foreground">{x.help}</p>
              {categories.length > 1 && (
                <ul className="mt-2 space-y-0.5 text-[12px]" data-testid="reason-categories">
                  {categories.map(([key, n]) => (
                    <li key={key} className="flex justify-between gap-2">
                      <span className="text-muted-foreground">{REASON_LABELS[key] ?? fmt.label(key)}</span>
                      <span className="tabular-nums">{fmt.int(n)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          )
        })}
      </ul>
      <div className="mt-4 space-y-1 text-[13px] text-muted-foreground">
        <p>
          {fmt.int(s.representative_exclusions ?? 0)} accepted reviews carry a known semantic flag. They stay in the accepted total but never appear as examples or in issue rankings. No accepted review has had human validation.
        </p>
        {candidates && (
          <p data-testid="issue-candidates">
            Issue candidates: {fmt.int(candidates.public_projection)} complaint or cancellation reviews for public rankings, out of {fmt.int(candidates.contract_baseline)} in the course baseline ({fmt.int(candidates.flagged_excluded)} flagged). No issue catalog or ranking has been saved yet.
          </p>
        )}
        {s.import && (
          <p>Imported {new Date(s.import.imported_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })} · handoff <span className="font-mono">{s.import.handoff_sha256.slice(0, 12)}</span></p>
        )}
      </div>
    </section>
  )
}
