#!/bin/bash
# usage: certora/status.sh <tag> [wait_seconds]  -> polls job status until ended or wait bound passes
cd /Users/shelly/skill-sdai-v0.6/sdai
job=$(cat certora/logs/$1.job); end=$(( $(date +%s) + ${2:-0} ))
while :; do
  s=$("$(uv tool dir)"/ai-composer/bin/prover-cli --job-id "$job" --status-only --format json 2>&1)
  st=$(echo "$s" | grep -oE '"(status|jobStatus)"[^,}]*' | head -1)
  case "$s" in *SUCCEEDED*|*FAILED*|*HALTED*|*ERROR*) break;; esac
  [ "$(date +%s)" -ge "$end" ] && break
  sleep 30
done
echo "$s" | head -c 600; echo
