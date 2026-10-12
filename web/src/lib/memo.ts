// Split the saved memo (plain markdown) into sections, so the main page can show a complete short version
// and the memo page can show every section with real headings. Nothing is cut mid-sentence: a section is
// either shown whole or not shown.

export type MemoBlock = { kind: "paragraph"; text: string } | { kind: "list"; items: string[] }
export type MemoSection = { heading: string; blocks: MemoBlock[] }
export type LedgerRow = { claimId: string; issueId: string; metric: string; value: string }
export type ParsedMemo = { title: string | null; intro: MemoBlock[]; sections: MemoSection[] }

const LEDGER_LINE = /^- (claim-[A-Za-z0-9_.:-]+): ([A-Za-z0-9-]+) ([a-z_]+) = ([0-9]+(?:\.[0-9]+)?)$/

function blocks(lines: string[]): MemoBlock[] {
  const out: MemoBlock[] = []
  let para: string[] = []
  let list: string[] = []
  const flush = () => {
    if (para.length) out.push({ kind: "paragraph", text: para.join(" ") })
    if (list.length) out.push({ kind: "list", items: list })
    para = []
    list = []
  }
  for (const raw of lines) {
    const line = raw.trim()
    if (!line) {
      flush()
    } else if (/^[-*] /.test(line)) {
      if (para.length) flush()
      list.push(line.slice(2))
    } else {
      if (list.length) flush()
      para.push(line)
    }
  }
  flush()
  return out
}

export function parseMemo(text: string): ParsedMemo {
  const lines = text.split(/\r?\n/)
  let title: string | null = null
  const intro: string[] = []
  const sections: { heading: string; lines: string[] }[] = []
  for (const line of lines) {
    const h1 = /^#\s+(.*)$/.exec(line)
    const h2 = /^#{2,6}\s+(.*)$/.exec(line)
    if (h1 && title === null && !sections.length) title = h1[1].trim()
    else if (h2) sections.push({ heading: h2[1].trim(), lines: [] })
    else (sections.length ? sections[sections.length - 1].lines : intro).push(line)
  }
  return { title, intro: blocks(intro), sections: sections.map((s) => ({ heading: s.heading, blocks: blocks(s.lines) })) }
}

/** Rows of a claim ledger section, or null when the section is not a ledger. */
export function ledgerRows(section: MemoSection): LedgerRow[] | null {
  const items = section.blocks.flatMap((b) => (b.kind === "list" ? b.items : []))
  if (!items.length || section.blocks.some((b) => b.kind !== "list")) return null
  const rows = items.map((item) => LEDGER_LINE.exec(`- ${item}`))
  if (rows.some((r) => !r)) return null
  return rows.map((r) => ({ claimId: r![1], issueId: r![2], metric: r![3], value: r![4] }))
}

/** "provisional finding" -> "Provisional finding" */
export const sentenceCase = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s)

/** Sections shown on the main page: the finding and the next action, when the memo has them. */
export const SUMMARY_SECTIONS = /finding|recommend|next action/i
