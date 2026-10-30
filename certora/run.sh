#!/bin/bash
# usage: certora/run.sh <conf> <tag> [extra certoraRun args]   (run from project root)
# Submits via certorail with wait_for_results none; prints JOB id. Log in certora/logs/<tag>.submit.log
set -u
cd /Users/shelly/skill-sdai-v0.6/sdai
export PATH="$PWD/certora/solc-bin:$PATH"
conf=$1; tag=$2; shift 2
certorail-run certora/submit.py -- "$conf" "$tag" > certora/logs/$tag.submit.log 2>&1
grep -E "JOB_URL|EXIT|ERROR|rror" certora/logs/$tag.submit.log | tail -8
job=$(grep JOB_URL certora/logs/$tag.submit.log | head -1 | sed -E 's#.*/jobs/([0-9a-f-]+)/report.*#\1#; s#.*/output/[0-9]+/([0-9a-f]+).*#\1#')
[ -n "$job" ] && echo "$job" > certora/logs/$tag.job && echo "JOB $job"
