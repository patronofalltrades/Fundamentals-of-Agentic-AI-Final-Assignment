import { Fragment } from "react"
import { ShieldCheck, TriangleAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { api, fmt, type Claim } from "@/lib/api"
import { LoadError, PendingNote } from "./bits"
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
  if (memo.error) return <LoadError message={memo.error} />
  if (!memo.data) return <Skeleton className="h-48 rounded-2xl bg-tile" />
  const checked = memo.data.status === "claims_checked"
  const byId = new Map((claims.data?.items ?? []).map((c) => [c.claim_id, c]))
  return (
    <TooltipProvider delayDuration={150}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl">Decision memo</h2>
        {memo.data.text && (
          <Badge variant="secondary" className={checked ? "gap-1.5 rounded-full text-positive" : "gap-1.5 rounded-full text-negative"}>
            {checked ? <ShieldCheck className="size-3.5" aria-hidden="true" /> : <TriangleAlert className="size-3.5" aria-hidden="true" />}
            {checked ? "Every claim matches its saved value" : fmt.label(memo.data.status)}
          </Badge>
        )}
      </div>
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
