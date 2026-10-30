VERDICT: REJECT

Judge round 1: erc4626-vault (spec certora/specs/erc4626-vault.spec, conf certora/confs/erc4626-vault.conf, run erc4626_iter2 / 25b859d6-9e44-44b9-95ac-7111f1caac64)

Summary: the rules are faithful to the source and strong. There are no unsourced tolerances and no trivializing summaries, and every bare require in the liveness rules traces to the property's own "sound Maker system" clause or to a revert path in the code. The rejection is structural:
- (1) the spec carries a copy of invariants.spec and a local chiAtLeastRay, instead of `import "invariants.spec";`;
- (2) the two expected-to-fail max rules do not, on their own, separate the genuine issue from their missing entry preconditions. A precondition-free witness rule is needed.

## 1. Code smells
- **Lines 5-338 are a verbatim copy of invariants.spec.**
  - Lines 5-7 import the three summary specs. Lines 9-338 are the copied body; `diff` against the current invariants.spec body shows it is identical.
  - Lines 358-366 add a local `chiAtLeastRay`.
  - NOTES_FOR_AGENTS.md forbids copying invariants and re-importing the summaries or call-resolution files.
  - `chiAtLeastRay` now lives in invariants.spec, proven over all five scene contracts (job 1080ee77-78e7-4afb-bb57-8a5da4e46a62). The local copy is proven over SavingsDai methods only, so it is weaker, and it would clash by name once imported.
  - See required change 1.
- **Methods block (lines 340-348):** `PotHarness.rho`, `PotHarness.dsr`, `DaiMock.balanceOf` and `maxRedeem` are envfree and used. None is in invariants.spec. No purposeless entries.
- **`maxRedeemIsBalance`** compares an implementation output (`maxRedeem`) with an independent storage getter (`balanceOf`). That is not a tautology.
- **No other smells.**
  - No type-bound requires, and no requires that only guard against reverts of non-`@withrevert` calls.
  - `require e.msg.sender != savingsDai` in `requireCanEnter` sits in a rule that is expected to fail. It can only make success easier, so it cannot rig that rule's failure.

## 2. Guideline compliance
No issue.
- Every rule ends in an assert.
- Pre/post snapshots are `mathint`. Contract results are `uint256`.
- `assert_uint256(now - rho)` is used only under `now > rho`.
- `method f` is always a rule parameter; `callWithParties` receives it as a parameter and does not declare one.
- In `maxWithdrawSucceeds`, the `@withrevert` return value `burned` is read only under `!reverted` (guideline 16).
- RAY and MAX_UINT256 are named definitions.
- No quantifiers. No bitwise operations.
- There are no `lastReverted <=>` revert-characteristic rules, so guideline-2's no-bare-require clause does not apply. The liveness rules are one-directional (`assert !lastReverted`) and are judged under criterion 4.

## 3. Precondition validity
No issue (with change 1 the invariants still come from the accepted file).
- iter1's spurious `chi == 0` states (withdrawEffectsExact, mintThenWithdrawNoProfit) are excluded by `requireInvariant chiAtLeastRay()`. That is the right fix, and it is now proven in invariants.spec over all contracts.
- The unchecked additions are bounded by proven invariants plus the Sload "summand <= sum" hooks:
  - `balanceOf[receiver] + shares` and `totalSupply + shares` in `_mint`;
  - `balanceOf[to] += value` in Dai.transferFrom and Dai.mint.
  - The proven invariants used are `requireShareAccounting` and `daiTotalSupplyEqualsSumOfDaiBalances`.
- The deposit/mint effects rules need no chi bound. With chi == 0, deposit reverts on division by zero, and mint yields 0 == ceilDiv(0, RAY).
- The rules that use no invariants are VERIFIED with rule_sanity basic, so no spurious prestate is hiding a failure: vaultVatDaiNeverDecreases, depositThenRedeemNoProfit, the preview rules, the donation rules, actionsDripToCurrentBlock and thirdPartyValueUnaffected.

## 4. Overconstrained inputs
I checked every bare require in the liveness rules against the revert paths of redeem/withdraw (SavingsDai.sol, PotHarness.drip, PotMock.exit, VatMock.move/suck, DaiJoinMock.exit, DaiMock.mint).

**redeemAlwaysPossible / maxRedeemSucceeds / maxWithdrawSucceeds.** Each require corresponds to a concrete revert site:
- `msg.value == 0`: the functions are non-payable.
- `receiver != 0 && != daiMock`: Dai.mint's `to` check; the property says "valid receiver".
- `shares <= balance`: the property's `b' <= b`.
- `vat.wards[pot] == 1`: vat.suck is auth.
- `dai.wards[daiJoin] == 1`: dai.mint is auth.
- `dsr >= RAY`: otherwise drip's checked `tmp - chi` reverts.
- `requireDripNoOverflow`:
  - `rpowG*chi` is the checked multiplication in drip;
  - `Pie*(chi'-chi)` is checked;
  - the four `suck` credits use checked `+` in Solidity 0.8.
- `requireExitNoOverflow`: the Vat credit in pot.exit (`dai[sDAI] + chi*shares`, which also bounds `shares*chi` in redeem) and the Vat credit in daiJoin.exit (`dai[daiJoin] + RAY*assets`).

The remaining success conditions come from proven invariants, not bare requires:
- Pot's Vat dai covers `chi*shares`: `potVatDaiCoversSavings`, carried through drip because suck credits `Pie*(chi'-chi)`.
- The Vat permission for daiJoin: `sdaiSetupPermissionsPersist`.
- `pie[sDAI] >= shares` and `Pie >= pie[sDAI]`: `sharesEqualPotPie`, `totalSupplyEqualsSumOfBalances`, `potTotalPieCoversSdaiPie`.
- Dai `totalSupply + assets` does not overflow: `daiJoinVatDaiCoversDaiSupply` plus the DaiJoin credit bound.

What the bare requires cover:
- The overflow requires are exactly the property's "rate accumulation does not overflow" (and Vat accounting, which is part of "Maker system is sound").
- The ward and dsr requires are trusted-governance configuration. NOTES: governance is trusted, and `Pot.cage` sets dsr = RAY, so "after cage" is included.
- Nothing restricts `live`, the caller (beyond `owner == caller`, which is the property's `self`), or `rho <= now`. The rules are broader than needed.
- For maxWithdrawSucceeds, `requireExitNoOverflow(now, balance)` matches the actual exit exactly:
  - `assets = floor(b*chi/RAY)` gives `RAY*assets` equal to the second bound;
  - `shares = ceil(assets*RAY/chi) <= b` keeps the first bound sufficient.
- Not rigged.

Non-blocking: the three governance facts (vat ward, dai ward, dsr) could be spec-local invariants proven under `requireUntrustedExternalCaller`, the same pattern as `potVatDaiCoversSavings`. Then they would be "true at deployment and never broken by non-governance methods" rather than assumed per state. The property's "Maker system is sound" clause covers them as bare requires, so I do not require this.

**maxDepositAccepted / maxMintAccepted** (`requireCanEnter`): nothing there rigs a failure.
- Every require helps deposit/mint succeed: caller funded and approved, valid receiver, rho <= now (needed by Pot.join), ward, dsr, chi >= RAY, drip no-overflow.
- Leaving out the DAI-supply invariants is necessary. With them, a balance of 2^256-1 is infeasible and the rule would be vacuous.

There is a fairness gap, though. These rules also lack the Maker-side entry conditions, which by design cannot hold for the amount 2^256-1:
- DaiJoin's Vat dai covers `RAY*assets` (DaiJoin.join's `vat.move` from daiJoin);
- the `dai[sDAI]` credit and the Pot's `dai[pot] + chi*shares` credit do not overflow;
- `Pie + shares` does not overflow.

So a hypothetically correct `maxDeposit` (e.g. `type(uint256).max / RAY`) could also violate the rules. The verdict "genuine issue" currently rests only on reading the counterexample: the revert is at `assets * RAY`, before any of those calls.

The issue itself is real. `assets * RAY` and `shares * chi` (chi >= RAY) are checked and overflow for the value `type(uint256).max` in every state. ERC-4626 says maxDeposit/maxMint "MUST NOT be higher than the actual maximum that would be accepted". It should be pinned by a rule that needs no preconditions: required change 2.

## 5. Trivializing summaries
No issue.
- The rpow summary is one deterministic uninterpreted `rpowG`, shared by `SavingsDai._rpow` and `PotMock._rpow`. The two are byte-for-byte the same algorithm with base RAY, and `rpowBaseCVL` asserts `base == RAY`.
- Its three constraints hold for the real rpow:
  - n=0 gives RAY;
  - n=1 gives x;
  - x >= RAY gives a result >= RAY, by half-up rounding of products of values >= RAY.
- The lost overflow reverts are re-stated as explicit assumptions in the liveness rules (`requireDripNoOverflow`), as the soundness note demands, and the property itself assumes them.
- Nothing is NONDET.
- The constructor-only UNRESOLVED wildcard entries come from invariants.spec and do not apply after construction.

## 6. Manifest errors
No issue.
- maxDepositAccepted and maxMintAccepted fail because of a genuine ERC-4626 deviation (see 4). Per the checklist that failure is the intended product and is not flagged.
- No other rule contradicts correct behaviour.

## 7. Meaningful contract interaction
No issue.
- **The `*EffectsExact` rules:**
  - Each compares the contract's return value with a CVL computation: floor(a*RAY/chi), ceilDiv(s*chi, RAY), ceilDiv(a*RAY, chi), floor(s*chi/RAY).
  - The CVL rounding matches `_divup` exactly, including x = 0.
  - Each also asserts DAI, share, totalSupply and Pot-pie deltas against that return value.
  - chi is read from the Pot after the call. On its own, that would not catch a contract that skips the drip. But `actionsDripToCurrentBlock` independently pins the post-call chi to `rpowG(dsr, now-rho)*chi/RAY`, computed from the pre-state. Together they establish "computed with the accrued, post-drip chi".
- **The preview rules:** each compares two distinct contract code paths (the view's extrapolation and the action's `pot.drip()`), in the same env and pre-state, with strict equality.
- **actionsDripToCurrentBlock** uses rpowG correctly.
  - `accruedChi` reads rho, chi and dsr before the call, so the arguments equal those drip later passes: sDAI calls drip first and nothing in between writes dsr.
  - Calling the ghost directly yields the same deterministic value that `rpowCVL` returns.
  - The `rhoBefore <= now =>` guard covers the unreachable `rho > now` state without assuming time monotonicity. In that state the chi assert still holds, because nothing drips.
- **Donation rules:** they really exercise donations, and none of the three donor calls is restricted:
  - `daiMock.transfer` to sDAI credits its DAI balance;
  - `vatMock.move(src, sDAI, rad)` credits its Vat dai (it needs only `wish(src, sender)`);
  - `daiJoinMock.join(sDAI, wad)` moves `RAY*wad` from DaiJoin's Vat dai to sDAI and burns the donor's DAI.
  - Each asserts that the contract's own views (`convertToShares`, `convertToAssets`, `totalAssets`) are unchanged.

## 8. Property coverage
All 14 properties are formalized. No tolerances anywhere.
- **The four effects properties:** every clause is asserted, and both deposit/mint overloads are covered through `withReferral`.
- **rounding_favors_vault:** strict `vat.dai(sDAI)` non-decrease, parametric over sDAI methods, with no requires.
  - Entry moves `+RAY*assets, -chi*shares`; exit moves `+chi*shares, -RAY*assets`. So the rule is exactly the property's two inequalities.
  - Donated Vat dai is free in the pre-state, so a net decrease could not hide behind an underflow revert.
- **round_trip_no_profit:** strict `assetsOut <= assets` and `sharesBurned >= shares`, with same-block envs as the property says. The general "no sequence" clause follows from the per-step rounding_favors_vault rule at a constant chi within one block. Only the base overloads are used; the referral overloads delegate, so this is acceptable.
- **preview_matches_action:** strict equality for all four previews. Elapsed time since the last drip is free, so the undripped case is included.
- **actions_price_at_accrued_rate:** `actionsDripToCurrentBlock` plus the effects rules.
- **third_party_value_unaffected:** strict equality of both balance and `convertToAssets(balance)`, in the same env. The parties are passed explicitly to every party-naming method.
- **share_price_independent_of_donations:** all three donation channels.
- **share_price_never_decreases:** `dsr >= RAY` is the property's own precondition.
- **deposit_pulls_only_from_caller:** parametric. sDAI's own balance is deliberately included.
- **redeem_always_possible:** see 4.
- **max_functions_accurate:** all four clauses. maxDeposit/maxMint need the witness in change 2 so that the reported violation is precondition-independent.

Non-blocking: `rule_sanity basic` shows that each rule is reachable as a whole, not that the drip branch (`now > rho`) is. Nothing in the specs restricts that branch, so I accept by inspection. A `satisfy` witness for `now > rho` in `actionsDripToCurrentBlock` would make it explicit.

## Required changes
1. **Use the accepted invariants file.**
   - Replace lines 5-7 (the three summary imports), the verbatim block (lines 9-338) and the local `invariant chiAtLeastRay` (lines 351-366) with the single line `import "invariants.spec";`.
   - Keep the local methods block (lines 340-348); none of its entries is in invariants.spec.
   - Every `requireInvariant chiAtLeastRay()` then refers to the invariants.spec version, proven over all five scene contracts in job 1080ee77-78e7-4afb-bb57-8a5da4e46a62.
2. **Add precondition-free witness rules for the two genuine issues.** Keep maxDepositAccepted and maxMintAccepted unchanged as the property formalizations.
   - `rule maxDepositAlwaysReverts(env e, address receiver) { uint256 a = maxDeposit(e, receiver); deposit@withrevert(e, a, receiver); assert lastReverted; }`, with no requires.
   - `rule maxMintAlwaysReverts(env e, address receiver) { requireInvariant chiAtLeastRay(); uint256 s = maxMint(e, receiver); mint@withrevert(e, s, receiver); assert lastReverted; }`
   - Both are expected VERIFIED. They show that deposit/mint of the advertised maximum reverts in every state (respectively every state with chi >= RAY), independent of the entry preconditions that maxDeposit/maxMintAccepted omit (see criterion 4).
   - Add both to `max_functions_accurate` in property_rules.json, and cite them in the commentary as the evidence for the genuine issue.
3. **Re-run and update the commentary.**
   - Re-run the conf unfiltered with `rule_sanity: basic`.
   - Update erc4626-vault.commentary.md: drop the "import workaround" section and the STRUCTURAL-INVARIANT REQUEST; state that chiAtLeastRay comes from invariants.spec (job 1080ee77); record the new job.
   - Expected result: everything VERIFIED except maxDepositAccepted and maxMintAccepted (genuine), with the two new witness rules VERIFIED.
