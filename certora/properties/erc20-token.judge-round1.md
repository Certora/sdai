VERDICT: REJECT

Judge round 1: erc20-token (spec certora/specs/erc20-token.spec, conf certora/confs/erc20-token.conf, run erc20_token_iter2 / 6d16a4fe-5e91-4bc1-b6c6-ab606be4620e)

## 1. Code smells
- The spec still carries the "verbatim excerpt" of invariants.spec and imports the three summary specs directly.
  - That excerpt is now stale. Since barrier 1, invariants.spec inlines the aliases and links, and it adds the DAI-sum and pie-sum ghosts and hooks plus more methods entries (VatMock.can, DaiMock.totalSupply, DaiMock.allowance).
  - So the excerpt no longer equals the judge-accepted file, and the commentary's "verbatim" claim is false.
  - Copying invariants into a component spec is also explicitly forbidden by NOTES_FOR_AGENTS.md.
  - See required change 1.
- Methods entries: `allowance(address,address)` and `DaiMock.balanceOf(address)` are both envfree and used, and neither is in invariants.spec. No purposeless entries.
- No tautological asserts. No type-bound requires. No requires that only guard against reverts.

## 2. Guideline compliance
No issue.
- Every rule ends in an assert. `method f` is a rule parameter. Mathint is used for snapshots.
- Return values of `@withrevert` calls are read only under `!reverted`.
- The max allowance is named with a definition (`MAX_ALLOWANCE`).
- The revert-characteristic rules (transferRevertConditions, transferFromRevertConditions, and the `reverted <=>` asserts in approve/increaseAllowance/decreaseAllowance) contain no `require` and no `requireInvariant`.
- After the import, imported invariants are not re-checked unless you add `use invariant` (docs/cvl/imports.html). That is fine: they were proven over all scene methods in job 1080ee77.

## 3. Precondition validity
No issue on the substance.
- **Revert `<=>` predicates** are complete against the source:
  - transfer: non-payable; `to != 0 && to != this`; `balance >= value`; the credit is unchecked, so there is no overflow revert.
  - transferFrom: the same, plus the allowance check only when `from != msg.sender` and the allowance is not max. The decrement is unchecked.
  - approve: only non-payability.
  - increaseAllowance: checked `+`.
  - decreaseAllowance: `allowed >= subtractedValue`.
- **Unchecked additions:**
  - transfer and transferFrom credits are covered by `requireInvariant totalSupplyEqualsSumOfBalances` plus the "balance <= sum" Sload hook.
  - The `_mint` credit in the parametric balance rule is covered by `requireInvariant sharesEqualPotPie`, because Pot.join adds the same shares to pie[sDAI] with checked arithmetic.
  - Both invariants are judge-accepted (job 1080ee77).
- **Sload hooks without their invariant.** In rules that do not requireInvariant the matching sum invariant, the shared Sload hooks constrain only a free ghost: sumBalances, and after the import also sumDaiBalances and sumPie. A sufficiently large initial ghost value always satisfies them, so they prune no contract state and do not truncate the `<=>` claims. The re-run after change 1 must still confirm this; rule_sanity is already on.

## 4. Overconstrained inputs
No issue.
- The component rules contain no bare `require`.
- The only bare requires in the file are the excerpted constructor-resolution requires, the Sload-hook requires and the sharesEqualPotPie preserved-block requires. All were judge-accepted in invariants.spec.
- With change 1 they leave this file entirely.

## 5. Trivializing summaries
No issue.
- No component summaries.
- The rpow summary (shared, accepted) is irrelevant to these rules.
- The permit signature path (ecrecover plus the ERC-1271 staticcall) is left unsummarized.
- Every assertion holds for both signature-check outcomes.

## 6. Manifest errors
None.
- Every assertion matches the obviously correct ERC-20 behaviour of the code: self-transfer is a no-op, the owner is exempt in transferFrom and `_burn`, and an infinite allowance is not decremented.

## 7. Meaningful contract interaction
No issue.
- Every assertion compares post-state contract reads (balanceOf, allowance, totalSupply, Pot pie, Dai balanceOf, Vat dai) or return values / `lastReverted` against pre-state contract reads.

## 8. Property coverage
All 8 properties are mapped and formalized at full strength, with one exception: allowance_increase_requires_owner_authorization.
- **Covered at full strength:**
  - transfer_moves_exact_amount and transfer_from_moves_exact_amount_and_spends_allowance: exact amounts, the self case, an arbitrary third account, totalSupply, and all three allowance cases.
  - Both revert properties, as exact `<=>`.
  - balance_decrease_requires_owner_or_allowance: parametric over all SavingsDai methods.
    - For withdraw/redeem, `decrease` equals `shares`. The rule forces either `caller == owner`, or `allowBefore >= shares` with the allowance unchanged if it is max and otherwise lowered by exactly the decrease. This is the full property, not a weakening.
  - allowance_management_functions_correct: three rules, with exact revert conditions, exact results, other allowances and balances.
  - erc20_ops_preserve_vault_backing: the filter equals the five functions the property names.
- **Weaker than its text: allowance_increase_requires_owner_authorization.** Assertion (b) of allowanceChangeRequiresAuthorization accepts `caller == spender && allowAfter < allowBefore` from *any* method. The property excepts only "spending by the caller as spender".
  - Spending happens only in transferFrom (from == owner), withdraw (owner) and redeem (owner).
  - A bug where, say, `transfer`, `deposit` or `approve` silently lowered `allowance[x][msg.sender]` would pass both this rule and the balance-decrease rule, because no balance decreases.
  - The real code satisfies the stricter form. See required change 2.

## Required changes
1. Replace the summary imports and the BEGIN/END excerpt with `import "invariants.spec";`.
   - Remove the three `import "summaries/..."` lines and everything between the BEGIN/END markers: methods entries, constructor wildcards and CVL functions, ghost/hooks, and both invariants.
   - Keep only this component's own methods entries: `allowance(address,address)` envfree and `DaiMock.balanceOf(address)` envfree. Do not redeclare any entry or alias that invariants.spec already has.
   - Keep the `requireInvariant` uses as they are; they now refer to the invariants proven in job 1080ee77.
   - Update the header comment and the commentary: drop the workaround section and the "verbatim excerpt" claims, and cite job 1080ee77.
   - Re-run in full, unfiltered, with `rule_sanity: basic`. invariants.spec's extra DAI/pie Sload hooks now apply to every rule, so the result must be re-confirmed.
2. Strengthen assertion (b) of `allowanceChangeRequiresAuthorization` so that a spender-side change counts only as spending:
   - Replace the disjunct `(caller == spender && allowAfter < allowBefore)` with `(caller == spender && allowAfter < allowBefore && (f.selector == sig:transferFrom(address,address,uint256).selector || f.selector == sig:withdraw(uint256,address,address).selector || f.selector == sig:redeem(uint256,address,address).selector))`.
   - Optional, recommended: in the same assertion, also restrict the `caller == owner` disjunct to approve/increaseAllowance/decreaseAllowance. The code satisfies this as well, and it would catch a method that zeroes the caller's own allowances as a side effect. It is not required, because the property text permits any change to (caller, *).
