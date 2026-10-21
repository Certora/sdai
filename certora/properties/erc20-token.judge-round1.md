VERDICT: REJECT

Judge: erc20-token, round 1. Spec: certora/specs/erc20-token.spec. Run: https://prover.certora.com/orgs/certora/jobs/5db01803-599c-442d-9b4c-c467df554acf/report (12/12 VERIFIED, rule_sanity basic: every `rule_not_vacuous` sub-check is "Violated", which means the rule is not vacuous, as intended).

## 1. Code smells
No issue. The asserts are not tautological. In `allowanceChangesOnlyByAuthorizedActions` the "as stated" asserts follow from the "precise" asserts, so they are redundant. They are not decorative, though: each one reads `allowance(owner, spender)` from the contract. There are no type-bound requires and no requires that only prevent reverts. The `allowance` envfree entry is used. `MAX_UINT` is a named definition.

## 2. Guideline compliance
No issue.
- Each revert behaviour is covered by one `lastReverted <=> P` rule. These rules contain no bare `require`, only `requireInvariant`. Non-payability is a disjunct of P rather than an assumption, which is correct.
- The `@withrevert` return values in the approve/increase/decrease rules are only used under `!reverted`, as guideline 16 requires. The prover's syntax warnings about this are harmless.
- All CVL functions end in `return`. There are no `method` variables inside branches. Locals such as `uint16 ref1` declared inside `if` branches of a CVL function are legal.
- Some `to_mathint` calls are unnecessary (guideline 19). That is cosmetic and does not block acceptance.

## 3. Precondition validity
No issue. The parametric rules `requireInvariant` all three proven invariants. The transfer/transferFrom success rules need the two-balance bound, discussed under criterion 4. The revert rules only use `totalSupplyIsSumOfBalances`. They need nothing more because the `+=` in transfer/transferFrom is unchecked and cannot revert. I found no spurious-start-state failure mode. The approve-family rules need no invariant.

## 4. Overconstrained inputs
No issue. `requireTwoBalancesBounded` contains exactly one bare require: `a != b => balanceOf(a) + balanceOf(b) <= totalSupply()`. I accept it for these reasons:
- The proven `totalSupplyIsSumOfBalances` makes `totalSupply == sumOfBalances`.
- `sumOfBalances` is maintained by an Sstore hook on every write to `balanceOf`, and nothing writes `balanceOf` in assembly. `init_state` is 0 and matches the constructor, which writes no balances. So in every reachable state the ghost is the true sum of all balances, which are non-negative uint256 values.
- For distinct a and b, the bound is therefore a plain arithmetic consequence of that sum. It is not an assumption about deployments.
- It does not constrain the case `a == b`, so self-transfers stay fully covered.
- It is only used in the two non-`@withrevert` success rules, never inside a `<=>` revert characterisation.
- It is needed: without it, the unchecked `balanceOf[to] += value` can wrap in an unreachable state, because the Sload hook only bounds individual balances.

## 5. Trivializing summaries
No issue. The erc20-token spec adds no summaries. The scene summaries are accepted:
- `rpowG` is not used on any ERC20 path.
- `isValidSignature` NONDET models a view staticcall. It over-approximates, so it is sound.
- The constructor-only NONDETs are reported as unused in this run.
No summary affects a function that moves balances.

## 6. Manifest errors
No issue. Every rule matches the Solidity semantics of transfer, transferFrom, approve, increaseAllowance, decreaseAllowance, _mint, _burn and permit.

## 7. Meaningful contract interaction
No issue. Every assert compares values read from the contract after the call (`balanceOf`, `allowance`, `totalSupply`, the return value, `lastReverted`) against values computed independently before the call.

## 8. Property coverage
Issue, in `third_party_balances_unaffected`. The property limits the exempt address arguments to "(from/to/receiver/owner)". `isAddressArg`, however, also exempts the **spender**:
- `approve`, `increaseAllowance` and `decreaseAllowance` return `u == a1`, where a1 is the spender.
- Both `permit` overloads return `u == a1 || u == a2`, where a2 is the spender.

So the rule as written allows `permit(owner, spender, ...)` to change the spender's share balance. No other rule in this spec rules that out:
- `totalSupplyChangesOnlyViaVaultOperations` only constrains the supply.
- `balanceDecreaseRequiresOwnerOrAllowance` does not apply when the caller is the owner.
- The approve-family rules each assert that every balance is unchanged, so only permit is actually exposed. The formalization is still weaker than the stated property for all five methods.

A hypothetical `permit` that moved shares from the owner to the spender would pass the whole spec. This must be tightened so the rule matches the description.

Everything else is fully covered:
- "returns true" is asserted for transfer, transferFrom, approve, increaseAllowance and decreaseAllowance.
- The self-transfer no-op is asserted for transfer and transferFrom (`sender == to`, `from == to`).
- The infinite-allowance and self-spend cases leaving the allowance unchanged are asserted.
- The overflow revert of increaseAllowance is in the `<=>`.
- decreaseAllowance reverts iff the value exceeds the allowance.
- "No other allowance or balance changes" is checked by free (o, s, u) parameters.
- The transfer/transferFrom revert iffs match the code exactly.

`callWithArgs` covers every method:
- All 13 mutating SavingsDai methods have their own branch, including both deposit/mint overloads and both permit overloads.
- a1, a2 and x are free rule parameters, so binding them loses no generality.
- referral, deadline and signature are left unconstrained.
- Every other selector, all of them views, gets arbitrary calldata through the `else` branch.
- No method is filtered out.

## Required changes
1. In `isAddressArg`, list only the roles the property names (from/to/receiver/owner):
   - `approve`, `increaseAllowance` and `decreaseAllowance` should exempt no address argument (return `false`), because spender is not a listed role.
   - Both `permit` overloads should exempt only the owner (`u == a1`), not the spender a2.
   - Keep transfer (to = a1), transferFrom (from = a1, to = a2), deposit/mint (receiver = a1) and withdraw/redeem (receiver = a1, owner = a2) as they are.
   - Re-run the full unfiltered conf and update the status/commentary files.
