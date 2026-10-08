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

On 8 October 2026 Hanif asked for Spotify's colour code. The layout and type stay from the reference; the colours
follow Spotify. Spotify Green `#1ED760` is Spotify's brand green. The near-black scale and silver text follow public
breakdowns of the Spotify web player ([open-design.ai](https://open-design.ai/systems/spotify/),
[shadcn.io](https://www.shadcn.io/design/spotify/raw)); they are not an official Spotify specification. Amber `#F59B23`
and blue `#509BF5` come from Spotify's playlist-cover palette.

| Token | Value | Use |
| --- | --- | --- |
| ambient | green glow `rgba(30,215,96,.16)` on `#000000` | Behind the app frame |
| `--canvas` | `#121212` | App canvas between cards |
| `--card` | `#181818` | Cards |
| `--sidebar` | `#000000` | Rail |
| `--tile`, `--secondary` | `#282828` | Tiles inside cards, table header, chips |
| `--track` | `#4D4D4D` | Empty part of bars and gauges |
| `--primary` | `#1ED760` | Spotify Green: the single accent |
| `--primary-foreground` | `#000000` | Text on the accent |
| `--foreground` | `#FFFFFF` | Titles, numbers |
| `--muted-foreground` | `#B3B3B3` | Labels |
| `--chart-1/2/3` | `#1ED760` / `#F59B23` / `#509BF5` | Reviews, complaints, mean severity lines |
| `--positive` / `--negative` | `#1ED760` / `#F15E6C` | Good / warning |
| hero gradient | `#0A0A0A` → `#0F1D15` → `#145A30` → `#1C8A47` | Hero card |
| `--radius` | `1.5rem` | Cards 24 px; tiles about 16 px |

**Brand safety:** the page uses our own logo, never Spotify's. The hero and the footer say "Independent course
project. Not affiliated with or endorsed by Spotify."

Type scale: card titles 20 px, KPI numbers 32 px light, body and table 15 px, labels 13 px. No bold weights.

## Structure

1. **Rail:** logo tile, one icon per section, active item with an accent bar and a soft fade. On phones, a bottom bar.
2. **Overview:** hero card (question, live status chips, "Read the memo") beside the activity card (three KPI tiles
   with sparklines) and a progress strip (classified toward 100,000; distinct texts sent to the model).
3. **Issues:** ranking table (complaints, severity sum, mean, share; claim IDs on hover) beside the two gauges and
   pipeline readiness (Ingest, Classify, Verify, Group, Rank, Memo).
4. **Memo:** the pipeline's memo. Claim IDs are highlighted, and each shows its saved value on hover.
5. **Example:** one saved review followed end to end: labels with confidence, evidence, review flag, a
   hypothetical threshold slider and the five pipeline stages. Ported from the Jev explainer handoff.
6. **Evidence:** topic filter, quote search, evidence cards, saved-record detail.
7. **Method:** labels, ranking rule and limits in plain words.

## Rules

1. Show only saved, checked data. Show a designed "pending" state, never sample numbers.
2. Keep the demo-coverage chip until 100,000 source rows are loaded.
3. No review IDs or full review texts in the page or the API. One exception (Hanif, 8 October 2026): the
   "One review, end to end" walkthrough shows a single public Google Play review in full, without its review ID,
   so it can highlight the evidence quote. Its saved values live in `web/src/lib/walkthrough.ts`.
4. Strict Content Security Policy: Astro adds hashes for its inline scripts and styles; no `unsafe-inline`. Chart
   colours come from CSS variables, so shadcn's chart style tag is not used. Islands that would server-render style
   attributes render on the client only.
5. Text contrast AA. Respect reduced motion. Keyboard focus is visible. Skip link at the top.
6. Self-hosted font and assets only. Opening the page makes no model call.
