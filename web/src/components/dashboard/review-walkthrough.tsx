import { useState } from "react"
import { Check, CircleHelp, ExternalLink, RotateCcw } from "lucide-react"

import { Progress } from "@/components/ui/progress"
import { REFLECTIONS } from "@/lib/reflections"
import { cn } from "@/lib/utils"
import { Reflection } from "./bits"
import {
  CONCEPTS, CONFIDENCE_COPY, FIELDS, POLICY_THRESHOLD, REVIEW, SAVED_NEEDS_REVIEW, SOURCES, STEPS, reviewAt, type FieldKey,
} from "@/lib/walkthrough"

const eyebrow = "text-[12px] tracking-[0.12em] text-muted-foreground uppercase"
const pill = "rounded-full px-4 py-2 text-[14px] transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"

function Mark({ children }: { children: string }) {
  return <mark className="rounded-md bg-primary/20 px-1 text-foreground decoration-primary underline decoration-2 underline-offset-4">{children}</mark>
}

function SavedRecord() {
  return (
    <article className="rounded-3xl bg-card p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-[60ch]">
          <p className="text-[12px] tracking-[0.12em] text-primary uppercase">Walkthrough</p>
          <h2 className="mt-1 text-xl">One review, end to end</h2>
          <Reflection className="mt-2">{REFLECTIONS.example}</Reflection>
        </div>
        <span className="rounded-full bg-tile px-3 py-1 text-[12px] text-muted-foreground">Saved output · row {REVIEW.row} of {REVIEW.of.toLocaleString("en-US")}</span>
      </header>

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <figure className="rounded-2xl bg-tile p-5">
            <figcaption className={eyebrow}>Original review · exact text</figcaption>
            <blockquote className="mt-3 text-[16px] leading-7">
              {REVIEW.before}<Mark>{REVIEW.quote}</Mark>{REVIEW.after}
            </blockquote>
            <p className="mt-3 text-[12px] text-muted-foreground">Highlight: the exact evidence quote extracted through DeepInfra. Not Jev word attribution.</p>
          </figure>
          <ol className="flex flex-wrap items-center gap-2 text-[13px]" aria-label="Record processing sequence">
            {["Source text", "Jev labels", "DeepInfra quote", "Validation and review flag"].map((s, i, all) => (
              <li key={s} className="flex items-center gap-2">
                <span className="rounded-full bg-tile px-3 py-1">{s}</span>
                {i < all.length - 1 && <span className="text-muted-foreground" aria-hidden="true">→</span>}
              </li>
            ))}
          </ol>
        </div>

        <div className="flex flex-col gap-4">
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="text-[15px]">What Jev's saved record contains</h3>
            <span className="text-[12px] text-muted-foreground">Bars: native confidence, saved unchanged</span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {(Object.keys(FIELDS) as FieldKey[]).map((key) => {
              const f = FIELDS[key]
              const low = f.confidence < POLICY_THRESHOLD
              return (
                <div key={key} className={cn("rounded-2xl bg-tile p-4", low && "ring-1 ring-chart-2/60")}>
                  <p className={eyebrow}>{f.name} · {f.type}</p>
                  <p className="mt-1 text-[1.5rem] leading-tight font-light">{f.value}{key === "sentiment" && <span className="text-[13px] text-muted-foreground"> on −1 to +1</span>}</p>
                  <div className="mt-3 flex justify-between text-[12px]">
                    <span className="text-muted-foreground">Confidence</span>
                    <span className={cn("tabular-nums", low && "text-chart-2")}>{f.confidence.toFixed(2)}</span>
                  </div>
                  <Progress value={f.confidence * 100} aria-label={`${f.name} confidence`} className={cn("mt-1.5 h-1.5 bg-track", low ? "[&>div]:bg-chart-2" : "[&>div]:bg-primary")} />
                </div>
              )
            })}
          </div>
          <p className="text-[13px] text-muted-foreground">
            <span className="text-foreground">These bars are not class probabilities or measured accuracy.</span> Topic, intent and severity use Choice;
            sentiment uses Score, which has a different confidence formula. The run did not save option distributions or the raw response.
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 rounded-2xl bg-[linear-gradient(120deg,#0f1d15,#181818_60%)] p-5 md:grid-cols-[minmax(0,1fr)_auto]">
        <div>
          <p className="text-[12px] tracking-[0.12em] text-primary uppercase">Saved routing result</p>
          <h3 className="mt-1 text-lg">Accepted record. Still flagged for review.</h3>
          <p className="mt-1 text-[15px] text-muted-foreground">
            Severity confidence is <span className="text-foreground">0.27</span>, below the <span className="text-foreground">0.60</span> threshold, so <code className="text-foreground">needs_review = true</code>.
          </p>
          <p className="mt-2 text-[13px] text-muted-foreground">Accepted means the record passed its processing checks. It does not mean a person confirmed the labels, and it does not clear the review flag.</p>
        </div>
        <ul className="space-y-1.5 self-center text-[14px]">
          {["Exact-source span check passed", "Source hashes match", "Row accepted"].map((c) => (
            <li key={c} className="flex items-center gap-2"><Check className="size-4 text-primary" aria-hidden="true" />{c}</li>
          ))}
        </ul>
      </div>

      <details className="mt-4 rounded-2xl bg-tile/50 px-4 py-3 text-[14px]">
        <summary className="cursor-pointer text-muted-foreground">Inspect the saved evidence and provenance</summary>
        <dl className="mt-3 grid gap-3 sm:grid-cols-2">
          {[
            ["Evidence quote", REVIEW.quote],
            ["Extracted entities", REVIEW.entities.join(" · ")],
            ["Sentiment scale", "Jev's Score value is rescaled from 0–4 to −1 to +1. The saved result is +0.325; its confidence stays 0.68."],
            ["Review policy", "Flag the row when any confidence is below 0.60, the topic is “other”, or the intent is “unclear”. This row meets the confidence condition."],
            ["Record origin", "Direct Jev and DeepInfra outputs. No human correction or quarantine recorded."],
            ["Snapshot source", "Saved project records, the 5,000-review checkpoint manifest and the Jev client code, read on 8 October 2026. The review ID is left out on purpose."],
          ].map(([k, v]) => (
            <div key={k}><dt className={eyebrow}>{k}</dt><dd className="mt-1">{v}</dd></div>
          ))}
        </dl>
      </details>
    </article>
  )
}

function Inspector() {
  const [field, setField] = useState<FieldKey>("severity")
  const [threshold, setThreshold] = useState(Math.round(POLICY_THRESHOLD * 100))
  const f = FIELDS[field]
  const t = threshold / 100
  const result = reviewAt(t)
  const reason = result.low.length
    ? `${result.low.map((x) => `${x.name} (${x.confidence.toFixed(2)})`).join(", ")} ${result.low.length === 1 ? "is" : "are"} below ${t.toFixed(2)}.`
    : `All four confidences meet or exceed ${t.toFixed(2)}. Neither label condition applies.`
  return (
    <article className="rounded-3xl bg-card p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg">Read the judgments on this review</h3>
          <p className="mt-1 text-[15px] text-muted-foreground">Pick a field to see what its value and confidence mean.</p>
        </div>
        <div role="group" aria-label="Saved field" className="flex flex-wrap gap-2">
          {(Object.keys(FIELDS) as FieldKey[]).map((key) => (
            <button key={key} type="button" aria-pressed={field === key} onClick={() => setField(key)}
              className={cn(pill, field === key ? "bg-primary text-primary-foreground" : "bg-tile text-muted-foreground hover:text-foreground")}>
              {FIELDS[key].name}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]" aria-live="polite">
        <div className="rounded-2xl bg-tile p-5">
          <p className={eyebrow}>{f.name} · {f.type}</p>
          <p className="mt-1 text-[2rem] leading-tight font-light">{f.value}</p>
          <p className="mt-2 text-[15px]">{f.copy}</p>
          <div className="mt-4 rounded-xl border border-dashed border-track/70 px-4 py-3 text-[14px]">
            <p className="text-foreground">Option probabilities: not saved</p>
            <p className="mt-1 text-muted-foreground">{f.probabilityCopy}</p>
          </div>
        </div>
        <div className="rounded-2xl bg-tile p-5">
          <p className={eyebrow}>Native Jev confidence</p>
          <p className="mt-1 text-[3rem] leading-none font-light tabular-nums">{f.confidence.toFixed(2)}</p>
          <p className="mt-3 text-[14px] text-muted-foreground">{CONFIDENCE_COPY[f.type]}</p>
          <a href="https://docs.typesafe.ai/confidence" target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-[13px] underline decoration-track underline-offset-4 hover:text-primary">
            TypeSafe's confidence definitions <ExternalLink className="size-3" aria-hidden="true" />
          </a>
        </div>
      </div>

      <div className="mt-4 rounded-2xl bg-tile/50 p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <label htmlFor="walkthrough-threshold" className="text-[15px]">Try a different threshold for this record</label>
          <span className="text-[12px] text-muted-foreground">Hypothetical only. The saved result does not change.</span>
        </div>
        <div className="mt-3 flex items-center gap-4">
          <input id="walkthrough-threshold" type="range" min={0} max={100} step={1} value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))} aria-describedby="walkthrough-threshold-hint"
            className="h-2 w-full cursor-pointer accent-primary" />
          <output htmlFor="walkthrough-threshold" className="w-12 text-right text-[1.25rem] tabular-nums">{t.toFixed(2)}</output>
        </div>
        <p id="walkthrough-threshold-hint" className="mt-2 text-[13px] text-muted-foreground">
          The rule checks all four confidences. It also flags topic “other” or intent “unclear”; neither applies here.
        </p>
        <div aria-live="polite" className={cn("mt-4 flex items-start gap-3 rounded-xl p-4", result.needsReview ? "bg-chart-2/10" : "bg-primary/10")}>
          {result.needsReview
            ? <CircleHelp className="mt-0.5 size-5 shrink-0 text-chart-2" aria-hidden="true" />
            : <Check className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />}
          <div>
            <p className="text-[15px]">Demo outcome: <code>needs_review = {String(result.needsReview)}</code></p>
            <p className="text-[14px] text-muted-foreground">{reason}</p>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[12px] text-muted-foreground">
          <span>Saved policy: {POLICY_THRESHOLD.toFixed(2)} · saved result: needs_review = {String(SAVED_NEEDS_REVIEW)}</span>
          <button type="button" onClick={() => setThreshold(Math.round(POLICY_THRESHOLD * 100))}
            className={cn(pill, "inline-flex items-center gap-1.5 bg-tile px-3 py-1.5 text-[13px] text-foreground hover:bg-track/60")}>
            <RotateCcw className="size-3.5" aria-hidden="true" /> Reset to {POLICY_THRESHOLD.toFixed(2)}
          </button>
        </div>
      </div>
    </article>
  )
}

function Pipeline() {
  const [step, setStep] = useState(0)
  const s = STEPS[step]
  return (
    <article className="flex flex-col rounded-3xl bg-card p-6">
      <h3 className="text-lg">Follow this record through the pipeline</h3>
      <p className="mt-1 text-[15px] text-muted-foreground">Jev supplies typed judgments. A separate model, served through DeepInfra, supplies the evidence.</p>
      <ol role="group" aria-label="Processing stages" className="mt-5 grid gap-2 sm:grid-cols-5">
        {STEPS.map((x, i) => (
          <li key={x.label}>
            <button type="button" aria-pressed={step === i} onClick={() => setStep(i)}
              className={cn("flex w-full flex-col items-start gap-1 rounded-2xl p-3 text-left text-[14px] transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none",
                step === i ? "bg-primary text-primary-foreground" : "bg-tile text-muted-foreground hover:text-foreground")}>
              <span className="text-[12px] tabular-nums opacity-80">0{i + 1}</span>{x.label}
            </button>
          </li>
        ))}
      </ol>
      <div aria-live="polite" className="mt-4 rounded-2xl bg-tile p-5">
        <p className={eyebrow}>{s.owner}</p>
        <h4 className="mt-1 text-[17px]">{s.title}</h4>
        <p className="mt-2 text-[15px] text-muted-foreground">{s.copy}</p>
        <pre className="mt-4 rounded-xl bg-canvas p-4 font-mono text-[13px] whitespace-pre-wrap">{s.example}</pre>
      </div>
    </article>
  )
}

function Meaning() {
  return (
    <article className="flex flex-col gap-4 rounded-3xl bg-card p-6">
      <h3 className="text-lg">Understand this review's numbers</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {CONCEPTS.map((c) => (
          <div key={c.eyebrow} className="rounded-2xl bg-tile p-4">
            <p className="text-[12px] tracking-[0.12em] text-primary uppercase">{c.eyebrow}</p>
            <p className="mt-1 text-[15px]">{c.title}</p>
            <p className="mt-1 text-[14px] text-muted-foreground">{c.body}</p>
          </div>
        ))}
      </div>
      <p className="rounded-2xl bg-tile px-4 py-3 text-[14px]">
        <span className="text-foreground">Accepted, confident and correct are different claims.</span>{" "}
        <span className="text-muted-foreground">This record passed its checks, but its severity still needs review. One review cannot show calibration or an accuracy rate. The Evals section measures those across many reviews.</span>
      </p>
      <details className="rounded-2xl bg-tile/50 px-4 py-3 text-[14px]">
        <summary className="cursor-pointer text-muted-foreground">Can we see what individual words did inside Jev?</summary>
        <p className="mt-2 text-muted-foreground">No. No per-word attribution, logits or token probabilities were saved. The highlight is an extracted quote. A heat map of “what Jev thought of each word” would invent information we do not have.</p>
      </details>
      <details className="rounded-2xl bg-tile/50 px-4 py-3 text-[14px]">
        <summary className="cursor-pointer text-muted-foreground">Sources ({SOURCES.length})</summary>
        <ul className="mt-2 space-y-1">
          {SOURCES.map((s) => (
            <li key={s.href}>
              <a href={s.href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline decoration-track underline-offset-4 hover:text-primary">
                {s.label}<ExternalLink className="size-3" aria-hidden="true" />
              </a>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[12px] text-muted-foreground">The documentation supports the terms used here, not a claim that this judgment is correct.</p>
      </details>
    </article>
  )
}

export default function ReviewWalkthrough() {
  return (
    <div className="space-y-6">
      <SavedRecord />
      <Inspector />
      <div className="grid items-start gap-6 xl:grid-cols-2">
        <Pipeline />
        <Meaning />
      </div>
    </div>
  )
}
