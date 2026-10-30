#!/bin/bash
# usage: certora/results.sh <tag>  -> downloads outputs and prints per-rule statuses + counterexamples
cd /Users/shelly/skill-sdai-v0.6/sdai
job=$(cat certora/logs/$1.job | tr -d '-'); out=certora/logs/$1_out
rm -rf $out; mkdir -p $out
curl -fsSL -H "Authorization: Bearer $CERTORAKEY" "https://data-api.certora.com/v1/domain/jobs/$job/f/outputs" -o certora/logs/$1.tar.gz || { echo "download failed"; exit 1; }
tar xzf certora/logs/$1.tar.gz -C $out
"$(uv tool dir)"/ai-composer/bin/python -c '
import sys, pathlib
from composer.prover.results import read_and_format_run_result
results = read_and_format_run_result(pathlib.Path(sys.argv[1]), "evm")
if isinstance(results, str): sys.exit(results)
for r in results.values():
    print(r.path.rule, r.path.contract or "", r.path.method or "", r.status, sep="\t")
    for m in r.error_messages: print("  error:", m)
    if r.counterexample and "--cex" in sys.argv: print(r.counterexample.render())
' $out/*/ "${@:2}"
