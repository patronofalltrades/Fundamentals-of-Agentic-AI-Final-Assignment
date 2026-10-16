import { Fragment, useState, type ReactNode } from "react"
import { ArrowRight, Search, ShieldCheck, TriangleAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { api, fmt, type Claim } from "@/lib/api"
import { ledgerRows, parseMemo, sentenceCase, SUMMARY_SECTIONS, type LedgerRow, type MemoBlock } from "@/lib/memo"
import { LoadError, PendingNote, Reflection } from "./bits"
import { CodeButton } from "./code-snippet"
import { REFLECTIONS } from "@/lib/reflections"
import { useData } from "./use-data"

const CLAIM = /(claim-[A-Za-z0-9_.:-]+)/g
const METRICS = ["complaint_count", "severity_sum", "mean_severity", "priority_score"] as const
/** Issue areas, from the issue ID prefix (for example PLY-FAIL is playback). */
const AREAS: Record<string, string> = {
  ACC: "Account", APP: "App", BIL: "Billing", CAT: "Catalog", DEV: "Devices", DLD: "Downloads",
  GEN: "General", PLY: "Playback", SUP: "Support", USE: "Usability",
}
const area = (issueId: string) => issueId.split("-")[0] ?? ""

/** Text with each claim ID marked; hovering shows the saved value. */
function WithClaims({ text, claims }: { text: string; claims: Map<string, Claim> }) {
  return (
    <>
      {text.split(CLAIM).map((part, i) => {
        const claim = claims.get(part)
        if (!claim) return <Fragment key={i}>{part}</Fragment>
        return (
          <Tooltip key={i}>
            <TooltipTrigger asChild>
              <mark tabIndex={0} className="cursor-help rounded-md bg-primary/12 px-1 text-primary">{part}</mark>
            </TooltipTrigger>
            <TooltipContent>{`${claim.issue_id} · ${fmt.label(claim.metric)} = ${claim.value}`}</TooltipContent>
          </Tooltip>
        )
      })}
    </>
  )
}

function Blocks({ blocks, claims }: { blocks: MemoBlock[]; claims: Map<string, Claim> }) {
  return (
    <div className="space-y-3">
      {blocks.map((b, i) =>
        b.kind === "paragraph" ? (
          <p key={i}><WithClaims text={b.text} claims={claims} /></p>
        ) : (
          <ul key={i} className="list-disc space-y-1 pl-5">
            {b.items.map((item, j) => <li key={j}><WithClaims text={item} claims={claims} /></li>)}
          </ul>
        ),
      )}
    </div>
  )
}

/** The claim ledger as one row per issue; each number carries its claim ID. Filter by issue name, ID or area. */
function Ledger({ rows, titles }: { rows: LedgerRow[]; titles: Map<string, string> }) {
  const [query, setQuery] = useState("")
  const [picked, setPicked] = useState<string | null>(null)
  const byIssue = new Map<string, { rank: string; values: Partial<Record<string, LedgerRow>> }>()
  for (const row of rows) {
    const item = byIssue.get(row.issueId) ?? { rank: row.claimId.split("-")[1] ?? "", values: {} }
    item.values[row.metric] = row
    byIssue.set(row.issueId, item)
  }
  const all = [...byIssue.entries()]
  const counts = new Map<string, number>()
  for (const [issueId] of all) counts.set(area(issueId), (counts.get(area(issueId)) ?? 0) + 1)
  const q = query.trim().toLowerCase()
  const shown = all.filter(([issueId]) =>
    (!picked || area(issueId) === picked) &&
    (!q || issueId.toLowerCase().includes(q) || (titles.get(issueId) ?? "").toLowerCase().includes(q)))
  const chip = (key: string | null, label: string, n: number) => (
    <button key={key ?? "all"} type="button" aria-pressed={picked === key} onClick={() => setPicked(key)}
      className="rounded-full bg-tile px-3 py-1 text-[13px] text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none aria-pressed:bg-primary aria-pressed:text-primary-foreground">
      {label} <span className="tabular-nums opacity-70">{n}</span>
    </button>
  )
  const cell = (row?: LedgerRow) =>
    row ? (
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0} className="cursor-help tabular-nums underline decoration-track decoration-dotted underline-offset-4">
            {row.metric === "mean_severity" ? Number(row.value).toFixed(2) : fmt.int(Number(row.value))}
          </span>
        </TooltipTrigger>
        <TooltipContent>{row.claimId} = {row.value}</TooltipContent>
      </Tooltip>
    ) : "—"
  return (
    <div data-testid="claim-ledger-filter">
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative sm:w-72">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input value={query} maxLength={60} onChange={(e) => setQuery(e.target.value)} placeholder="Filter by issue name or ID"
            aria-label="Filter the claim ledger by issue name or ID" className="h-9 rounded-full pl-8" />
        </div>
        <p className="text-[13px] text-muted-foreground" aria-live="polite">
          <span className="tabular-nums">{shown.length} of {all.length}</span> issues
          {shown.length !== all.length && <> · <span className="tabular-nums">{shown.reduce((n, [, v]) => n + Object.keys(v.values).length, 0)}</span> claims</>}
        </p>
      </div>
      <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Filter by issue area">
        {chip(null, "All", all.length)}
        {[...counts.entries()].sort((a, b) => b[1] - a[1]).map(([key, n]) => chip(key, AREAS[key] ?? key, n))}
      </div>
      <Table className="text-[14px]" data-testid="claim-ledger">
        <TableHeader className="[&_tr]:border-0">
          <TableRow className="bg-tile hover:bg-tile">
            <TableHead className="rounded-l-xl text-[13px] font-normal text-muted-foreground">Issue</TableHead>
            <TableHead className="text-right text-[13px] font-normal text-muted-foreground">Complaints</TableHead>
            <TableHead className="text-right text-[13px] font-normal text-muted-foreground max-sm:rounded-r-xl">Severity sum</TableHead>
            <TableHead className="hidden text-right text-[13px] font-normal text-muted-foreground sm:table-cell">Mean</TableHead>
            <TableHead className="hidden rounded-r-xl text-right text-[13px] font-normal text-muted-foreground sm:table-cell">Priority</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {shown.map(([issueId, { rank, values }]) => (
            <TableRow key={issueId} className="border-border/70">
              <TableCell className="py-2.5 whitespace-normal">
                <span className="mr-2 text-muted-foreground tabular-nums">{Number(rank)}</span>
                {titles.get(issueId) ?? issueId}
                <span className="ml-2 hidden font-mono text-[12px] text-muted-foreground sm:inline">{issueId}</span>
              </TableCell>
              {METRICS.map((m, i) => (
                <TableCell key={m} className={i >= 2 ? "hidden text-right sm:table-cell" : "text-right"}>{cell(values[m])}</TableCell>
              ))}
            </TableRow>
          ))}
          {shown.length === 0 && (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={5} className="py-6 text-center text-muted-foreground">
                No issue matches this filter.{" "}
                <button type="button" className="text-primary underline underline-offset-4" onClick={() => { setQuery(""); setPicked(null) }}>Clear filter</button>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}

function Section({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <section className="mt-6">
      <h3 className="mb-2 text-lg text-foreground">{sentenceCase(heading)}</h3>
      {children}
    </section>
  )
}

/**
 * The decision memo. ``summary`` (main page) shows the opening note, the finding and the next action, each in
 * full, and links to the memo page. ``full`` (memo page) shows every section, with the claim ledger as a table.
 */
export default function MemoPanel({ variant = "summary" }: { variant?: "summary" | "full" }) {
  const memo = useData(api.memo)
  const claims = useData(api.claims)
  const recommendations = useData(api.recommendations)
  const issues = useData(api.issues)
  if (memo.error) return <LoadError message={memo.error} />
  if (!memo.data) return <Skeleton className="h-48 rounded-2xl bg-tile" />
  const checked = memo.data.status === "claims_checked" || memo.data.status === "claims_checked_provisional"
  const provisional = memo.data.status === "claims_checked_provisional"
  const byId = new Map((claims.data?.items ?? []).map((c) => [c.claim_id, c]))
  const titles = new Map((issues.data?.items ?? []).map((i) => [i.issue_id, i.title]))
  const parsed = memo.data.text ? parseMemo(memo.data.text) : null
  const actions = recommendations.data?.items ?? []
  const full = variant === "full"
  const sections = parsed ? parsed.sections.filter((s) => full || (SUMMARY_SECTIONS.test(s.heading) && !(actions.length && /recommend|next action/i.test(s.heading)))) : []
  const claimCount = claims.data?.items.length ?? 0

  return (
    <TooltipProvider delayDuration={150}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        {full ? <h1 className="text-2xl">{parsed?.title ? sentenceCase(parsed.title) : "Decision memo"}</h1> : <h2 className="text-xl">Decision memo</h2>}
        {memo.data.text && (
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className={checked ? "gap-1.5 rounded-full text-positive" : "gap-1.5 rounded-full text-negative"}>
              {checked ? <ShieldCheck className="size-3.5" aria-hidden="true" /> : <TriangleAlert className="size-3.5" aria-hidden="true" />}
              {checked ? "Ranking claims match saved values" : fmt.label(memo.data.status)}
            </Badge>
            <CodeButton id="claim-check" label="How claims are checked" />
          </div>
        )}
      </div>
      {!full && <Reflection className="mt-2">{REFLECTIONS.memo}</Reflection>}

      {!parsed ? (
        <div className="mt-4">
          <PendingNote>
            Pending. The memo comes from the pipeline's export. Each number in it cites a claim ID, and the dashboard checks
            each claim against the saved ranking before it shows the memo.
          </PendingNote>
        </div>
      ) : (
        <div className="max-w-[78ch] text-[15px] leading-7 text-foreground/90" data-testid={full ? "memo-full" : "memo-summary"}>
          {parsed.intro.length > 0 && <div className="mt-4"><Blocks blocks={parsed.intro} claims={byId} /></div>}
          {sections.map((s) => {
            const rows = ledgerRows(s)
            return (
              <Section key={s.heading} heading={s.heading}>
                {rows ? <Ledger rows={rows} titles={titles} /> : <Blocks blocks={s.blocks} claims={byId} />}
              </Section>
            )
          })}
        </div>
      )}

      {recommendations.error && <div className="mt-4"><LoadError message={recommendations.error} /></div>}
      {!full && actions.length > 0 && (
        <div className="mt-6 rounded-2xl border border-border bg-tile p-4">
          <h3 className="text-base">Provisional next action</h3>
          {actions.map((item) => (
            <div key={item.recommendation_id} className="mt-2 text-[15px] leading-7">
              <p>{item.text}</p>
              <p className="text-sm text-muted-foreground">
                Saved issue: {item.issue_ids.join(", ")}
                {item.claim_ids?.length ? ` · Checked claims: ${item.claim_ids.join(", ")}` : ""}
              </p>
            </div>
          ))}
          {provisional && (
            <p className="mt-2 text-sm text-muted-foreground">
              The issue map is model-derived. Separately, one assistant's manual assignments agreed with human answers
              on 16/40 (40%); this did not evaluate the production grouping model.
              The ranking is advisory until targeted human review; these counts do not establish a product effect or revenue impact.
            </p>
          )}
        </div>
      )}

      {!full && parsed && (
        <a href="/memo/" data-testid="full-memo-link"
          className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-[15px] text-primary-foreground transition hover:brightness-105 focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:outline-none">
          Read the full memo{claimCount ? ` · all ${claimCount} checked claims` : ""} <ArrowRight className="size-4" aria-hidden="true" />
        </a>
      )}
    </TooltipProvider>
  )
}
