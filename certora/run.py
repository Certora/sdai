import sys
# Usage: certorail-run skill-sdai/certora/run.py -- <conf relative to project> [typecheck]
argv = sys.argv[1:]
conf = argv[0]
if len(argv) > 1 and argv[1] == "typecheck":
    r = certora.exec("certoraRun", conf, "--compilation_steps_only", cwd="skill-sdai", stream=True)
else:
    r = certora.exec("certoraRun", conf, cwd="skill-sdai", stream=True)
print("EXIT", r.returncode)
