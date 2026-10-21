# erc20-token: commentary

Final run (iter 2, full, unfiltered, rule_sanity basic): https://prover.certora.com/orgs/certora/jobs/6aa78c3d-b8e4-468c-8fbc-7efdf0ec5bbd/report. All 12 rules VERIFIED, including all 40 method instances of each parametric rule and every rule_not_vacuous sanity check. Iter 1 (round 1): https://prover.certora.com/orgs/certora/jobs/5db01803-599c-442d-9b4c-c467df554acf/report.

## Decisions
- **Non-payable functions.** Every SavingsDai function is non-payable. In the revert-characterization rules `e.msg.value != 0` is a disjunct of the iff predicate rather than a `require`. The `<=>` claim is therefore unrestricted and these rules use no bare require. The same applies to the approve/increaseAllowance/decreaseAllowance rules (approve: `lastReverted <=> msg.value != 0`).
- **"Other" accounts/allowances** (third-party balance, unrelated allowance entries) are free rule parameters guarded by an implication inside the assert, not by `require`.
- **One bare require**, in `requireTwoBalancesBounded(a, b)` (used only by the two success rules for transfer/transferFrom): `a != b => balanceOf(a) + balanceOf(b) <= totalSupply`. This follows arithmetically from the proven `totalSupplyIsSumOfBalances` (the sum covers all addresses and every term is non-negative). It has to be stated explicitly because the invariant's Sload hook bounds only a single balance by the ghost sum. Without it the prover could choose two balances that each fit under the sum but together exceed it, which would make the unchecked `balanceOf[to] += value` wrap around. That state is unreachable.
- **Parametric rules** range over all SavingsDai methods (`parametric_contracts: ["SavingsDai"]`) with no filters. The rules about allowances and third-party balances need to refer to "the address arguments of the call", so they use the CVL helper `callWithArgs(e, f, a1, a2, x)`. It dispatches on `f.selector` and calls each mutating method with explicit arguments: transfer(to=a1), transferFrom(from=a1,to=a2), approve/increase/decrease(spender=a1), deposit/mint(+referral overloads)(receiver=a1), withdraw/redeem(receiver=a1, owner=a2), both permit overloads(owner=a1, spender=a2). The remaining arguments (referral, deadline, signature/v,r,s) are unconstrained, and views get arbitrary calldata. No behaviour is lost.
- **allowanceChangesOnlyByAuthorizedActions** asserts the property as stated and also a sharper version that ties the changed entry to the call arguments:
  - Increase: only approve/increaseAllowance with sender==owner and spender==a1, or permit(owner=a1, spender=a2).
  - Decrease: approve/decreaseAllowance by the owner; transferFrom by the spender with from==owner; withdraw/redeem by the spender with owner==a2; or permit.
- **thirdPartyBalancesUnaffected**: a changed balance must belong to the caller or to one of the method's from/to/receiver/owner arguments (`isAddressArg`). The exempt arguments are: transfer to; transferFrom from and to; deposit/mint receiver; withdraw/redeem receiver and owner; permit owner only. Spenders are not exempt: approve-family calls exempt no argument, and the permit spender is not exempt, so a permit or approve that moved shares to the spender would fail the rule. Round 2 changed this in response to judge round 1 (criterion 8); round 1 had also exempted the approve-family spender and the permit spender.
- **balanceDecreaseRequiresOwnerOrAllowance** and **totalSupplyChangesOnlyViaVaultOperations** use a generic `f(e, args)`.
- The parametric rules `requireInvariant` all three proven invariants so that they start from reachable states. The revert rules `requireInvariant totalSupplyIsSumOfBalances`.

## Summaries / trust assumptions
No summaries beyond those in the shared scene (scene.spec: `rpowG` ghost for `_rpow`, NONDET `isValidSignature`, constructor-only NONDETs). Pot/Vat are harness models. `optimistic_loop` applies to the memory-copy loops in permit.

## Expected failures / skipped
None.
