import { Copy, ScanSearch } from "lucide-react"

import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { api, fmt } from "@/lib/api"
import { useData } from "./use-data"

function Item({ icon, label, value, ratio }: { icon: React.ReactNode; label: string; value: string; ratio: number }) {
  return (
    <div className="flex min-w-0 flex-1 items-center gap-3">
      <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-tile text-foreground">{icon}</span>
      <div className="min-w-0">
        <p className="text-[13px] text-muted-foreground">{label}</p>
        <p className="truncate text-[15px] tabular-nums">{value}</p>
      </div>
      <Progress value={Math.min(100, ratio * 100)} aria-label={label} className="ml-auto h-1.5 w-28 shrink-0 bg-track [&>div]:bg-primary" />
    </div>
  )
}

export default function ProgressStrip() {
  const { data: s } = useData(api.summary)
  if (!s) return <Skeleton className="h-20 rounded-3xl bg-card" />
  const c = s.coverage
  return (
    <div className="flex flex-col gap-4 rounded-3xl bg-card p-4 md:flex-row md:items-center md:gap-6 md:px-6">
      <Item icon={<ScanSearch className="size-4" aria-hidden="true" />} label="Classified toward the minimum"
        value={`${fmt.int(c.completed_rows)} of ${fmt.int(s.target.minimum_source_rows)}`} ratio={c.completed_rows / s.target.minimum_source_rows} />
      <span className="hidden h-10 w-px bg-border md:block" aria-hidden="true" />
      <Item icon={<Copy className="size-4" aria-hidden="true" />} label="Distinct texts sent to the model"
        value={`${fmt.int(c.distinct_nonempty_texts)} of ${fmt.int(c.nonempty_rows)} reviews`} ratio={c.nonempty_rows ? c.distinct_nonempty_texts / c.nonempty_rows : 0} />
    </div>
  )
}
