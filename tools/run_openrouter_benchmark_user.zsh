#!/bin/zsh
# User runs this in their own Terminal. The key is hidden and never saved.
set -euo pipefail
cd "${0:A:h:h}"
limit="${1:-3}"
retry_id="${2:-}"
if [[ "$limit" != "3" && "$limit" != "100" ]]; then
  print -u2 'Use 3 for smoke or 100 to finish both routes.'
  exit 2
fi
if [[ -n "$retry_id" && "$retry_id" != "2" ]]; then
  print -u2 'Only reconciled attempt 2 is approved for an explicit retry.'
  exit 2
fi
retry_args=()
if [[ -n "$retry_id" ]]; then
  retry_args=(--retry-reconciled-id "$retry_id")
fi
dataset='/Users/haniframadhan/Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset'
baseline='/Users/haniframadhan/Documents/Codex/2026-10-06/task-2/spotify-v2-comparison/local/jev_pilot_v2_evidence.db'
print 'Enter your existing OpenRouter key. Input is hidden. No key is stored in a file.'
read -rs 'pilot_key?Existing OpenRouter API key: '
print
if [[ -z "$pilot_key" ]]; then
  print -u2 'No key entered. No calls made.'
  exit 2
fi
OPENROUTER_API_KEY="$pilot_key" PYTHONPYCACHEPREFIX=/tmp/spotify-pycache \
  python3 tools/openrouter_extractor_benchmark.py \
  --source "$dataset/cost_100.csv" --manifest "$dataset/manifest.json" \
  --baseline "$baseline" --limit "$limit" "${retry_args[@]}"
unset pilot_key
