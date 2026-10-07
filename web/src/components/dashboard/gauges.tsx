import { PolarAngleAxis, RadialBar, RadialBarChart } from "recharts"

import { ChartContainer, type ChartConfig } from "@/components/ui/chart"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { useData } from "./use-data"

function Gauge({ ratio, display, label }: { ratio: number | null; display: string; label: string }) {
  const config = { value: { label } } satisfies ChartConfig
  return (
    <div className="relative size-36 shrink-0" role="img" aria-label={`${label}: ${display}`}>
      <ChartContainer config={config} className="aspect-square size-36">
        <RadialBarChart data={[{ value: ratio ?? 0 }]} startAngle={225} endAngle={-45} innerRadius="80%" outerRadius="100%" barSize={10}>
          <PolarAngleAxis type="number" domain={[0, 1]} tick={false} axisLine={false} />
          <RadialBar dataKey="value" cornerRadius={10} fill="var(--primary)" background={{ fill: "var(--track)" }} isAnimationActive={false} />
        </RadialBarChart>
      </ChartContainer>
      <span className="absolute inset-0 grid place-items-center text-[2rem] font-light tabular-nums">{display}</span>
    </div>
  )
}

function Panel({ title, subtitle, foot, gauge }: { title: string; subtitle: string; foot: React.ReactNode; gauge: React.ReactNode }) {
  return (
    <section className="flex items-center justify-between gap-4 rounded-3xl bg-card p-6">
      <div className="min-w-0 space-y-2">
        <h2 className="text-xl">{title}</h2>
        <p className="text-[15px] text-muted-foreground">{subtitle}</p>
        <p className="pt-4 text-[13px] text-muted-foreground">{foot}</p>
      </div>
      {gauge}
    </section>
  )
}

export default function Gauges() {
  const { data: s } = useData(api.summary)
  if (!s) return <div className="space-y-6">{[0, 1].map((i) => <Skeleton key={i} className="h-44 rounded-3xl bg-card" />)}</div>
  const sets = s.evaluation.status === "saved" ? s.evaluation.sets : {}
  const chosen = sets["adjudicated"] ?? sets["original"] ?? Object.values(sets)[0]
  const joint = chosen?.agreement.joint ?? null
  const top = s.top_issue
  return (
    <div className="space-y-6">
      <Panel
        title="Golden agreement"
        subtitle={chosen ? `All three labels match the human labels (${chosen.label_set} set)` : "Pending a saved evaluation of these labels"}
        foot={chosen ? <>Topic {chosen.agreement.topic ?? "—"} · intent {chosen.agreement.intent ?? "—"} · {chosen.approved_cases} cases</> : "Scored against the 50 human golden labels"}
        gauge={<Gauge ratio={joint} display={joint === null ? "—" : joint.toFixed(2)} label="Golden agreement" />}
      />
      <Panel
        title="Top issue severity"
        subtitle={top ? (top.title !== top.issue_id ? top.title : top.issue_id.replace(/^issue-/, "")) : "Pending the accepted issue ranking"}
        foot={top ? <>Mean of {top.complaint_count} complaints · scale 1–5</> : "Mean severity of the rank-1 issue"}
        gauge={<Gauge ratio={top ? (Number(top.mean_severity) - 1) / 4 : null} display={top ? Number(top.mean_severity).toFixed(1) : "—"} label="Top issue mean severity" />}
      />
    </div>
  )
}
