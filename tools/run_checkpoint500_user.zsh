#!/bin/zsh
# User enters the existing TypeSafe key in a visible Terminal. Never echo it.
set +x
set -euo pipefail
umask 077

repo_dir=${0:A:h:h}
cd "$repo_dir"

dataset='/Users/haniframadhan/Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset'
sample="$dataset/checkpoint_500.csv"
manifest="$dataset/manifest.json"
ledger='local/jev_checkpoint500_v2.db'
result='local/jev_checkpoint500_labels_run.json'
lock='local/jev_checkpoint500_labels_launch.lock'

if [[ ! -f "$ledger" || -e "$result" || -e "${result}.tmp" ]]; then
  print -u2 'Prepared checkpoint ledger is missing or a run result already exists. Stop and inspect it.'
  exit 1
fi
if ! mkdir "$lock" 2>/dev/null; then
  print -u2 'A checkpoint launch lock exists. Stop and inspect the prior launch.'
  exit 1
fi
trap 'unset pilot_key 2>/dev/null || true; rmdir "$lock" 2>/dev/null || true' EXIT

# These reads cannot send review text or contact an API.
PYTHONPYCACHEPREFIX=/tmp/spotify-pycache python3 -m tools.checkpoint_500 \
  --input "$sample" --manifest "$manifest" --plan >/dev/null

print 'Ready for your existing TypeSafe key. Input is hidden; press Return to start the bounded 400-row Jev label run.'
read -rs 'pilot_key?Paste existing TypeSafe key: '
print
if [[ -z "$pilot_key" ]]; then
  print -u2 'No key entered; no calls made.'
  exit 1
fi

if TYPESAFE_API_KEY="$pilot_key" PYTHONPYCACHEPREFIX=/tmp/spotify-pycache \
    python3 -m tools.checkpoint_500 \
      --input "$sample" --manifest "$manifest" --db "$ledger" \
      --execute-labels --max-new-rows 400 --approve-new-review-transmission \
      --confirmed-input-rate-usd-per-million 0.042 --rate-checked-on 2026-10-06 \
      > "${result}.tmp"; then
  unset pilot_key
  mv "${result}.tmp" "$result"
  print "Checkpoint labels complete. Aggregate result: $repo_dir/$result"
else
  run_status=$?
  unset pilot_key
  rm -f "${result}.tmp"
  print -u2 'Checkpoint runner stopped. Inspect the saved ledger before any resume.'
  exit "$run_status"
fi
