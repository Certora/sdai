VERDICT: ACCEPT

Judge: erc20-token, round 2. Spec: certora/specs/erc20-token.spec. Conf: certora/confs/erc20-token.conf (unfiltered, `parametric_contracts: [SavingsDai]`, `rule_sanity: basic`). Run: https://prover.certora.com/orgs/certora/jobs/6aa78c3d-b8e4-468c-8fbc-7efdf0ec5bbd/report. The log (certora/logs/erc20-token_run2.log) shows every rule and every parametric instance Verified, "No errors found by Prover!", and exit code 0. The only `Violated` lines are the `rule_not_vacuous` sanity sub-checks, which is the expected non-vacuity outcome. `thirdPartyBalancesUnaffected` has all 40 method instances Verified, including approve, increaseAllowance, decreaseAllowance and both permit overloads.

## Round-1 required change
Done correctly. `isAddressArg` now returns:
- transfer, deposit, mint: `u == a1` (to / receiver).
- transferFrom, withdraw, redeem: `u == a1 || u == a2` (from, to / receiver, owner).
- both permit overloads: `u == a1` (owner only; the spender a2 is no longer exempt).
- approve, increaseAllowance, decreaseAllowance and views: `false`.

This matches the property text "(from/to/receiver/owner)" exactly. A permit or approve that moved shares to the spender would now fail the rule, and the rule still verifies, so SavingsDai does not do that. The status JSON and commentary were updated with the new run link, and the commentary describes the change.

## 1. Code smells
No issue. Unchanged from round 1. The redundant "as stated" asserts in `allowanceChangesOnlyByAuthorizedActions` are harmless, and none of the asserts are tautologies.

## 2. Guideline compliance
No issue. `isAddressArg` is a CVL function with `return` on every path and no `method` variables declared in branches. The round-1 cosmetic note about unnecessary `to_mathint` calls still applies and does not block acceptance.

## 3. Precondition validity
No issue. All parametric rules still `requireInvariant` the three proven invariants. The revert rules use only `requireInvariant totalSupplyIsSumOfBalances`. No new preconditions were added.

## 4. Overconstrained inputs
No issue. The only bare require is still `requireTwoBalancesBounded`, which was accepted in round 1 with justification. It is used only in the two non-revert success rules. The change added no requires.

## 5. Trivializing summaries
No issue. Scene summaries are unchanged (`rpowG`, NONDET `isValidSignature`, constructor-only NONDETs). The run reports the constructor-only NONDETs as unused.

## 6. Manifest errors
No issue. The new exemption set matches the Solidity semantics: permit and the approve family write only `allowance`/`nonces`, never `balanceOf`.

## 7. Meaningful contract interaction
No issue. `thirdPartyBalancesUnaffected` compares `balanceOf(u)` after `callWithArgs` against the value read before the call.

## 8. Property coverage
No issue. The round-1 gap is closed: the exempt set is now exactly caller ∪ {from, to, receiver, owner}. For permit, the owner exemption follows the property's wording ("owner" is a listed role). The other rules are unchanged:
- `allowanceChangesOnlyByAuthorizedActions`, `balanceDecreaseRequiresOwnerOrAllowance` and `totalSupplyChangesOnlyViaVaultOperations` still cover every method with no filters.
- The approve-family exact rules still assert that every balance is unchanged.

Everything else round 1 confirmed is still covered, with no regressions.

## Required changes
None.
