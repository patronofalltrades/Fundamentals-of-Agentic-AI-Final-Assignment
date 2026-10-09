import { Badge } from "@/components/ui/badge"
import { api, fmt } from "@/lib/api"
import { useData } from "./use-data"

/** Small live line under the hero headline: data scope and memo state. */
export default function HeroStatus() {
  const { data: s } = useData(api.summary)
  if (!s) return <p className="h-6" aria-hidden="true" />
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {s.target.is_demo && (
        <Badge variant="secondary" className="rounded-full bg-chart-2/12 font-normal text-chart-2">
          Demo data · {fmt.int(s.coverage.source_rows)} of {fmt.int(s.target.minimum_source_rows)} reviews
        </Badge>
      )}
      {!s.target.is_demo && s.import && (
        <Badge variant="secondary" className="rounded-full bg-white/8 font-normal">
          Development checkpoint · {fmt.int(s.import.selected_rows)} reviews
        </Badge>
      )}
      <Badge variant="secondary" className="rounded-full bg-white/8 font-normal">
        Memo: {s.analysis.memo === "claims_checked" ? "checked" : fmt.label(s.analysis.memo)}
      </Badge>
    </div>
  )
}
