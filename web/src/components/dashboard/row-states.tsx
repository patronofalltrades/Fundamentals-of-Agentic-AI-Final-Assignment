import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { api, fmt, ROW_STATES } from "@/lib/api"
import { cn } from "@/lib/utils"
import { STATE_TONE } from "./review-detail"
import { useData } from "./use-data"

const BAR: Record<string, string> = {
  accepted: "bg-primary", quarantined: "bg-negative", unresolved: "bg-chart-2", empty: "bg-muted-foreground", pending: "bg-chart-3",
}

/** Every selected review in exactly one state, plus a lookup that opens a review link. */
export default function RowStates() {
  const { data: s } = useData(api.summary)
  const [row, setRow] = useState("")
  if (!s) return <Skeleton className="h-40 rounded-3xl bg-card" />
  if (!s.states) return null
  const total = Object.values(s.states).reduce((a, b) => a + b, 0)
  const last = total - 1
  const open = (e: React.FormEvent) => {
    e.preventDefault()
    const n = Number(row)
    if (Number.isInteger(n) && n >= 0 && n <= last) window.location.hash = `review-${n}`
  }
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
        {ROW_STATES.map((x) => (
          <li key={x.key} className="rounded-2xl bg-tile p-3" data-state={x.key}>
            <span className={cn("rounded-full px-2 py-0.5 text-[12px]", STATE_TONE[x.key])}>{x.label}</span>
            <p className="mt-2 text-[1.35rem] leading-none font-light tabular-nums">{fmt.int(s.states![x.key])}</p>
            <p className="mt-1 text-[12px] text-muted-foreground">{x.help}</p>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex flex-col gap-3 text-[13px] text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <p>
          {s.representative_exclusions ?? 0} accepted reviews carry a known semantic flag and never appear as examples.
          {s.import && <> Imported {new Date(s.import.imported_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })} · handoff <span className="font-mono">{s.import.handoff_sha256.slice(0, 12)}</span></>}
        </p>
        <form onSubmit={open} className="flex shrink-0 items-center gap-2" aria-label="Open a review by row">
          <Input inputMode="numeric" value={row} onChange={(e) => setRow(e.target.value.replace(/[^0-9]/g, ""))}
            placeholder={`Row 0–${fmt.int(last)}`} aria-label="Row number" className="h-9 w-36 rounded-full bg-tile" />
          <Button type="submit" variant="secondary" size="sm" className="rounded-full">Open</Button>
        </form>
      </div>
    </section>
  )
}
