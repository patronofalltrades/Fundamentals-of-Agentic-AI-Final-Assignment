import { ArrowRight } from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"
import { api, fmt } from "@/lib/api"
import { useData } from "./use-data"

/** Plain-language summary of the project, shown first. Numbers come from the saved results. */
export default function ProjectSummary() {
  const summary = useData(api.summary)
  const issues = useData(api.issues)
  const s = summary.data
  if (!s) return <Skeleton className="h-56 rounded-3xl bg-card" />
  const selected = s.import?.selected_rows ?? s.coverage.source_rows
  const accepted = s.coverage.completed_rows
  const candidates = s.import?.issue_candidates?.contract_baseline
  const ranked = issues.data?.items ?? []
  const [first, second] = ranked

  return (
    <section aria-labelledby="about-title" className="rounded-3xl bg-card p-6" data-testid="project-summary">
      <p className="text-[13px] tracking-[0.18em] text-primary uppercase">About this project</p>
      <h1 id="about-title" className="mt-2 max-w-[60ch] text-[1.6rem] leading-tight font-normal tracking-tight text-balance">
        Which Spotify problems should get product effort first? We read {fmt.int(selected)} app reviews to find out.
      </h1>
      <p className="mt-3 max-w-[80ch] text-[15px] text-muted-foreground">
        A multi-agent pipeline, built for a course on agentic AI, turns public Google Play reviews of Spotify into a ranked
        list of product problems and a short decision memo. Every number on this page comes from saved results and can be
        traced back to them. Independent course project, not affiliated with Spotify.
      </p>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl bg-tile p-4">
          <h2 className="text-base text-foreground">1. Read and label</h2>
          <p className="mt-1 text-[14px] leading-6 text-muted-foreground">
            One model labelled each review's topic, intent and severity. A second model saved an exact quote as evidence.
            Code checked every quote against the review text: {fmt.int(accepted)} of {fmt.int(selected)} reviews passed.
          </p>
        </div>
        <div className="rounded-2xl bg-tile p-4">
          <h2 className="text-base text-foreground">2. Group and rank</h2>
          <p className="mt-1 text-[14px] leading-6 text-muted-foreground">
            {candidates ? `${fmt.int(candidates)} complaints and cancellations` : "Complaints and cancellations"} were grouped
            into {s.import?.issue_import?.issues ?? ranked.length} issues by AI agents, checked by a blind second model and by
            human decisions. Issues rank by the sum of their severities, so both volume and harm count.
          </p>
        </div>
        <div className="rounded-2xl bg-tile p-4">
          <h2 className="text-base text-foreground">3. What we found (provisional)</h2>
          <p className="mt-1 text-[14px] leading-6 text-muted-foreground">
            {first && second ? (
              <>
                <span className="text-foreground">{first.title}</span> leads ({fmt.int(first.review_count)} complaints, mean
                severity {Number(first.mean_severity).toFixed(2)}). <span className="text-foreground">{second.title}</span> is
                second, with fewer but more severe complaints (mean {Number(second.mean_severity).toFixed(2)}).
              </>
            ) : (
              "The issue ranking appears when the saved issue membership is loaded."
            )}{" "}
            The issue map is model-made; treat the ranking as advisory.
          </p>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        <a href="#memo" className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-[15px] text-primary-foreground transition hover:brightness-105 focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:outline-none">
          Memo summary <ArrowRight className="size-4" aria-hidden="true" />
        </a>
        <a href="/memo/" className="inline-flex items-center gap-2 rounded-full bg-tile px-5 py-2.5 text-[15px] text-foreground transition hover:bg-track/60 focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:outline-none">
          Full memo
        </a>
        <a href="#issues" className="inline-flex items-center gap-2 rounded-full bg-tile px-5 py-2.5 text-[15px] text-foreground transition hover:bg-track/60 focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:outline-none">
          Issue ranking
        </a>
      </div>
    </section>
  )
}
