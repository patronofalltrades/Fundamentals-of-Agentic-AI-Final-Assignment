import { Area, AreaChart, ReferenceDot, XAxis, YAxis } from "recharts"
import { CalendarRange } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Skeleton } from "@/components/ui/skeleton"
import { api, fmt, type Summary } from "@/lib/api"
import { Leader, LoadError, PendingNote } from "./bits"
import { useData } from "./use-data"

type Point = { month: string; value: number | null }

function Spark({ id, data, color, label }: { id: string; data: Point[]; color: string; label: string }) {
  const config = { value: { label } } satisfies ChartConfig // no colours here: they come from CSS variables
  const values = data.map((d) => d.value).filter((v): v is number => v !== null)
  const peak = data.reduce<Point | null>((best, d) => (d.value !== null && (!best || d.value > (best.value ?? -1)) ? d : best), null)
  const last = [...data].reverse().find((d) => d.value !== null) ?? null
  return (
    <ChartContainer config={config} className="aspect-auto h-full min-h-24 w-full">
      <AreaChart data={data} margin={{ top: 10, right: 6, bottom: 4, left: 6 }}>
        <defs>
          <linearGradient id={`fill-${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" style={{ stopColor: color, stopOpacity: 0.28 }} />
            <stop offset="100%" style={{ stopColor: color, stopOpacity: 0 }} />
          </linearGradient>
        </defs>
        <XAxis dataKey="month" hide />
        <YAxis hide domain={[Math.min(...values) * 0.85, Math.max(...values) * 1.08]} />
        <ChartTooltip cursor={false} content={<ChartTooltipContent hideIndicator labelFormatter={(_, p) => fmt.month(String(p?.[0]?.payload?.month ?? ""))} />} />
        <Area dataKey="value" type="monotone" stroke={color} strokeWidth={1.6} fill={`url(#fill-${id})`} connectNulls isAnimationActive={false} />
        {peak && <ReferenceDot x={peak.month} y={peak.value ?? 0} r={3.5} fill="var(--tile)" stroke={color} strokeWidth={1.5} ifOverflow="visible" />}
        {last && last !== peak && <ReferenceDot x={last.month} y={last.value ?? 0} r={3.5} fill="var(--tile)" stroke={color} strokeWidth={1.5} ifOverflow="visible" />}
      </AreaChart>
    </ChartContainer>
  )
}

function Tile({ title, value, children, chart }: { title: string; value: string; children: React.ReactNode; chart: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col rounded-2xl bg-gradient-to-b from-tile to-tile/60 p-4">
      <h3 className="text-[15px] text-foreground">{title}</h3>
      <div className="-mx-4 mt-2 flex min-h-24 flex-1">{chart}</div>
      <p className="mt-2 text-[2rem] leading-none font-light tracking-tight tabular-nums">{value}</p>
      <div className="mt-4 space-y-2">{children}</div>
    </div>
  )
}

function tiles(s: Summary) {
  const t = s.trends
  if (!t) return null
  const totalComplaints = t.complaints.reduce((a, b) => a + b, 0)
  const weighted = t.mean_severity.reduce((acc, m, i) => acc + (m === null ? 0 : Number(m) * t.complaints[i]), 0)
  const mean = totalComplaints ? weighted / totalComplaints : null
  const peakIndex = t.complaints.indexOf(Math.max(...t.complaints))
  const series = (values: (number | string | null)[]) => t.months.map((month, i) => ({ month, value: values[i] === null ? null : Number(values[i]) }))
  return { t, totalComplaints, mean, peakIndex, series }
}

export default function KpiTiles() {
  const { data: s, error } = useData(api.summary)
  if (error) return <LoadError message={error} />
  if (!s) return <div className="grid gap-4 md:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-72 rounded-2xl bg-tile" />)}</div>
  const k = tiles(s)
  const range = k ? `${fmt.month(k.t.months[0])} – ${fmt.month(k.t.months[k.t.months.length - 1])}` : null
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xl">Review activity</h2>
        {range && (
          <Badge variant="secondary" className="gap-1.5 rounded-full px-3 py-1 text-[13px] font-normal">
            <CalendarRange className="size-3.5" aria-hidden="true" />
            {range}
          </Badge>
        )}
      </div>
      {!k ? (
        <PendingNote>Monthly trends are not saved in this database yet. Reload the bundle to add them.</PendingNote>
      ) : (
        <div className="grid flex-1 gap-4 md:grid-cols-3">
          <Tile title="Source reviews" value={fmt.int(s.coverage.source_rows)}
            chart={<Spark id="reviews" label="Reviews" color="var(--chart-1)" data={k.series(k.t.reviews)} />}>
            <Leader label="Target" value={fmt.int(s.target.minimum_source_rows)} />
            <Leader label="Coverage" value={fmt.pct(s.coverage.source_rows / s.target.minimum_source_rows, 1)} />
          </Tile>
          <Tile title="Complaints" value={fmt.int(k.totalComplaints)}
            chart={<Spark id="complaints" label="Complaints" color="var(--chart-2)" data={k.series(k.t.complaints)} />}>
            <Leader label="Share of reviews" value={fmt.pct(k.totalComplaints / s.coverage.completed_rows)} />
            <Leader label="Peak month" value={fmt.month(k.t.months[k.peakIndex])} />
          </Tile>
          <Tile title="Mean severity" value={k.mean === null ? "—" : k.mean.toFixed(2)}
            chart={<Spark id="severity" label="Mean severity" color="var(--chart-3)" data={k.series(k.t.mean_severity)} />}>
            <Leader label="Scale" value="1 – 5" />
            <Leader label="Complaints only" value="yes" />
          </Tile>
        </div>
      )}
    </div>
  )
}
