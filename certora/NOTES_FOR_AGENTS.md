# Shared context for spec generators and judges (sDAI verification)

Project root: /Users/shelly/skill-sdai-v0.6/sdai  (makerdao/sdai @ 2b7acb9). Main contract: src/SavingsDai.sol:SavingsDai.

## Scene (certora/confs/SavingsDai.conf `files`)
- SavingsDai (main), PotHarness (certora/harnesses/PotHarness.sol = repo PotMock + mainnet Pot.drip()),
  VatMock, DaiJoinMock, DaiMock (src/test/mocks/, faithful copies of dss Vat/DaiJoin/Dai), DummyERC20Impl (autosetup mock, unused: sDAI.dai is linked to DaiMock).
- Links (certora/specs/summaries/SavingsDai_call_resolution.spec): sDAI.pot->PotHarness, sDAI.daiJoin->DaiJoinMock,
  sDAI.dai->DaiMock, sDAI.vat->VatMock, DaiJoinMock.vat->VatMock, DaiJoinMock.dai->DaiMock, PotHarness.vat->VatMock.
  `using` aliases defined there: savingsDai, potHarness, vatMock, daiJoinMock, daiMock, dummyERC20Impl. Do NOT redeclare them.
- Sanity (all 40 sDAI methods reachable) passed with this setup: job 2f6f6595-e837-45a6-8f93-096a5993bbfa.

## Required imports (every spec)
    import "summaries/SavingsDai_base_summaries.spec";
    import "summaries/SavingsDai_call_resolution.spec";
    import "summaries/rpow_summary.spec";
(paths are relative to certora/specs/). rpow_summary.spec summarizes both _rpow loops with one uninterpreted
function; read its header for the soundness story. It defines `definition RAY()`.
Component specs: `import "invariants.spec";` ONLY. Since barrier 1 it imports base + rpow summaries and INLINES the
call-resolution aliases/links (hooks in imported specs cannot see aliases from nested imports). Do not import the
summaries or the call-resolution file again, and do not copy invariants into your spec. invariants.spec also contains wildcard summaries for `_.vat()`, `_.dai()`, `_.hope(address)`,
`_.approve(address,uint256)` that fix unresolved calls in sDAI's constructor -- do NOT redeclare those entries.
Invariants (job 1080ee77-78e7-4afb-bb57-8a5da4e46a62, judge-accepted; chiAtLeastRay added at barrier 1), all proven over every method of the 5 scene contracts:
  totalSupplyEqualsSumOfBalances, sharesEqualPotPie, potTotalPieCoversSdaiPie, sdaiSetupPermissionsPersist,
  potTotalPieEqualsSumOfPie, noVatPermissionsFromPotOrDaiJoin(x), daiTotalSupplyEqualsSumOfDaiBalances, chiAtLeastRay: usable with requireInvariant.
  potVatDaiCoversSavings, daiJoinVatDaiCoversDaiSupply: proven under trusted governance (top-level caller not a Maker ward
  and not sDAI/Pot/DaiJoin) and setYield never called -- usable via requireInvariant; say so in your commentary when you rely on them.
  Helper requireUntrustedExternalCaller(e) is defined in invariants.spec. Read invariants.spec for their exact parameters.
Methods-block receivers must be SCENE contracts: use PotHarness.pie(...), not PotMock (PotMock is not in the scene;
only the internal PotMock._rpow entry works because it is inherited code). Check invariants.spec's methods block first and do not duplicate its entries.

## Conf overlay (write certora/confs/<slug>.conf)
Start from certora/confs/SavingsDai.conf, then set: "verify": "SavingsDai:certora/specs/<slug>.spec",
"parametric_contracts": ["SavingsDai"], "optimistic_loop": true, "rule_sanity": "basic", "msg": "<slug> iterN".
Keep "wait_for_results": "none" (see below). For rule filters add "rule": [...] to a COPY of the conf.

## Running the prover (IMPORTANT: commands run under a 15-minute cap; never wait on a job inside one command)
All from the project root:
- Typecheck (fast, ~1-2 min): `PATH="$PWD/certora/solc-bin:$PATH" certorail-run certora/submit.py -- certora/confs/<slug>.conf tc` does a full submit;
  for typecheck only, make a conf copy with "compilation_steps_only": true and submit with run.sh (it returns when done, no job).
- Submit:   `certora/run.sh certora/confs/<slug>.conf <tag>`   -> prints JOB <id>; writes certora/logs/<tag>.job.
  <tag> must be unique per run and use only letters, digits, _ and - (e.g. invariants_iter3).
- Poll:     `certora/status.sh <tag> 420`  (bash tool timeout 540000). Repeats until SUCCEEDED/FAILED/HALTED or 420s pass.
  Re-run it until the job ends; after each call write a one-line progress note. Never use background monitors/timers,
  and never end your turn while you own a running job.
- Results:  `certora/results.sh <tag>`  (per-rule status), `certora/results.sh <tag> --cex` (with counterexamples).
- Report link: https://app.certora.com/orgs/certora/jobs/<id>/report
Keep runs under ~15 minutes of prover time; split/summarize slow rules (see skill references).

## Design facts worth knowing
- RAY = 1e27. Pot: chi (ray), rho (last drip time), dsr (ray), pie[usr], Pie. Pot.join requires block.timestamp == rho.
  sDAI drips first when block.timestamp > rho. Vat.move(src,dst,rad) requires src == msg.sender or vat.can[src][msg.sender]==1.
- sDAI never stores pie itself; the Pot's pie[sDAI] is the backing for totalSupply.
- Maker governance (wards of Vat/Pot/Dai) is trusted and is not an adversary.
- References: /Users/shelly/.claude/plugins/cache/certora-skills/certora-autoprover/0.6.0/skills/certora-autoprover/references/
  (cvl-writing.md, cvl-pitfalls.md, prover-loop.md, property-classes.md). CVL docs: https://docs.certora.com/en/latest/docs/cvl/<page>.html
  (fetch with: certorail-run -c 'certora.exec("curl","-fsSL","-o","<abs out path>","<url>",cwd=".")' ; strip tags with sed).
