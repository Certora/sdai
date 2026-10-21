# invariants — commentary

Run (iter 2, full, unfiltered): https://prover.certora.com/orgs/certora/jobs/b91ff71e-7cb3-4cc9-85b5-b30457145a95/report — all VERIFIED, rule_sanity basic.

- `totalSupplyIsSumOfBalances`: ghost `sumOfBalances` maintained by an Sstore hook on `balanceOf`, with an Sload hook bounding each read balance by the sum. Iter 1 failed on deposit/mint because `_mint` adds unchecked; the Pot.join of the same shares is checked, so the preserved block `requireInvariant sharesBackedByPie()` rules the wrap out.
- `sharesBackedByPie`: `pot.pie(sDAI) >= totalSupply`. Iter 1 failed on withdraw/redeem (unchecked `totalSupply - shares`); `requireInvariant totalSupplyIsSumOfBalances()` gives `shares <= balance <= totalSupply`. Mutual requireInvariant is sound (simultaneous induction).
- `zeroAndSelfHoldNoShares`: no preconditions needed.
- Iter 1 base case of the sum invariant failed because the constructor's calls to still-arbitrary addresses (vat.hope, dai.approve) were unresolved and havoced every ghost. scene.spec adds wildcard NONDET summaries for hope/approve/vat/dai under the default UNRESOLVED policy, which only fires for those constructor calls; linked calls keep real code. Sound because a contract under construction has no code and cannot be re-entered.
- Trust assumptions: `_rpow` summarized by the ghost function `rpowG` (never reverts). Pot and Vat are verification models (certora/harnesses).
- `parametric_contracts: ["SavingsDai"]`: invariants range over SavingsDai's methods; the scene models (Pot, Vat, DaiJoinMock, DaiMock) are external MakerDAO components whose own correctness is outside this task. `optimistic_loop` only affects permit's memory-copy loops (rpow loops are summarized), which these invariants don't read.
- Judge round 1: ACCEPT (certora/properties/invariants.judge-round1.md).

## Pass 2
Scene changed (DaiMock/DaiJoinMock -> faithful dss Dai/DaiJoin ports, SigPacker added). Spec unchanged; barrier re-run, full and unfiltered: all VERIFIED — https://prover.certora.com/orgs/certora/jobs/7a094bd0-a0b9-4458-aaaa-d308a0c25dbd/report
