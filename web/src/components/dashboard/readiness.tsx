import { Check, CircleDashed } from "lucide-react"

import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { api, fmt, type Summary } from "@/lib/api"
import { cn } from "@/lib/utils"
import { useData } from "./use-data"

type Stage = { name: string; state: "done" | "sample" | "pending" }

function stages(s: Summary): Stage[] {
  const c = s.coverage
  const state = (done: boolean): Stage["state"] => (done ? "done" : "pending")
  // The blind verifier checked a sample of the issue map. Its result is in the memo, not in this database.
  const verify = s.quality.blind_verifier !== "pending" ? "done" : s.analysis.grouping === "accepted" ? "sample" : "pending"
  return [
    { name: "Ingest", state: state(c.source_rows > 0) },
    { name: "Classify", state: state(c.completed_rows >= s.target.minimum_source_rows) },
    { name: "Verify", state: verify },
    { name: "Group", state: state(s.analysis.grouping === "accepted") },
    { name: "Rank", state: state(s.analysis.ranking !== "pending") },
    { name: "Memo", state: state(s.analysis.memo === "claims_checked" || s.analysis.memo === "claims_checked_provisional") },
  ]
}

export default function Readiness() {
  const { data: s } = useData(api.summary)
  if (!s) return <Skeleton className="h-44 rounded-3xl bg-card" />
  const list = stages(s)
  const done = list.filter((x) => x.state === "done").length
  const sampled = list.some((x) => x.state === "sample")
  return (
    <section className="rounded-3xl bg-card p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-xl">Pipeline readiness</h2>
        <p className="text-[15px]"><span className="tabular-nums">{done} of {list.length}</span> <span className="text-muted-foreground">stages</span></p>
      </div>
      <Progress value={(done / list.length) * 100} aria-label="Pipeline readiness" className="mt-8 h-1.5 bg-track [&>div]:bg-primary" />
      <ol className="mt-4 flex flex-wrap justify-between gap-x-3 gap-y-2 text-[13px]">
        {list.map((stage) => (
          <li key={stage.name} className={cn("flex items-center gap-1", stage.state === "pending" ? "text-muted-foreground" : "text-foreground")}>
            {stage.state === "done" && <Check className="size-3.5 text-primary" aria-hidden="true" />}
            {stage.state === "sample" && <CircleDashed className="size-3.5 text-chart-3" aria-hidden="true" />}
            {stage.name}
            <span className="sr-only">{stage.state === "sample" ? "sample only" : stage.state}</span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-[13px] text-muted-foreground">
        Classify counts {fmt.int(s.coverage.completed_rows)} accepted reviews against the {fmt.int(s.target.minimum_source_rows)} minimum.
        {sampled && " Verify ran on a sample: a blind second model checked 600 issue assignments (see the memo's confidence section)."}
      </p>
    </section>
  )
}
