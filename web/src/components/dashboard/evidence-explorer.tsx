import { useEffect, useRef, useState } from "react"
import { Search } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { api, fmt, TOPICS, type ReviewItem } from "@/lib/api"
import { REFLECTIONS } from "@/lib/reflections"
import { LoadError, Reflection } from "./bits"
import { ReviewDetail } from "./review-detail"

const PAGE = 12
const ALL = "all"

const LINK = /^#review-([0-9]{1,7})$/

/** The row named by a review link (#review-N), or null. */
function useLinkedRow() {
  const read = () => {
    const m = LINK.exec(window.location.hash)
    return m ? Number(m[1]) : null
  }
  const [row, setRow] = useState<number | null>(read)
  useEffect(() => {
    const onHash = () => {
      const next = read()
      setRow(next)
      if (next !== null) document.getElementById("evidence")?.scrollIntoView({ behavior: "smooth", block: "start" })
    }
    window.addEventListener("hashchange", onHash)
    if (read() !== null) onHash()
    return () => window.removeEventListener("hashchange", onHash)
  }, [])
  return row
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
        <span><a href={`#review-${item.row_index}`} className="underline decoration-track underline-offset-4 hover:text-foreground">Row {fmt.int(item.row_index)}</a> · {item.is_cached ? "exact-text reuse" : "direct result"}</span>
        <Button variant="ghost" size="sm" className="h-7 rounded-full text-[13px]" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Hide record" : "Saved record"}
        </Button>
      </div>
      {open && <ReviewDetail row={item.row_index} />}
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
  const [blocked, setBlocked] = useState<number | null>(null)
  const linked = useLinkedRow()
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
        setBlocked(page.excluded_blocked ?? null)
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
      <p className="mt-2 text-[12px] text-muted-foreground">
        Source-exact quotes from accepted reviews. Review IDs and full texts are not shown.
        {blocked ? ` ${fmt.int(blocked)} reviews with a known semantic flag are left out of these examples. Unflagged reviews have not had human review.` : ""}
      </p>
      {linked !== null && (
        <section className="mt-4 rounded-2xl bg-tile/60 p-4" aria-label="Linked review" data-testid="linked-review">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-[15px]">Linked review</h3>
            <a href="#evidence" className="text-[13px] text-muted-foreground underline decoration-track underline-offset-4 hover:text-foreground">Close</a>
          </div>
          <ReviewDetail row={linked} showQuote />
        </section>
      )}
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
