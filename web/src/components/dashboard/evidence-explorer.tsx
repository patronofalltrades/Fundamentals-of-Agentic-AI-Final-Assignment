import { useEffect, useRef, useState } from "react"
import { Search } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { api, fmt, TOPICS, type ReviewDetail, type ReviewItem } from "@/lib/api"
import { REFLECTIONS } from "@/lib/reflections"
import { LoadError, Reflection } from "./bits"

const PAGE = 12
const ALL = "all"

function Detail({ row }: { row: number }) {
  const [detail, setDetail] = useState<ReviewDetail | null>(null)
  useEffect(() => {
    api.review(row).then(setDetail).catch(() => setDetail(null))
  }, [row])
  if (!detail) return <Skeleton className="mt-3 h-14 rounded-xl bg-canvas/60" />
  return (
    <dl className="mt-3 grid gap-x-6 gap-y-1 rounded-xl bg-canvas/60 p-3 text-[13px] sm:grid-cols-2">
      <div><dt className="inline text-muted-foreground">Sentiment </dt><dd className="inline tabular-nums">{detail.sentiment ?? "—"}</dd></div>
      <div><dt className="inline text-muted-foreground">Model </dt><dd className="inline">{detail.model ?? "unknown"} · {detail.prompt_version ?? "unknown"}</dd></div>
      <div className="sm:col-span-2 break-all"><dt className="inline text-muted-foreground">Source row hash </dt><dd className="inline font-mono text-[12px]">{detail.source_sha256}</dd></div>
    </dl>
  )
}

function Card({ item }: { item: ReviewItem }) {
  const [open, setOpen] = useState(false)
  return (
    <article className="rounded-2xl bg-tile/60 p-4">
      <div className="flex flex-wrap gap-1.5">
        <Badge variant="secondary" className="rounded-full bg-canvas/50 font-normal">{item.topic}</Badge>
        <Badge variant="secondary" className="rounded-full bg-canvas/50 font-normal">{item.intent}</Badge>
        <Badge variant="secondary" className="rounded-full bg-canvas/50 font-normal">severity {item.severity}</Badge>
        {item.needs_review ? <Badge variant="secondary" className="rounded-full bg-canvas/50 font-normal text-chart-2">needs review</Badge> : null}
      </div>
      <blockquote className="mt-3 text-[15px] leading-6 break-words">“{item.evidence_quote}”</blockquote>
      <div className="mt-3 flex items-center justify-between gap-3 text-[13px] text-muted-foreground">
        <span>Row {item.row_index} · {item.is_cached ? "exact-text reuse" : "direct result"}</span>
        <Button variant="ghost" size="sm" className="h-7 rounded-full text-[13px]" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Hide record" : "Saved record"}
        </Button>
      </div>
      {open && <Detail row={item.row_index} />}
    </article>
  )
}

export default function EvidenceExplorer() {
  const [topic, setTopic] = useState(ALL)
  const [query, setQuery] = useState("")
  const [submitted, setSubmitted] = useState("")
  const [items, setItems] = useState<ReviewItem[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const request = useRef(0)

  const load = (reset: boolean) => {
    const id = ++request.current
    setBusy(true)
    api
      .reviews({ topic: topic === ALL ? undefined : topic, q: submitted || undefined, offset: reset ? 0 : items.length, limit: PAGE })
      .then((page) => {
        if (id !== request.current) return
        setItems(reset ? page.items : [...items, ...page.items])
        setTotal(page.total)
        setError(null)
      })
      .catch((e: Error) => id === request.current && setError(e.message))
      .finally(() => id === request.current && setBusy(false))
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => load(true), [topic, submitted])

  return (
    <div>
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <h2 className="text-xl">Supporting evidence</h2>
        <form className="flex flex-col gap-2 sm:flex-row" role="search" onSubmit={(e) => { e.preventDefault(); setSubmitted(query.trim()) }}>
          <Select value={topic} onValueChange={setTopic}>
            <SelectTrigger className="w-full rounded-full bg-tile sm:w-40" aria-label="Topic"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All topics</SelectItem>
              {TOPICS.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
            </SelectContent>
          </Select>
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input value={query} maxLength={100} onChange={(e) => setQuery(e.target.value)} placeholder="Search quotes"
              aria-label="Search quotes" className="w-full rounded-full bg-tile pl-9 sm:w-60" />
          </div>
        </form>
      </div>
      <Reflection className="mt-2">{REFLECTIONS.evidence}</Reflection>
      <p className="mt-2 text-[12px] text-muted-foreground">Source-exact quotes. Review IDs and full texts are not shown.</p>
      {error && <div className="mt-4"><LoadError message={error} /></div>}
      <p className="mt-4 text-[13px] text-muted-foreground" aria-live="polite">
        {total === null ? "Loading…" : `${fmt.int(total)} matching reviews`}
      </p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {items.map((item) => <Card key={item.row_index} item={item} />)}
        {!items.length && busy && [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-32 rounded-2xl bg-tile/60" />)}
      </div>
      {total !== null && items.length < total && (
        <div className="mt-4 flex justify-center">
          <Button variant="secondary" className="rounded-full" disabled={busy} onClick={() => load(false)}>Load more</Button>
        </div>
      )}
    </div>
  )
}
