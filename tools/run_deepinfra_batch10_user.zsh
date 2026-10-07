#!/bin/zsh
# One authorized ten-review DeepInfra canary. Key is read from macOS Keychain.
set -euo pipefail
cd "${0:A:h:h}"
mode="${1:-run}"
if [[ "$mode" != "run" && "$mode" != "check" ]]; then
  print -u2 'Use check to verify Keychain and provider limit, or run for a pending approved canary.'
  exit 2
fi
dataset='/Users/haniframadhan/Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset'
baseline='/Users/haniframadhan/Documents/Codex/2026-10-06/task-3/spotify-extractor-benchmark/local/openrouter_corrected_100.db'
prior_ledger='/Users/haniframadhan/Documents/Codex/2026-10-06/task-3/spotify-extractor-benchmark/local/openrouter_extractor_benchmark.db'
expected_baseline_sha='340153ef37c1bd49f28392e88ca10685343a68480bf32f7186583d85b656960b'
if [[ ! -f "$baseline" || "$(shasum -a 256 "$baseline" | cut -d ' ' -f1)" != "$expected_baseline_sha" ]]; then
  print -u2 'Corrected development baseline is missing or changed. No call made.'
  exit 2
fi
if [[ ! -f "$prior_ledger" ]]; then
  print -u2 'Historical benchmark ledger is missing. No call made.'
  exit 2
fi
args=(--source "$dataset/cost_100.csv" --manifest "$dataset/manifest.json"
      --baseline "$baseline" --prior-ledger "$prior_ledger")
PYTHONPYCACHEPREFIX=/tmp/spotify-pycache python3 tools/deepinfra_batch10_canary.py "${args[@]}"
if [[ "$mode" == "check" ]]; then
  PYTHONPYCACHEPREFIX=/tmp/spotify-pycache \
    python3 tools/deepinfra_batch10_canary.py "${args[@]}" --check-key
  exit 0
fi
PYTHONPYCACHEPREFIX=/tmp/spotify-pycache \
  python3 tools/deepinfra_batch10_canary.py "${args[@]}" --run
