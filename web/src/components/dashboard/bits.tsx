import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/** "Label ······ value" row, as in the reference KPI tiles. */
export function Leader({ label, value, className }: { label: ReactNode; value: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-baseline text-[13px]", className)}>
      <span className="text-muted-foreground">{label}</span>
      <span className="leader" aria-hidden="true" />
      <span className="tabular-nums text-foreground">{value}</span>
    </div>
  )
}

export function PendingNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-2xl border border-dashed border-track/60 px-4 py-3 text-sm text-muted-foreground">{children}</p>
  )
}

export function LoadError({ message }: { message: string }) {
  return <p role="alert" className="text-sm text-negative">Could not load saved results ({message}).</p>
}

/** A short reflection at the top of a section: what we learned, not what the section shows. */
export function Reflection({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn("max-w-[72ch] border-l-2 border-primary/70 pl-3 text-[15px] leading-relaxed text-muted-foreground", className)}>
      <span className="mr-1.5 text-[12px] tracking-[0.12em] text-primary uppercase">Reflection</span>
      {children}
    </p>
  )
}
