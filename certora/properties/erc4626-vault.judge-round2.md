VERDICT: ACCEPT

Judge round 2: erc4626-vault (spec certora/specs/erc4626-vault.spec, conf certora/confs/erc4626-vault.conf, run erc4626_iter3 / 59ab9ca6-d468-4b07-8b67-604dcf1ed984)

Re-read from disk.
- **Unchanged since round 1:** the helper and rule bodies (spec lines 18-361 now, lines 368-711 in round 1). A `diff` shows them byte-identical, so the round-1 analysis of every one of these rules still holds.
- **Changed:**
  - the head of the file (now `import "invariants.spec";` alone);
  - two new witness rules: maxDepositAlwaysReverts and maxMintAlwaysReverts;
  - one new satisfy rule: actionDripBranchReachable;
  - property_rules.json;
  - the commentary.

## 1. Code smells
No issue.
- Round-1 required change 1 is done:
  - the three summary imports, the verbatim copy of invariants.spec and the local `chiAtLeastRay` are gone;
  - the spec opens with `import "invariants.spec";` only.
- The local methods block (`PotHarness.rho`, `PotHarness.dsr`, `DaiMock.balanceOf`, `maxRedeem`, all envfree and all used) duplicates nothing in invariants.spec.
- The new rules contain no superfluous requires.

## 2. Guideline compliance
No issue.
- maxDepositAlwaysReverts and maxMintAlwaysReverts end in an assert, and they read only `lastReverted` after the `@withrevert` call.
- actionDripBranchReachable ends in `satisfy`.
- Snapshots are typed `uint256` from contract calls, which guideline 3 allows.

## 3. Precondition validity
No issue.
- `requireInvariant chiAtLeastRay()` now refers to the version in invariants.spec, proven over all five scene contracts (job 1080ee77-78e7-4afb-bb57-8a5da4e46a62).
- The commentary records the invariants' jobs and states that this conf does not re-check the imported invariants.

## 4. Overconstrained inputs
No issue.
- **Liveness rules:** their preconditions are unchanged and were accepted in round 1. Every bare require traces to a revert site and to the property's "Maker system is sound" or "rate accumulation does not overflow" clauses.
- **maxDepositAlwaysReverts** has no requires. Every path reverts:
  - in the drip branch, drip either reverts or returns chi;
  - in every case `type(uint256).max * RAY` then overflows checked arithmetic.
- **maxMintAlwaysReverts** assumes only the proven invariant `chi >= RAY`. The chi after drip is at least the pre-drip chi, because of the checked `tmp - chi`, so `type(uint256).max * chi` overflows.
- These VERIFIED rules establish the ERC-4626 deviation regardless of the entry preconditions that maxDepositAccepted and maxMintAccepted omit. That closes the round-1 fairness gap.

## 5. Trivializing summaries
No issue. Only the shared, accepted summaries are used: the rpow summary (one uninterpreted rpowG) and the constructor-only UNRESOLVED entries in invariants.spec.

## 6. Manifest errors
No issue.
- maxDepositAccepted and maxMintAccepted are VIOLATED because of a genuine issue: maxDeposit and maxMint return `type(uint256).max`, and deposit/mint of that amount always revert. The witness rules now prove this.
- They are not flagged.

## 7. Meaningful contract interaction
No issue.
- The two witness rules assert on the contract's revert behaviour when called with the contract's own `maxDeposit` / `maxMint` output.
- actionDripBranchReachable shows that an action (redeem) in a state with `now > rho` ends with `rho == now`, `chi != 0` and `shares > 0`.
  - So the drip branch that actionsDripToCurrentBlock relies on is reachable.
  - The witness uses redeem only. That suffices: all six actions share the same `pot.drip()` prologue.

## 8. Property coverage
No issue.
- All 14 properties remain formalized as in round 1, with strict assertions and no tolerances.
- `max_functions_accurate` now also maps the two witness rules.
- `actions_price_at_accrued_rate` maps the reachability witness.

## Required changes
None.
