# Production dashboard screenshots

Captured from the live public site in **Google Chrome on macOS** on 12 October 2026 (UTC). These are direct browser viewport captures at 1230 × 876 pixels, saved as JPEG. No values or interface elements were generated or staged.

| File | Capture time (UTC) | Source URL | Suggested caption |
| --- | --- | --- | --- |
| `overview-review-activity.jpg` | 23:32:48 | https://hanif-spotify-insights.vercel.app/ | Review activity: 110,000 source reviews against a 100,000 target; 30,400 complaints; mean complaint severity 3.02; 100,229 classified toward the minimum. |
| `issue-ranking-top-five.jpg` | 23:32:59 | https://hanif-spotify-insights.vercel.app/#issues | Top five issue ranking by severity sum. Ad frequency or interruption leads with 5,195 complaints and severity sum 11,869; playback fails or stops follows with 2,474 complaints and severity sum 8,904. |
| `evaluation-prompt-benchmark.jpg` | 23:33:23 | https://hanif-spotify-insights.vercel.app/#evals | Measured 100-review comparison of prompt rubrics v1 and v2: 32 topic changes, zero intent changes, one severity change, and 16 review-flag changes. This is a prompt comparison, not human-label accuracy. |

## Verification and publication notes

- Each saved image was reopened and visually inspected. The relevant numbers are legible; there are no loading or error states in the captured viewports.
- The issue map is provisional. The page reports 40% agreement with a blind human review and says to treat its ranking as advisory. The human golden evaluation remains pending.
- These screenshots contain no review quotes, review IDs, account details, browser profile details, credentials, or unrelated private pages. They reproduce the public site's branding and figures; keep the site's independent-course-project/non-affiliation context with any publication.
- No site, database, repository, or deployment changes were made in this task.

## SHA-256

```text
629d5f49ed6cb440e7e75c4d995581bb8d8cd253c3978f1e99247f5f2d8a465f  overview-review-activity.jpg
90ebdc41bdd6869ac3744c00b619f9eff511f9ee47cc52fd078164e83ca69539  issue-ranking-top-five.jpg
6f74b29e137a27504095b0e1842fb46b3784f1ce1f00af1d11f9fd7826d19e70  evaluation-prompt-benchmark.jpg
```
