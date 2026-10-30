VERDICT: ACCEPT

Spec: certora/specs/invariants.spec (round 2). Conf: certora/confs/invariants.conf. Run: tag invariants_iter3, job 3c95349d-c8a0-4655-ad5a-4285034a5ed9, all VERIFIED with rule_sanity basic, unfiltered.

Status of the round-1 required changes:
1. potTotalPieCoversSdaiPie: done. It is now proven over all 52 methods plus the constructor, using the supporting invariant potTotalPieEqualsSumOfPie.
2. potVatDaiCoversSavings and daiJoinVatDaiCoversDaiSupply: done.
   - The blanket filter is gone. The only exclusion is `PotHarness.setYield`, by selector and only on potVatDaiCoversSavings.
   - Governance trust is stated explicitly: the top-level caller is not a ward.
   - The caller is not sDAI, the Pot or DaiJoin.
   - The new supporting invariant noVatPermissionsFromPotOrDaiJoin(x) is used through requireInvariant.
3. Commentary: done. It now records the final scope of every invariant and every bare require. NOTES_FOR_AGENTS.md no longer advertises the three formerly filtered invariants for unconditional use; it points readers to the commentary. The orchestrator should fold the final scope into NOTES. That is a bookkeeping step, not a spec defect.

## 1. Code smells
No issue. The redundant `to_mathint` wrappers and the unused `env` binding I flagged in round 1 have been removed. Every methods-block entry is used, and there are no tautological asserts.

## 2. Guideline compliance
No issue.
- The invariant `noVatPermissionsFromPotOrDaiJoin(address x)` takes a parameter instead of using `forall`, as rule 22 asks.
- The CVL helper `requireUntrustedExternalCaller` returns void and omits the returns clause, as rules 14 and 15 require.
- Each `preserved constructor()` that requires the invariant's own predicate does so on pre-existing Maker state. This is the same pattern I accepted in round 1: the invariant is not auto-assumed in the base step, and sDAI's constructor provably does not write the state involved.

## 3. Precondition validity
No issue. Every supporting fact needed for the widened scope is a proven invariant, used through requireInvariant:
- `Pie == Σ pie` (potTotalPieEqualsSumOfPie);
- `can[Pot][x] == 0 && can[DaiJoin][x] == 0` (noVatPermissionsFromPotOrDaiJoin);
- `Dai.totalSupply == Σ balanceOf` (daiTotalSupplyEqualsSumOfDaiBalances).

I checked by hand that these are enough for the permissionless paths that touch `Vat.dai[pot]`, `Vat.dai[daiJoin]`, `Pie` or `Dai.totalSupply`:
- Vat.move from the Pot or DaiJoin needs `wish(src, sender)`.
- Vat.frob with `w ∈ {Pot, DaiJoin}` and `dart < 0` also needs `wish`.
- Vat.heal only touches `dai[msg.sender]`.
- Pot.join, Pot.exit and drip keep `dai[pot] ≥ chi·Pie`, because drip's checked `tmp - chi` together with `suck(Pie·Δchi)` covers the increase.
- DaiJoin.join and DaiJoin.exit move exactly `RAY·wad` against `wad` of DAI.
- Dai.burn only lowers totalSupply.

## 4. Overconstrained inputs
Every new bare require was examined, and all are acceptable.
- **Two-summand load hook on pie**, `a != savingsDai => p + pie[savingsDai] <= sumPie`. For distinct a and sDAI these are two non-negative summands of Σ pie, so the bound is true in every state where sumPie is the real sum. The hook keeps sumPie exact at every load, because every Sstore updates it. Where potTotalPieEqualsSumOfPie is not required, sumPie is free and the require only bounds a free variable. The read of `potHarness.pie[savingsDai]` inside the hook is a CVL storage read, so it does not re-trigger the hook. No vacuity: sanity passed.
- **`requireUntrustedExternalCaller(e)`**:
  - *Not a ward of Vat, Pot or Dai.* This is the "Maker governance is trusted" assumption, now stated precisely instead of as a blanket method filter, which is what round 1 asked for. It restricts only the top-level caller. The nested calls that need ward rights (Pot.drip → Vat.suck, DaiJoin.exit → Dai.mint) still run with the contract as msg.sender, so drip and DaiJoin.exit are fully checked.
    - The restriction also removes the case of a ward calling sDAI's own methods. No sDAI code path depends on whether its caller is a ward: every nested call is made with msg.sender equal to sDAI, the Pot or DaiJoin. So no reachable behaviour is hidden. Not blocking.
  - *Not sDAI, the Pot or DaiJoin.* These are CREATE-deployed contracts with no private key, so they never start a transaction. Every state-changing call they make runs inside their own methods, and those methods are checked in the same invariant. Their only other outgoing call is sDAI's and Dai's ERC-1271 `staticcall`, which cannot write state. This is the same justification I accepted in round 1.
- **noVatPermissionsFromPotOrDaiJoin: `msg.sender ∉ {potHarness, daiJoinMock}`.** Same justification. Neither Pot nor DaiJoin has a code path that calls hope or nope.
- **New Maker-state constructor requires** (`Pie == sumPie`; Pot and DaiJoin hold no `can`). Both hold from Maker's all-zero deployment. Both are now backed by preservation over every scene method, which round 1 made the condition for accepting these requires. sDAI's constructor writes only `Vat.can[sDAI][*]` and `Dai.allowance[sDAI][*]`.
- **No `msg.sender != savingsDai` on potTotalPieCoversSdaiPie.** Correct, and better than what I proposed in round 1. Pot.join and Pot.exit by sDAI change `Pie` and `pie[sDAI]` by the same amount, so the require is not needed. Fewer assumptions.
- **Requires carried over from round 1** (constructor-resolution summaries, `pie[sDAI] == 0` at deployment, the DaiMock.permit `owner != savingsDai` ECDSA assumption, the one-summand hooks): unchanged and still accepted.

## 5. Trivializing summaries
No issue. Nothing changed here since round 1: the rpow over-approximation states only true facts about the real function, and the constructor-only UNRESOLVED summaries run real callee code.

## 6. Manifest errors
No issue.

## 7. Meaningful contract interaction
No issue. Every invariant, including the three supporting ones, compares contract storage or getters. The ghosts are tied to storage through Sstore hooks.

## 8. Property coverage
No issue. All six properties are formalized, and property_rules.json lists the supporting invariants each one depends on.
- Every invariant is proven over all methods of SavingsDai, PotHarness, VatMock, DaiJoinMock and DaiMock, plus the constructor.
- The only method exclusion is `PotHarness.setYield` on potVatDaiCoversSavings. It is justified:
  - setYield is PotMock's test hook, and mainnet Pot has no such function;
  - its suck amount (`Pie·yield`) is inconsistent in units with its new chi;
  - the harness restores mainnet `drip()`, which is checked and verified.

## Required changes
None.

Advisory, not blocking: the orchestrator should update NOTES_FOR_AGENTS.md lines 22–25 with the final round-2 scope from the commentary. All seven invariants are proven over every scene method. potVatDaiCoversSavings additionally assumes trusted governance and no setYield; daiJoinVatDaiCoversDaiSupply additionally assumes trusted governance.
