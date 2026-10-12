import { useEffect, useRef, useState } from "react"
import { Search } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { api, fmt, reviewKey, TOPICS, type ReviewItem } from "@/lib/api"
import { REFLECTIONS } from "@/lib/reflections"
import { LoadError, Reflection } from "./bits"
import { Quote, ReviewDetail } from "./review-detail"

const PAGE = 12
const ALL = "all"

const LINK = /^#review-([A-Za-z0-9]{1,40})$/

/** The example named by a review link (#review-<reference>), or null. */
function useLinkedRow() {
  const read = () => LINK.exec(window.location.hash)?.[1] ?? null
  const [row, setRow] = useState<string | null>(read)
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
      <Quote item={item} className="mt-3" />
      <div className="mt-3 flex items-center justify-between gap-3 text-[13px] text-muted-foreground">
        <span><a href={`#review-${reviewKey(item)}`} className="underline decoration-track underline-offset-4 hover:text-foreground">
          {item.ref ? "Link" : `Row ${fmt.int(item.row_index ?? 0)}`}</a> · {item.is_cached ? "exact-text reuse" : "direct result"}</span>
        <Button variant="ghost" size="sm" className="h-7 rounded-full text-[13px]" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Hide record" : "Saved record"}
        </Button>
      </div>
      {open && <ReviewDetail id={reviewKey(item)} />}
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
  const [excluded, setExcluded] = useState<{ blocked?: number | null; personal?: number | null; bounded: boolean }>({ bounded: false })
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
        setExcluded({ blocked: page.excluded_blocked, personal: page.excluded_personal_info,
          bounded: page.items.some((i) => i.excerpt !== undefined) })
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
        {excluded.bounded
          ? "Excerpts of at most 30 words from the source-exact evidence of accepted reviews; longer quotes are shortened and marked. Review IDs, row numbers and full texts are not shown."
          : "Source-exact quotes from accepted reviews. Review IDs and full texts are not shown."}
        {excluded.blocked ? ` ${fmt.int(excluded.blocked)} reviews with a known semantic flag are left out.` : ""}
        {excluded.personal ? ` ${fmt.int(excluded.personal)} more are left out because an automatic screen found possible personal information.` : ""}
        {excluded.blocked || excluded.personal ? " The examples shown have not had human review." : ""}
      </p>
      {linked !== null && (
        <section className="mt-4 rounded-2xl bg-tile/60 p-4" aria-label="Linked review" data-testid="linked-review">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-[15px]">Linked review</h3>
            <a href="#evidence" className="text-[13px] text-muted-foreground underline decoration-track underline-offset-4 hover:text-foreground">Close</a>
          </div>
          <ReviewDetail id={linked} showQuote />
        </section>
      )}
      {error && <div className="mt-4"><LoadError message={error} /></div>}
      <p className="mt-4 text-[13px] text-muted-foreground" aria-live="polite">
        {total === null ? "Loading…" : `${fmt.int(total)} matching reviews`}
      </p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {items.map((item) => <Card key={reviewKey(item)} item={item} />)}
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
