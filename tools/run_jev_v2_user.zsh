#!/bin/zsh
# Run this script yourself in a visible Terminal. It never stores the API key.
set +x
set -euo pipefail
umask 077

repo_dir=${0:A:h:h}
cd "$repo_dir"

sample='/Users/haniframadhan/Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset/cost_100.csv'
manifest='/Users/haniframadhan/Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset/manifest.json'
ledger='local/jev_pilot_v2.db'
result='local/jev_pilot_v2_run.json'
timing='local/jev_pilot_v2_timing.json'
lock='local/jev_pilot_v2_launch.lock'

mkdir -p local
if [[ -e "$ledger" || -e "$result" || -e "${result}.tmp" || -e "$timing" || -e "${timing}.tmp" || -e "${ledger}-wal" || -e "${ledger}-shm" ]]; then
  print -u2 'A v2 ledger or result already exists. Stop and inspect it; this launcher will not repeat calls.'
  exit 1
fi
if ! mkdir "$lock" 2>/dev/null; then
  print -u2 'A v2 launch lock exists. Stop and inspect the prior launch.'
  exit 1
fi
trap 'rmdir "$lock" 2>/dev/null || true' EXIT

# The runner verifies the exact source hash and manifest before it can call Jev.
python3 -m tools.jev_pilot --input "$sample" --manifest "$manifest" >/dev/null

print 'Ready for the existing TypeSafe key. Input is hidden; press Return to start the bounded v2 run.'
read -rs 'pilot_key?Paste existing TypeSafe key: '
print
if [[ -z "$pilot_key" ]]; then
  print -u2 'No key entered; no calls made.'
  exit 1
fi

# v1 measured cost is USD 0.003691254. The remaining cumulative cap is USD 0.596308746.
if TYPESAFE_API_KEY="$pilot_key" python3 -m tools.jev_pilot \
    --input "$sample" --manifest "$manifest" --db "$ledger" \
    --execute --approved-cap-usd 0.596308746 > "${result}.tmp"; then
  run_status=0
else
  run_status=$?
fi
unset pilot_key
python3 - "${result}.tmp" "$run_status" > "${timing}.tmp" <<'PY'
import json
import sys
result_path, status = sys.argv[1], int(sys.argv[2])
wall = None
if status == 0:
    with open(result_path, encoding="utf-8") as stream:
        wall = json.load(stream)["runner_wall_seconds"]
print(json.dumps({"scope": "paid runner, including account access check",
                  "wall_seconds": wall,
                  "runner_exit_code": status}, indent=2))
PY
mv "${timing}.tmp" "$timing"
if (( run_status != 0 )); then
  print -u2 'V2 runner stopped. Inspect the new ledger and timing; do not repeat uncertain calls.'
  exit "$run_status"
fi
mv "${result}.tmp" "$result"
print "V2 run complete. Aggregate result: $repo_dir/$result"
