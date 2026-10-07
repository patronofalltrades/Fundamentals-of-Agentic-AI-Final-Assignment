#!/bin/zsh
# User-only hidden TypeSafe key entry. The key is never printed or saved.
set +x
set -euo pipefail
umask 077
cd "${0:A:h:h}"
mode="${1:-}"
if [[ "$mode" != "first100" && "$mode" != "rest" ]]; then
  print -u2 'Use first100 or rest after the first-100 evidence quality gate.'
  exit 2
fi
if [[ ! -f local/checkpoint5000_manifest.json || ! -f local/project_budget.db ]]; then
  print -u2 'Prepared private manifest or shared project ledger is missing.'
  exit 2
fi
PYTHONPYCACHEPREFIX=/tmp/spotify-pycache python3 -m tools.checkpoint5000_dispatch --status
print 'Enter the existing TypeSafe key. Input is hidden. This command sends only approved first-5000 source texts and stops at the shared USD 0.60 Jev cap.'
read -rs 'pilot_key?TypeSafe key: '
print
if [[ -z "$pilot_key" ]]; then
  print -u2 'No key entered; no paid call made.'
  exit 2
fi
args=(--run-labels --jev-price-checked-on "$(date +%Y-%m-%d)")
if [[ "$mode" == "first100" ]]; then
  args+=(--first-100)
fi
TYPESAFE_API_KEY="$pilot_key" PYTHONPYCACHEPREFIX=/tmp/spotify-pycache \
  python3 -m tools.checkpoint5000_dispatch "${args[@]}"
unset pilot_key
