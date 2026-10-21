# Generator brief (Phase 6) — SavingsDai

Project root: `/Users/shelly/skill-sdai`. Main contract: `src/SavingsDai.sol:SavingsDai`.

## Scene (fixed — do not edit these files; hand back requests instead)
- `certora/confs/base.conf` — autosetup base conf + explicit `link`s (SavingsDai.pot/vat/daiJoin/dai, DaiJoin.vat/dai, Pot.vat).
- Contracts (PASS 2 scene): `SavingsDai`, `Pot` (certora/harnesses/Pot.sol, port of dss pot.sol), `Vat` (certora/harnesses/Vat.sol, DAI ledger only), `DaiJoin` (certora/harnesses/DaiJoin.sol, port of the real dss DaiJoin: has `live`/`cage`, `exit` requires live == 1), `Dai` (certora/harnesses/Dai.sol, port of mainnet dss dai.sol v1: checked math, no receiver checks, push/pull/move, DAI-style permit), `SigPacker` (certora/harnesses/SigPacker.sol: `pack(v, r, s)` returns abi.encodePacked(r, s, v)). DaiJoinMock / DaiMock are NO LONGER in the scene.
- `certora/specs/scene.spec` — `_rpow` in SavingsDai and Pot summarized by one ghost function `rpowG(x, n, base)`; `_.isValidSignature` NONDET. Defines `RAY()`.
- `certora/specs/invariants.spec` — proven structural invariants: `totalSupplyIsSumOfBalances()`, `sharesBackedByPie()`, `zeroAndSelfHoldNoShares()` (plus the `sumOfBalances` ghost + hooks). It declares `using Pot as pot;` and envfree `totalSupply`, `balanceOf`, `Pot.pie`.

Every spec MUST start with these imports (paths relative to `certora/specs/`):
```
import "summaries/SavingsDai_base_summaries.spec";
import "summaries/SavingsDai_call_resolution.spec";
import "scene.spec";
import "invariants.spec";
```
(Importing invariants.spec brings in `using Pot as pot` — do not redeclare that alias; add your own `using` lines for other contracts, e.g. `using Dai as daiToken; using Vat as vatC; using DaiJoin as join;` — check alias names don't clash with SavingsDai getters like `dai()`, `vat()`, `pot()`.)

## Conf
Write `certora/confs/<slug>.conf` = `certora/confs/invariants.conf` with `verify` changed to `SavingsDai:certora/specs/<slug>.spec` and `msg` to `"<slug> iter N"` (msg chars: letters, digits, spaces and `()[]'"-_.,:/\=*$` only). Keep `rule_sanity: basic`, `optimistic_loop`, `wait_for_results: all`, `parametric_contracts: ["SavingsDai"]`, links. You may add `"rule": [...]` for cheap iterations but the final run must have no rule filter. If you need `precise_bitwise_ops` or `smt_timeout`/`prover_args` tweaks, add them to your own conf only and note it.

## Running (all tool commands go through certorail)
```
cd /Users/shelly && export PATH=/Users/shelly/skill-sdai/certora/solc-bin:$HOME/.foundry/bin:$PATH
certorail-run skill-sdai/certora/run.py -- certora/confs/<slug>.conf typecheck      # ~10s, foreground
certorail-run skill-sdai/certora/run.py -- certora/confs/<slug>.conf > skill-sdai/certora/logs/<slug>_runN.log 2>&1   # full run
```
Run full runs in the background (your Bash tool's run_in_background) and poll the log tail. The log prints the report link (`https://prover.certora.com/orgs/certora/jobs/<JOBID>/report`) and at the end lists failing rules per method (or "No errors found by Prover!"). Runs take ~2-10 min.

Counterexamples: download the run's output archive (job id = the UUID in the report link, dashes removed) with the authenticated downloader:
```
S=<your own scratch dir under /private/tmp/claude-501/-Users-shelly-skill-sdai/bd91409c-2ea4-42cb-8ac6-325befdb2dbb/scratchpad/>
cd /Users/shelly && certorail-run /private/tmp/claude-501/-Users-shelly-skill-sdai/bd91409c-2ea4-42cb-8ac6-325befdb2dbb/scratchpad/dl.py -- "https://data-api.certora.com/v1/domain/jobs/<JOBID_NO_DASHES>/f/outputs" $S/run.tgz
mkdir -p $S/run && tar xzf $S/run.tgz -C $S/run
```
Then `$S/run/*/Reports/ctpp_<rule>-<method>.txt` is a readable call trace per violated rule/method (skip Setup / "Evaluate branch condition" noise). Never print or copy `scratchpad/auth.hdr` (it holds the API key).

## References (read before writing CVL)
- `/Users/shelly/.claude-iso/sdai-with-skill/config/skills/certora-verify/references/cvl-writing.md` (23 guidelines + judge checklist)
- `/Users/shelly/.claude-iso/sdai-with-skill/config/skills/certora-verify/references/cvl-pitfalls.md`
- `/Users/shelly/.claude-iso/sdai-with-skill/config/skills/certora-verify/references/prover-loop.md` (counterexample triage table)
- Docs pages already fetched as text: `/private/tmp/claude-501/-Users-shelly-skill-sdai/bd91409c-2ea4-42cb-8ac6-325befdb2dbb/scratchpad/docs/{hooks,ghosts,invariants,methods,using}.txt`. Fetch others from https://docs.certora.com/en/latest/docs/cvl/<page>.html with curl via certorail if needed.

## Rules of the road
- Formalize each property so VERIFIED = good thing holds / attack impossible.
- Prefer `requireInvariant` of the proven invariants over bare `require`. Every bare `require` needs a comment justifying it; it will be scrutinized.
- Never NONDET a side-effecting function; never `persistent` ghosts to dodge havocs.
- Do NOT edit invariants.spec, scene.spec, base.conf, harnesses, or contract sources. If you need a new structural invariant or scene change, describe it in your hand-back.
- A rule that fails because the contract genuinely violates the property is a FINDING: keep the rule, mark it expected-to-fail with the CEX scenario. Do not weaken it.
- A property you believe is invalid: skip with justification (attempt it first).

## Deliverables
1. `certora/specs/<slug>.spec`
2. `certora/confs/<slug>.conf`
3. `certora/properties/<slug>.property_rules.json` — `{"<property title>": ["ruleName", ...], ...}` plus `"_skipped": {"<title>": "<reason>"}` and `"_expected_fail": {"<rule>": {"reason": "finding|prover_limitation", "detail": "..."}}`.
4. `certora/properties/<slug>.commentary.md` — decisions, summaries, trust assumptions, expected failures with CEX scenario.
5. Final message: report link of the final FULL unfiltered run, per-rule status table, expected-fail list, skipped list, any structural-invariant / scene requests.
