import { Fragment } from "react"
import { ShieldCheck, TriangleAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { api, fmt, type Claim } from "@/lib/api"
import { LoadError, PendingNote, Reflection } from "./bits"
import { REFLECTIONS } from "@/lib/reflections"
import { useData } from "./use-data"

const CLAIM = /(claim-[A-Za-z0-9_.:-]+)/g

function MemoText({ text, claims }: { text: string; claims: Map<string, Claim> }) {
  return (
    <div className="max-w-[72ch] text-[15px] leading-7 whitespace-pre-wrap text-foreground/90">
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
    </div>
  )
}

export default function MemoPanel() {
  const memo = useData(api.memo)
  const claims = useData(api.claims)
  const recommendations = useData(api.recommendations)
  if (memo.error) return <LoadError message={memo.error} />
  if (!memo.data) return <Skeleton className="h-48 rounded-2xl bg-tile" />
  const checked = memo.data.status === "claims_checked" || memo.data.status === "claims_checked_provisional"
  const provisional = memo.data.status === "claims_checked_provisional"
  const byId = new Map((claims.data?.items ?? []).map((c) => [c.claim_id, c]))
  return (
    <TooltipProvider delayDuration={150}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl">Decision memo</h2>
        {memo.data.text && (
          <Badge variant="secondary" className={checked ? "gap-1.5 rounded-full text-positive" : "gap-1.5 rounded-full text-negative"}>
            {checked ? <ShieldCheck className="size-3.5" aria-hidden="true" /> : <TriangleAlert className="size-3.5" aria-hidden="true" />}
            {checked ? "Numeric claims match saved values" : fmt.label(memo.data.status)}
          </Badge>
        )}
      </div>
      <Reflection className="mt-2">{REFLECTIONS.memo}</Reflection>
      {recommendations.error && <div className="mt-4"><LoadError message={recommendations.error} /></div>}
      {!!recommendations.data?.items.length && (
        <div className="mt-4 rounded-2xl border border-border bg-tile p-4">
          <h3 className="text-base">Provisional next action</h3>
          {recommendations.data.items.map((item) => (
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
              The issue map is model-derived. Pre-override blind human agreement was 16/40 (40%).
              The ranking is advisory until targeted human review; these counts do not establish a product effect or revenue impact.
            </p>
          )}
        </div>
      )}
      <div className="mt-4">
        {memo.data.text ? (
          <MemoText text={memo.data.text} claims={byId} />
        ) : (
          <PendingNote>
            Pending. The memo comes from the pipeline's export. Each number in it cites a claim ID, and the dashboard checks
            each claim against the saved ranking before it shows the memo.
          </PendingNote>
        )}
      </div>
    </TooltipProvider>
  )
}
