import { CodeXml, ExternalLink } from "lucide-react"

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import data from "@/lib/code-snippets.json"

// Excerpts cut from the repository by tools/build_code_snippets.py; `--check` fails when they drift from the source.

type Run = string | [string, string]
type Part = { path: string; symbol: string; first_line: number; last_line: number; url: string; lines: Run[][] }
type Snippet = { title: string; caption: string; parts: Part[] }

const SNIPPETS = data.snippets as unknown as Record<string, Snippet>
export type SnippetId = keyof typeof data.snippets

const TOKEN: Record<string, string> = {
  kw: "text-chart-3",
  fn: "text-primary",
  str: "text-chart-2",
  com: "text-muted-foreground italic",
  num: "text-chart-5",
  const: "text-chart-5",
}

function Code({ part }: { part: Part }) {
  return (
    <figure className="min-w-0">
      <figcaption className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-[13px]">
        <span className="text-foreground">
          <code>{part.path}</code> <span className="text-muted-foreground">· <code>{part.symbol}</code></span>
        </span>
        <a href={part.url} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-muted-foreground underline-offset-4 hover:text-primary hover:underline">
          Lines {part.first_line}–{part.last_line} on GitHub <ExternalLink className="size-3" aria-hidden="true" />
        </a>
      </figcaption>
      <pre className="overflow-x-auto rounded-2xl bg-canvas py-3 text-[12.5px] leading-[1.6]" tabIndex={0}
        aria-label={`${part.path}, lines ${part.first_line} to ${part.last_line}`}>
        <code className="grid min-w-max font-mono">
          {part.lines.map((line, i) => (
            <span key={i} className="flex">
              <span className="w-11 shrink-0 pr-3 text-right text-track select-none" aria-hidden="true">{part.first_line + i}</span>
              <span className="pr-4 whitespace-pre text-foreground/90">
                {line.length === 0 ? " " : line.map((run, j) =>
                  typeof run === "string" ? run : <span key={j} className={TOKEN[run[0]]}>{run[1]}</span>)}
              </span>
            </span>
          ))}
        </code>
      </pre>
    </figure>
  )
}

/** A small "View code" button that opens the real source behind a step, with links to GitHub. */
export function CodeButton({ id, className, label = "View code" }: { id: SnippetId; className?: string; label?: string }) {
  const snippet = SNIPPETS[id]
  return (
    <Dialog>
      <DialogTrigger
        className={cn("inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[12px] text-primary transition-colors hover:bg-primary/20 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none", className)}
        data-testid={`code-${id}`}
      >
        <CodeXml className="size-3.5" aria-hidden="true" />
        {label}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{snippet.title}</DialogTitle>
          <DialogDescription>{snippet.caption}</DialogDescription>
        </DialogHeader>
        {snippet.parts.map((part) => <Code key={`${part.path}:${part.first_line}`} part={part} />)}
        <p className="text-[12px] text-muted-foreground">
          Excerpts copied from the repository's <code>main</code> branch by <code>tools/build_code_snippets.py</code>. Line
          numbers are the file's own.
        </p>
      </DialogContent>
    </Dialog>
  )
}
