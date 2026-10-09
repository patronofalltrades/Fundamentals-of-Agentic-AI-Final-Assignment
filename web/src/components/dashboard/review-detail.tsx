import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { api, fmt, ROW_STATES, type ReviewDetail as Detail } from "@/lib/api"
import { cn } from "@/lib/utils"

export const STATE_TONE: Record<string, string> = {
  accepted: "bg-primary/15 text-primary",
  quarantined: "bg-negative/15 text-negative",
  unresolved: "bg-chart-2/15 text-chart-2",
  empty: "bg-tile text-muted-foreground",
  pending: "bg-chart-3/15 text-chart-3",
}

export function StateBadge({ state }: { state: string }) {
  const label = ROW_STATES.find((s) => s.key === state)?.label ?? fmt.label(state)
  return <Badge variant="secondary" className={cn("rounded-full font-normal", STATE_TONE[state])}>{label}</Badge>
}

/** One saved row, any state. Labels appear only for accepted rows. The review text is never shown. */
export function ReviewDetail({ row, showQuote = false }: { row: number; showQuote?: boolean }) {
  const [state, setState] = useState<{ detail?: Detail; missing?: boolean }>({})
  useEffect(() => {
    setState({})
    api.review(row).then((detail) => setState({ detail })).catch(() => setState({ missing: true }))
  }, [row])
  if (state.missing) return <p role="alert" className="mt-3 text-[13px] text-negative">No saved row {fmt.int(row)}.</p>
  const d = state.detail
  if (!d) return <Skeleton className="mt-3 h-14 rounded-xl bg-canvas/60" />
  const accepted = !d.state || d.state === "accepted"
  return (
    <div className="mt-3 space-y-2 rounded-xl bg-canvas/60 p-3 text-[13px]" data-testid="review-detail" data-state={d.state ?? "accepted"}>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-muted-foreground">Row {fmt.int(d.row_index)}</span>
        {d.state && <StateBadge state={d.state} />}
        {d.representative_blocked && (
          <Badge variant="secondary" className="rounded-full bg-negative/15 font-normal text-negative">Known semantic flag · not an example</Badge>
        )}
      </div>
      {accepted ? (
        <>
          {showQuote && d.evidence_quote && <blockquote className="text-[15px] leading-6 break-words">“{d.evidence_quote}”</blockquote>}
          <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
            <div><dt className="inline text-muted-foreground">Labels </dt><dd className="inline">{d.topic} · {d.intent} · severity {d.severity}</dd></div>
            <div><dt className="inline text-muted-foreground">Sentiment </dt><dd className="inline tabular-nums">{d.sentiment ?? "—"}</dd></div>
            <div><dt className="inline text-muted-foreground">Model </dt><dd className="inline">{d.model ?? "unknown"} · {d.prompt_version ?? "unknown"}</dd></div>
            {d.flag_categories && d.flag_categories.length > 0 && (
              <div><dt className="inline text-muted-foreground">Flag </dt><dd className="inline">{d.flag_categories.map(fmt.label).join(", ")}</dd></div>
            )}
          </dl>
        </>
      ) : (
        <dl className="grid gap-y-1">
          <div><dt className="inline text-muted-foreground">Saved state </dt><dd className="inline">{fmt.label(d.source_state ?? d.state ?? "")}</dd></div>
          <div><dt className="inline text-muted-foreground">Reason </dt><dd className="inline break-words">{d.reason ?? "—"}</dd></div>
          <div className="text-muted-foreground">No labels: only accepted rows carry labels and enter the totals.</div>
        </dl>
      )}
      <p className="break-all text-muted-foreground">Source row hash <span className="font-mono text-[12px] text-foreground">{d.source_sha256}</span></p>
    </div>
  )
}
