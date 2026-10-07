# OpenRouter project key in macOS Keychain

Hanif approved a **USD 5 total OpenRouter project cap** and a reusable local
Keychain credential. This setup does not authorize a 100,000-review run or
change the chosen model. The existing DeepInfra ten-review canary has already
completed. Its result stays in the ignored ledger; this setup makes future
approved runs easier to launch.

## User-only setup

1. In [OpenRouter API Keys](https://openrouter.ai/settings/keys), create a
   **normal inference key**, named for the Spotify review project. Set its
   spending limit to **USD 5** and its reset to **None/Never**. Do not enable
   automatic top-up or a periodic reset. The [OpenRouter key API reference](https://openrouter.ai/docs/api/api-reference/api-keys/create-a-new-api-key)
   defines `limit` in USD and `limit_reset: null` as no reset. Enter and submit
   the new key only in OpenRouter's UI. Do not paste it into chat or a shell
   command.
2. In **Keychain Access**, select the local **login** keychain and create a
   new generic password item. Set the item name/service to
   `spotify-review-openrouter` and account to `hanif-spotify-project`. Put
   the new key in its Password field and save it yourself. If an item with
   that service and account already exists, stop and identify the conflict;
   do not overwrite it. Do not put the key in `.env`, Git, a document, or chat.
3. In a foreground Terminal window, change to the `spotify-batch10-canary`
   worktree and run `zsh tools/run_deepinfra_batch10_user.zsh check`.
   This retrieves the item
   inside the local Python process, calls OpenRouter's read-only
   [`GET /api/v1/key`](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key),
   and prints only whether the normal key is authorized, its USD limit,
   remaining limit, and reset setting. It sends **no inference request**.
   The check waits up to 90 seconds for Keychain access. If macOS asks whether
   `/usr/bin/security` may access the item, choose
   **Allow Once**. Do not choose **Always Allow**: that grants broader
   continuing access to the shared system binary.

The login Keychain item is visible in Keychain Access, but a background
workspace-sandbox lookup reported it missing. A lookup outside that sandbox
found the item; the background password read then timed out without a visible
prompt. A foreground Terminal check is the next diagnostic step. It prints
only sanitized key-limit status and sends no model request. If it still fails,
stop and report the exact error; do not expose the key or change access rules.

The batch runner calls `/usr/bin/security find-generic-password` with fixed
service and account arguments, captures its output privately, and never logs
the secret or places it in command arguments, files, or environment variables.
It checks the key has a non-resetting USD 5 limit and enough remaining for
the full next reservation before any paid call. Only the user can create the
provider key, save it in Keychain, and approve the macOS access prompt.

The local project ledger includes historical OpenRouter known charges and
held unknown exposures. Its latest saved prior exposure is **$0.725867396**;
the completed ten-review canary cost **$0.000226396**. The combined local
exposure is **$0.726093792**. The USD 5 provider key limit is a second guard,
not a guarantee that delayed provider billing can never overshoot. The local
runner reserves the full published endpoint bound before a request and stops
admitting work at or above the project cap. A v2 prompt is prepared in a
separate ignored ledger because the first canary's entity semantics need
review. The `check` command sends no inference. Hanif subsequently approved
and completed the single v2 ten-review trial. Its measured result and the
remaining cross-ledger accounting gap are recorded in
`reports/deepinfra-batch10-canary.md`; no larger run is authorized.
