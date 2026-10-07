# Dashboard design requirements

Reference: "AI Dashboard Design" by Kyrylo Soliar for SOLAR Digital (Dribbble shot 26983160). We copy its design
language, not its assets. Colours were sampled from the 1600 × 1200 original on 8 October 2026.

## Decisions (Hanif, 8 October 2026)

| Topic | Decision |
| --- | --- |
| Framework | Astro (static HTML) with React islands for data and interaction |
| Components | shadcn/ui (`new-york`, Radix): Card, Table, Badge, Progress, Chart, Tooltip, Skeleton, Input, Select, Button |
| Font | Inter Tight, self-hosted (`@fontsource-variable/inter-tight`) |
| Hero visual | CSS orb (layered gradients). It stops rotating when the reader asks for reduced motion. |
| Layout | One long scrolling page: Overview, Issues, Memo, Evidence, Method |
| Trend lines | Real monthly data: reviews, complaints and mean severity per month |
| Gauges | Both: golden agreement (saved evaluation) and the top issue's mean severity |

## Language

- Layered dark surfaces with almost no borders. Depth comes from surface steps, not lines or shadows.
- One accent colour for every "active" or "progress" element.
- Pastel chart colours. Large, light numbers with small grey labels.
- Large radii, pill buttons, round bar caps, dotted leaders ("Target ······ 100,000").
- One showpiece: the orb. Everything else stays quiet.

## Tokens (`web/src/styles/global.css`)

| Token | Value | Use |
| --- | --- | --- |
| ambient | `#24384F` → `#0B0F15` | Glow behind the app frame |
| `--canvas` | `#060508` | App canvas between cards |
| `--card`, `--sidebar` | `#18171A` | Cards and rail |
| `--tile`, `--secondary` | `#2E2D30` | Tiles inside cards, table header, chips |
| `--track` | `#5A595C` | Empty part of bars and gauges |
| `--primary` | `#AAC5FA` | The accent |
| `--primary-foreground` | `#000010` | Text on the accent |
| `--foreground` | `#FFFFFF` | Titles, numbers |
| `--muted-foreground` | `#ADACAF` | Labels |
| `--chart-1/2/3` | `#BDCDE7` / `#FDF9D4` / `#D2F6F5` | Lavender, butter, mint lines |
| `--positive` / `--negative` | `#D7F8C8` / `#F4D2D1` | Up / down and warnings |
| `--radius` | `1.5rem` | Cards 24 px; tiles about 16 px |

Type scale: card titles 20 px, KPI numbers 32 px light, body and table 15 px, labels 13 px. No bold weights.

## Structure

1. **Rail:** logo tile, one icon per section, active item with an accent bar and a soft fade. On phones, a bottom bar.
2. **Overview:** hero card (question, live status chips, "Read the memo") beside the activity card (three KPI tiles
   with sparklines) and a progress strip (classified toward 100,000; distinct texts sent to the model).
3. **Issues:** ranking table (complaints, severity sum, mean, share; claim IDs on hover) beside the two gauges and
   pipeline readiness (Ingest, Classify, Verify, Group, Rank, Memo).
4. **Memo:** the pipeline's memo. Claim IDs are highlighted, and each shows its saved value on hover.
5. **Evidence:** topic filter, quote search, evidence cards, saved-record detail.
6. **Method:** labels, ranking rule and limits in plain words.

## Rules

1. Show only saved, checked data. Show a designed "pending" state, never sample numbers.
2. Keep the demo-coverage chip until 100,000 source rows are loaded.
3. No review IDs or full review texts in the page or the API.
4. Strict Content Security Policy: Astro adds hashes for its inline scripts and styles; no `unsafe-inline`. Chart
   colours come from CSS variables, so shadcn's chart style tag is not used. Islands that would server-render style
   attributes render on the client only.
5. Text contrast AA. Respect reduced motion. Keyboard focus is visible. Skip link at the top.
6. Self-hosted font and assets only. Opening the page makes no model call.
