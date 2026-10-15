import { useState } from "react"
import { Layer, Rectangle, ResponsiveContainer, Sankey, type SankeyLinkProps, type SankeyNodeProps } from "recharts"

import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, fmt, type Flow, type FlowNode } from "@/lib/api"
import { LoadError, PendingNote, Reflection } from "./bits"
import { useData } from "./use-data"

const MARGIN = { top: 8, right: 300, bottom: 8, left: 120 }
const NODE_WIDTH = 10
/** Headings start at each node column: x = left margin, then evenly spaced up to width - right margin - node width. */
const COLUMNS = [
  { name: "Intent", className: "left-[120px] -translate-x-full pr-2" },
  { name: "Topic", className: "left-[calc(50%-95px)]" },
  { name: "Issue", className: "left-[calc(100%-310px)]" },
]

/** Intent and topic labels are lower-case codes; issue titles are already in sentence case. */
const display = (n: FlowNode) => (n.column < 2 ? n.label.charAt(0).toUpperCase() + n.label.slice(1) : n.label)

/** One colour per node: intent by kind, topics neutral, leading issues in the accent, combined issues grey. */
function colour(id: string) {
  if (id === "intent:complaint") return "var(--chart-2)"
  if (id === "intent:cancellation") return "var(--negative)"
  if (id.startsWith("topic:")) return "var(--muted-foreground)"
  return id === "issue:OTHER" ? "var(--track)" : "var(--primary)"
}

type Datum = FlowNode & { name: string }

function Chart({ flow, total }: { flow: Flow; total: number }) {
  const [active, setActive] = useState<number | null>(null)
  const index = new Map(flow.nodes.map((n, i) => [n.id, i]))
  const data = {
    nodes: flow.nodes.map((n): Datum => ({ ...n, name: n.label })),
    links: flow.links.map((l) => ({ source: index.get(l.source)!, target: index.get(l.target)!, value: l.records })),
  }
  const hovered = active === null ? null : flow.links[active]
  const name = (id: string) => display(flow.nodes[index.get(id)!])

  function renderNode({ x, y, width, height, payload: raw }: SankeyNodeProps) {
    const payload = raw as unknown as Datum
    const left = payload.column === 0
    const tx = left ? x - 8 : x + width + 8
    return (
      <Layer>
        <Rectangle x={x} y={y} width={width} height={Math.max(height, 1)} radius={2} fill={colour(payload.id)} fillOpacity={1} />
        <text x={tx} y={y + height / 2} textAnchor={left ? "end" : "start"} dominantBaseline="central" className="fill-foreground stroke-card stroke-[3px] text-[13px] [paint-order:stroke]">
          {display(payload)}
          <tspan className="fill-muted-foreground tabular-nums" dx={6}>{fmt.int(payload.records)}</tspan>
        </text>
      </Layer>
    )
  }

  function renderLink({ sourceX, targetX, sourceY, targetY, sourceControlX, targetControlX, linkWidth, index: i, payload: raw }: SankeyLinkProps) {
    const payload = raw as unknown as { source: Datum; target: Datum }
    const toIssue = payload.target.column === 2
    const tint = colour(toIssue ? payload.target.id : payload.source.id)
    return (
      <path
        d={`M${sourceX},${sourceY} C${sourceControlX},${sourceY} ${targetControlX},${targetY} ${targetX},${targetY}`}
        fill="none" stroke={tint} strokeWidth={Math.max(linkWidth, 1)}
        strokeOpacity={active === null ? (toIssue && payload.target.id === "issue:OTHER" ? 0.35 : 0.3) : active === i ? 0.75 : 0.12}
        onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)}
      />
    )
  }

  return (
    <>
      <div className="-mx-2 mt-6 overflow-x-auto px-2" role="img"
        aria-label={`Sankey diagram: ${fmt.int(total)} complaint and cancellation reviews flowing from intent to topic to issue. The counts are in the table below.`}>
        <div className="min-w-[820px]">
          <div className="relative mb-2 h-4 text-[12px] tracking-[0.14em] text-muted-foreground uppercase" aria-hidden="true">
            {COLUMNS.map((c) => <span key={c.name} className={`absolute top-0 ${c.className}`}>{c.name}</span>)}
          </div>
          <ResponsiveContainer width="100%" height={470}>
            <Sankey data={data} sort={false} nodeWidth={NODE_WIDTH} nodePadding={22} linkCurvature={0.5} iterations={64}
              margin={MARGIN} node={renderNode} link={renderLink} />
          </ResponsiveContainer>
        </div>
      </div>
      <p className="mt-2 min-h-5 text-[13px] text-muted-foreground" aria-live="polite">
        {hovered
          ? <><span className="text-foreground">{name(hovered.source)} → {name(hovered.target)}</span> · {fmt.int(hovered.records)} reviews ({fmt.pct(hovered.records / total, 1)})</>
          : "Point at a band to see its count."}
      </p>
    </>
  )
}

function FlowTable({ flow, total }: { flow: Flow; total: number }) {
  const label = new Map(flow.nodes.map((n) => [n.id, display(n)]))
  const layers = [
    { title: "Intent to topic", links: flow.links.filter((l) => l.source.startsWith("intent:")) },
    { title: "Topic to issue", links: flow.links.filter((l) => l.source.startsWith("topic:")) },
  ]
  return (
    <details className="mt-4 rounded-2xl bg-tile px-4 py-3 text-[14px]" data-testid="complaint-flow-table">
      <summary className="cursor-pointer text-foreground">Show the counts as a table</summary>
      <div className="mt-3 grid gap-6 lg:grid-cols-2">
        {layers.map((layer) => (
          <Table key={layer.title}>
            <caption className="mb-2 text-left text-[13px] text-muted-foreground">{layer.title} · each layer sums to {fmt.int(total)}</caption>
            <TableHeader>
              <TableRow><TableHead>From</TableHead><TableHead>To</TableHead><TableHead className="text-right">Reviews</TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {layer.links.map((l) => (
                <TableRow key={l.source + l.target}>
                  <TableCell>{label.get(l.source)}</TableCell>
                  <TableCell>{label.get(l.target)}</TableCell>
                  <TableCell className="text-right tabular-nums">{fmt.int(l.records)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ))}
      </div>
    </details>
  )
}

export default function ComplaintFlow() {
  const { data: flow, error } = useData(api.flow)
  if (error) return <LoadError message={error} />
  if (!flow) return <Skeleton className="h-[34rem] rounded-2xl bg-tile" />
  const total = flow.records ?? 0
  return (
    <div data-testid="complaint-flow">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-xl">How complaints reach the ranked issues</h2>
        {total > 0 && <p className="text-[15px]"><span className="tabular-nums">{fmt.int(total)}</span> <span className="text-muted-foreground">reviews</span></p>}
      </div>
      {flow.status === "pending" || total === 0 ? (
        <div className="mt-4"><PendingNote>The complaint flow appears once the accepted issue map is loaded.</PendingNote></div>
      ) : (
        <>
          <Reflection className="mt-2">
            Each complaint or cancellation review counts once in every column: its intent, its topic, then the one issue it
            was grouped into. The {flow.leading_issues} issues ranked highest by severity sum keep their own band; the other{" "}
            {flow.combined_issues} are combined. A topic is the classifier's label and an issue is the grouping step's, so a
            playback topic can still feed an ads issue.
          </Reflection>
          <Chart flow={flow} total={total} />
          <FlowTable flow={flow} total={total} />
          <p className="mt-3 text-[13px] text-muted-foreground">
            Computed by the backend from the stored issue map at request time.
            {flow.flagged_members_excluded ? ` ${fmt.int(flow.flagged_members_excluded)} members with a known semantic flag are left out, as in the public ranking.` : ""}
          </p>
        </>
      )}
    </div>
  )
}
