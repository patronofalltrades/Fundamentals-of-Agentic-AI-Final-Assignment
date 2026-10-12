import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { api, fmt, ROW_STATES, type ReviewDetail as Detail, type ReviewItem } from "@/lib/api"
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

/** The quote a visitor may see: the bounded excerpt, marked when shortened, or the older full quote. */
export function Quote({ item, className }: { item: ReviewItem; className?: string }) {
  const text = item.excerpt ?? item.evidence_quote ?? ""
  return (
    <blockquote className={cn("text-[15px] leading-6 break-words", className)}>
      “{text}”
      {item.shortened && <span className="ml-1.5 text-[12px] text-muted-foreground" data-testid="shortened">(shortened)</span>}
    </blockquote>
  )
}

/** One public example. Labels and a bounded excerpt only; the review text is never shown. */
export function ReviewDetail({ id, showQuote = false }: { id: string; showQuote?: boolean }) {
  const [state, setState] = useState<{ detail?: Detail; missing?: boolean }>({})
  useEffect(() => {
    setState({})
    api.review(id).then((detail) => setState({ detail })).catch(() => setState({ missing: true }))
  }, [id])
  if (state.missing) return <p role="alert" className="mt-3 text-[13px] text-negative">This review link does not match a public example.</p>
  const d = state.detail
  if (!d) return <Skeleton className="mt-3 h-14 rounded-xl bg-canvas/60" />
  return (
    <div className="mt-3 space-y-2 rounded-xl bg-canvas/60 p-3 text-[13px]" data-testid="review-detail" data-state={d.state ?? "accepted"}>
      <div className="flex flex-wrap items-center gap-1.5">
        {d.ref ? <span className="font-mono text-[12px] text-muted-foreground">{d.ref}</span>
          : <span className="text-muted-foreground">Row {fmt.int(d.row_index ?? 0)}</span>}
        {d.state && <StateBadge state={d.state} />}
        {d.human_validated === false && (
          <Badge variant="secondary" className="rounded-full bg-tile font-normal text-muted-foreground">Not human-validated</Badge>
        )}
      </div>
      {showQuote && <Quote item={d} />}
      <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
        <div><dt className="inline text-muted-foreground">Labels </dt><dd className="inline">{d.topic} · {d.intent} · severity {d.severity}</dd></div>
        <div><dt className="inline text-muted-foreground">Sentiment </dt><dd className="inline tabular-nums">{d.sentiment ?? "—"}</dd></div>
        <div><dt className="inline text-muted-foreground">Model </dt><dd className="inline">{d.model ?? "unknown"} · {d.prompt_version ?? "unknown"}</dd></div>
      </dl>
      {d.source_sha256 && (
        <p className="break-all text-muted-foreground">Source row hash <span className="font-mono text-[12px] text-foreground">{d.source_sha256}</span></p>
      )}
    </div>
  )
}
