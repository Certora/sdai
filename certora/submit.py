# usage: certorail-run certora/submit.py -- <conf relative to project> <msg>
# Submits a prover job without waiting for results (works within certorail's 900s exec cap).
# Rule filters go in the conf ("rule": [...]), not on the command line.
import sys
import re
conf = sys.argv[1]
msg = sys.argv[2]
if conf.startswith("-") or msg.startswith("-"):
    raise SystemExit("bad args")
r = certora.exec("certoraRun", conf, "--msg", msg, "--wait_for_results", "none", cwd="/Users/shelly/skill-sdai-v0.6/sdai")
out = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
print(out[-3000:])
for m in re.findall(r"https://\S+/jobs/[0-9a-f-]+/report|https://prover\.certora\.com/output/\S+", out):
    print("JOB_URL", m)
print("EXIT", r.returncode)
