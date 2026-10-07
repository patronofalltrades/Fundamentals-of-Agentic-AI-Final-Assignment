import { Check } from "lucide-react"

import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { api, type Summary } from "@/lib/api"
import { cn } from "@/lib/utils"
import { useData } from "./use-data"

function stages(s: Summary) {
  const c = s.coverage
  return [
    { name: "Ingest", done: c.source_rows > 0 },
    { name: "Classify", done: c.completed_rows > 0 && c.completed_rows >= c.nonempty_rows },
    { name: "Verify", done: s.quality.blind_verifier !== "pending" },
    { name: "Group", done: s.analysis.grouping === "accepted" },
    { name: "Rank", done: s.analysis.ranking !== "pending" },
    { name: "Memo", done: s.analysis.memo === "claims_checked" },
  ]
}

export default function Readiness() {
  const { data: s } = useData(api.summary)
  if (!s) return <Skeleton className="h-44 rounded-3xl bg-card" />
  const list = stages(s)
  const done = list.filter((x) => x.done).length
  return (
    <section className="rounded-3xl bg-card p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-xl">Pipeline readiness</h2>
        <p className="text-[15px]"><span className="tabular-nums">{done} of {list.length}</span> <span className="text-muted-foreground">stages</span></p>
      </div>
      <Progress value={(done / list.length) * 100} aria-label="Pipeline readiness" className="mt-8 h-1.5 bg-track [&>div]:bg-primary" />
      <ol className="mt-4 flex flex-wrap justify-between gap-x-3 gap-y-2 text-[13px]">
        {list.map((stage) => (
          <li key={stage.name} className={cn("flex items-center gap-1", stage.done ? "text-foreground" : "text-muted-foreground")}>
            {stage.done && <Check className="size-3.5 text-primary" aria-hidden="true" />}
            {stage.name}
            <span className="sr-only">{stage.done ? "done" : "pending"}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}
