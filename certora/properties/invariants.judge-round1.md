VERDICT: ACCEPT

Judge round 1: certora/specs/invariants.spec (+ scene.spec, summaries/*), conf certora/confs/invariants.conf, run b91ff71e (logs/invariants_run2.log).

## 1. Code smells
No issue. There are no type-bound requires, no requires that only exist to stop a non-`@withrevert` call from reverting, and no tautological asserts. Each methods-block entry has a purpose: `totalSupply`, `balanceOf` and `Pot.pie` are `envfree` because the invariant expressions call them without an env. The remaining entries are summaries. The `invariant_not_trivial_postcondition` sanity sub-checks are "Violated" for every sub-rule, which means none of the three invariant expressions is a tautology.

## 2. Guideline compliance
No issue.
- G18: no preserved block requires its own invariant.
- G20: `sumOfBalances` is not `persistent`.
- G23: the ghost+hook mirror is justified, because CVL can sum only ghost mappings, not storage. The expr.html "Ghost Mapping Sums" note says so.
- G8: `Pot.pie` in the methods block uses the contract type name, not the `pot` alias.
- G21: `RAY` is a `definition`.
- G6: the wildcard NONDET entries have no return type and no `expect`. That is correct, because `expect` is required only for expression summaries.

## 3. Precondition validity
No issue. The only preconditions are mutual `requireInvariant`s between `totalSupplyIsSumOfBalances` and `sharesBackedByPie`. invariants.html ("i requires j, j requires i") shows that this is sound simultaneous induction when both invariants are verified, and both are.

Both are also load-bearing:
- `_mint`'s unchecked additions do not wrap because the checked `pie + shares` in `Pot.join` and `pie >= totalSupply >= balance` bound them.
- `_burn`'s unchecked `totalSupply - shares` does not underflow because `shares <= balance <= sum == totalSupply`.

`zeroAndSelfHoldNoShares` needs no preconditions: `transfer`, `transferFrom` and `_mint` all reject `to/receiver ∈ {0, this}`.

## 4. Overconstrained inputs
No issue. I scrutinised each item below.
- **Sload hook `require sumOfBalances >= bal`.** This is the one bare require. It holds in every reachable state for three reasons:
  - `init_state axiom sumOfBalances == 0` matches the all-zero storage of the base case (invariants.html: "newly created state, where all storage variables are 0").
  - The Sstore hook tracks every write to `balanceOf`. All writes are plain Solidity; there is no assembly access to that mapping.
  - Outside the constructor, no unresolved call could havoc the ghost. The only remaining one, the ERC-1271 staticcall, is NONDET.

  So the ghost is the exact sum of uint256 values, and the require is a mathematical consequence, not a "realistic deployment" assumption. It cannot mask a violation in the post-state either:
  - In `zeroAndSelfHoldNoShares` the ghost is otherwise unconstrained.
  - The `totalSupplyIsSumOfBalances` post-state reads no balance.

  The docs-sanctioned alternative is a ghost mirror mapping plus `usum`, which builds in "larger than any value" (expr.html). It would still need a bare mirror-equality require in an Sload hook, so it is not strictly better. Not required.
- **`rpowG` replacing both `_rpow`s.** This is an uninterpreted, deterministic function with no axioms. Every concrete execution in which `_rpow` does not revert corresponds to some interpretation of `rpowG`. Real reverts only remove paths, and the summary keeps them, so this is a sound over-approximation for safety invariants.

  Sharing one ghost between `SavingsDai._rpow` (base RAY) and `Pot._rpow(x, n, base)` matches the identical code, since SavingsDai passes `RAY()` explicitly. The log warning "SavingsDai._rpow summarization unused" is expected: only view functions call it, and invariants skip view functions.
- **NONDET on `_.hope`, `_.approve`, `_.vat`, `_.dai` (wildcard, so the policy defaults to UNRESOLVED per methods.html).** These apply only to unresolved calls. Resolved and linked calls run the real code ("only summarized if the resolution type is ALL"). The only unresolved calls of these signatures are in the SavingsDai constructor, where `daiJoin`, `vat` and `dai` come from arguments.

  NONDET assumes the callee has no side effects. None of the three invariants depends on state that an arbitrary callee could change during construction:
  - `balanceOf` and `totalSupply` belong to SavingsDai, which has no code yet and cannot be re-entered to write them.
  - `Pot.pie[sDAI]` can be written only with `msg.sender == sDAI`, which is impossible from foreign code.

  The base cases are not vacuous: `Induction base ... rule_not_vacuous` is reported as Violated for all three, which means the sanity check passed. So the NONDET returns did not make the constructor always revert.

  Caveat for other batches (not this one): NONDET drops the constructor's real `vat.hope` and `dai.approve` effects on Vat and DaiMock state. Any future invariant that reads `Vat.can` or `DaiMock.allowance` must not rely on this scene summary for its base case.
- **NONDET on `_.isValidSignature`.** This is a staticcall, so it has no side effects. Sound.
- **Conf.**
  - `parametric_contracts: [SavingsDai]` is justified. No method of Pot, Vat, DaiMock or DaiJoinMock can change `pie[sDAI]`, `balanceOf` or `totalSupply` when called externally by anyone other than sDAI. Including Pot would only add spurious `msg.sender == sDAI` calls to `Pot.exit`.
  - `optimistic_loop` affects only memory-copy loops in `permit`. `permit` writes only `allowance` and `nonces`, which no invariant here reads. The `_rpow` loops are summarized.

## 5. Trivializing summaries
No issue. No balance-moving function is summarized:
- `transferFrom`, `join`, `exit`, `move`, `suck`, `burn` and `mint` all run the real linked code.
- `drip` runs the real code except for the uninterpreted `rpowG`, which over-approximates.
- The NONDET entries cover only constructor-time configuration calls and a view call.

## 6. Manifest errors
No issue. All three properties hold for the real contract and are stated in the correct direction. `pie >= totalSupply` is weaker than the true equality, but it matches the property description.

## 7. Meaningful contract interaction
No issue. Each invariant compares contract state directly: `totalSupply()`, `balanceOf(...)` and `pot.pie(currentContract)`. The ghost is driven by contract storage writes. All 14 non-view SavingsDai methods are checked per invariant, plus the constructor.

## 8. Property coverage
No issue. All three properties in invariants.properties.json are formalized and mapped in invariants.property_rules.json:
- total_supply_equals_sum_of_balances → `totalSupplyIsSumOfBalances`
- shares_backed_by_pot_pie → `sharesBackedByPie`
- zero_and_self_hold_no_shares → `zeroAndSelfHoldNoShares`

There are no skips and no expected failures.

## Required changes
None.

Optional, not blocking:
- Record the justification for the `parametric_contracts` restriction and for `optimistic_loop` in invariants.commentary.md.
- Narrow scene.spec's soundness note so that it explicitly covers only SavingsDai, Pot.pie and ghost state.
