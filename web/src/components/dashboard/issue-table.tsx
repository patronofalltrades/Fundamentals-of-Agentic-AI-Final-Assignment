import { useState } from "react"
import { ArrowRight } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { api, fmt, type Claim } from "@/lib/api"
import { LoadError, PendingNote } from "./bits"
import { useData } from "./use-data"

const SHOWN = 5

function ClaimValue({ value, claim }: { value: string | number; claim?: Claim }) {
  if (!claim) return <span className="tabular-nums">{value}</span>
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="cursor-help tabular-nums underline decoration-track decoration-dotted underline-offset-4">{value}</span>
      </TooltipTrigger>
      <TooltipContent>{claim.claim_id}</TooltipContent>
    </Tooltip>
  )
}

export default function IssueTable() {
  const issues = useData(api.issues)
  const claims = useData(api.claims)
  const [all, setAll] = useState(false)
  if (issues.error) return <LoadError message={issues.error} />
  if (!issues.data) return <Skeleton className="h-80 rounded-2xl bg-tile" />
  const items = issues.data.items
  const byKey = new Map((claims.data?.items ?? []).map((c) => [`${c.issue_id}:${c.metric}`, c]))
  const totalComplaints = items.reduce((a, i) => a + i.review_count, 0)
  return (
    <TooltipProvider delayDuration={150}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xl">Issue ranking</h2>
        {items.length > SHOWN && (
          <Button variant="ghost" size="sm" className="gap-2 rounded-full text-[13px]" onClick={() => setAll(!all)}>
            {all ? "Show top 5" : `View all ${items.length}`}
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </Button>
        )}
      </div>
      {!items.length ? (
        <div className="mt-4 space-y-3">
          <PendingNote>
            Pending. The ranking appears when the pipeline's accepted issue membership is loaded. Raw topic labels are never
            shown as issues.
          </PendingNote>
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-10 rounded-xl bg-tile/60" />)}
        </div>
      ) : (
        <Table className="mt-4 text-[15px]">
          <TableHeader className="[&_tr]:border-0">
            <TableRow className="bg-tile hover:bg-tile">
              <TableHead className="rounded-l-xl text-[13px] font-normal text-muted-foreground">Issue</TableHead>
              <TableHead className="text-right text-[13px] font-normal text-muted-foreground">Complaints</TableHead>
              <TableHead className="text-right text-[13px] font-normal text-muted-foreground">Severity sum</TableHead>
              <TableHead className="text-right text-[13px] font-normal text-muted-foreground">Mean</TableHead>
              <TableHead className="rounded-r-xl text-right text-[13px] font-normal text-muted-foreground">Share</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(all ? items : items.slice(0, SHOWN)).map((issue, index) => (
              <TableRow key={issue.issue_id} className="border-border/70 hover:bg-tile/40">
                <TableCell className="py-3.5">
                  <span className="mr-2 text-muted-foreground tabular-nums">{index + 1}</span>
                  {issue.title !== issue.issue_id ? issue.title : fmt.label(issue.issue_id.replace(/^issue-/, ""))}
                </TableCell>
                <TableCell className="text-right"><ClaimValue value={issue.review_count} claim={byKey.get(`${issue.issue_id}:complaint_count`)} /></TableCell>
                <TableCell className="text-right"><ClaimValue value={issue.priority_score} claim={byKey.get(`${issue.issue_id}:severity_sum`)} /></TableCell>
                <TableCell className="text-right"><ClaimValue value={Number(issue.mean_severity).toFixed(2)} claim={byKey.get(`${issue.issue_id}:mean_severity`)} /></TableCell>
                <TableCell className="text-right">
                  <Badge variant="secondary" className="rounded-full bg-transparent px-0 font-normal text-foreground">
                    {fmt.pct(totalComplaints ? issue.review_count / totalComplaints : 0)}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </TooltipProvider>
  )
}
