VERDICT: REJECT

Judge round 1, erc4626-vault. Reviewed: certora/specs/erc4626-vault.spec, its conf, scene.spec, invariants.spec, SavingsDai.sol, Pot.sol, Vat.sol, DaiJoinMock.sol, DaiMock.sol, the properties/property_rules/commentary files, and logs run1/run2. Run 2 is the full unfiltered run with rule_sanity basic, and it ends with "No errors found by Prover!".

## 1. Code smells
No issue. Every methods-block entry (allowance, maxRedeem, maxDeposit, maxMint, Pot.chi/rho/dsr, DaiMock.balanceOf/totalSupply) is used in an envfree call. I found no pointless type-bound requires and no requires that only suppress reverts.

None of the asserts is tautological. In the accounting rules, the return value, `balanceOf`, `totalSupply`, `pot.pie` and the DAI balances are all read from the contract and compared with an expectation built from the pre-state.

`expectedChi` does not make `chi == chiExpected` trivially true. It is built from the Pot pre-state (rho, chi, dsr) and the shared `rpowG` ghost. The post-state `pot.chi()` matches it only if three things hold:
- the operation takes the drip branch exactly when `now > rho`;
- drip computes `rpow * chi / RAY` in that order;
- chi is left untouched otherwise.

Because `rpowG` is uninterpreted, the rule checks how drip uses rpow, not the value of rpow. That is the right scope here.

`maxDeposit == max_uint256` and `maxMint == max_uint256` compare implementation outputs with constants, which the property asks for.

## 2. Guideline compliance
No issue. The arithmetic is mathint, and the one narrowing (`assert_uint256(e.block.timestamp - rho)` under `timestamp > rho`) is safe. `method` variables are declared as rule parameters and passed to CVL helpers. Every void CVL function ends with `return`. No `@withrevert` return value is used.

The single-case revert rules (invalidReceiverRejected, redeemAboveMaxReverts, withdrawAboveMaxReverts) are one-directional implications that the properties themselves state, and none of them contains a bare require. That is acceptable.

## 3. Precondition validity
No issue. The three proven structural invariants are required via `requireInvariant` wherever `_mint` or `_burn` runs unchecked arithmetic: the accounting rules, the preview-vs-operation rules, the roundtrip rules, the parametric share-price rule and the other-holders rules.

The rules that skip them (rounding, max functions, invalid receiver, the above-max reverts) only use views, or claim reverts, so a spurious pre-state cannot make them fail. Pot `rho`, `dsr` and `chi` are otherwise unconstrained, so stale Pots, un-dripped Pots and `dsr < RAY` are all explored.

## 4. Overconstrained inputs
This criterion has one finding: the DAI balance bound.

**`requirePotChiAtLeastRay()` (withdrawAccounting, mintWithdrawRoundtripNoProfit): accepted.**
- The evidence is verifiable and mostly in the spec. Pot's constructor sets `chi = RAY`. The VERIFIED rule `potChiNeverDecreases` covers every state-changing Pot entry point (drip, join, exit, both `file` overloads, cage, rely, deny). Only Pot writes Pot storage, so these two facts give `chi >= RAY` in every reachable state by induction.
- The require constrains only `chi`, not `dsr`. `dsr < RAY` stays explored: with a stale Pot, drip's checked `tmp - chi` reverts, and success-only accounting rules correctly make no claim about that case.
- `0 < chi < RAY` is unreachable for the same reason.
- Note (no change required): `chi > 0` would be enough for both rules. For mint→withdraw, `ceil(ceil(s*c/R)*R/c) >= s` holds for any `c > 0`. The stronger `>= RAY` is still justified, so this is not an overconstraint.

**`requireDaiBalanceBounded(receiver)` (withdrawAccounting, redeemAccounting): not accepted as written.**
- The justification is an informal appeal to "the DAI token's own ERC20 sum invariant", and nothing in this spec or any other spec proves it.
- DaiMock is part of the scene. Hooks on another contract's storage can be written through a `using` alias (hooks.txt, "Access paths": "Contract fields may be qualified by the contract that defines them ... an instance variable introduced by a using statement"). So the assumption can be justified here exactly the way the chi assumption was.
- The checklist does not let a "can't happen in deployment" claim stand without verifiable evidence. The carve-out for out-of-scope components requires a validating rule for that component, and none exists.
- Accepting the chi justification rule while leaving this one bare is inconsistent.

## 5. Trivializing summaries
No issue. The spec adds no summaries.

The scene's `rpowG` ghost is shared by SavingsDai's view-side estimate and `Pot.drip`, which matches the real code (same algorithm, base = RAY). The `isValidSignature` NONDET applies to a staticcall. The wildcard NONDETs apply to unresolved calls only, and the log warns that all of them are unused in this run.

All balance-moving calls (DaiMock transferFrom/burn/mint, DaiJoinMock join/exit, Vat move/suck, Pot join/exit/drip) run their real linked code.

## 6. Manifest errors
No issue. The rules are consistent with correct ERC-4626 and DSR behaviour.

The same-block restriction in `sharePriceNeverDecreases` is a valid formalization of "no SavingsDai operation lowers chi or share value". The property is about the effect of a user action, so value must be compared at the same timestamp. Comparing across timestamps would mix in interest accrual, which the action does not cause, and `rpowG` is uninterpreted anyway. The rule is parametric over every SavingsDai method and asserts both stored-chi monotonicity and `convertToAssets(s)` monotonicity.

The same-block restriction in the roundtrip rules is also correct: across blocks, accrued interest is a legitimate gain.

## 7. Meaningful contract interaction
No issue. Every assert depends on a value the contract returns, or on a post-state read from SavingsDai, Pot or DaiMock storage.

`withdrawRedeemRequireAllowance` computes the burned amount from `balanceOf(owner)` before and after the call, and compares the post-state `allowance` with it.

## 8. Property coverage
All 12 properties are formalized. Points checked against the brief:

- **Accounting rules.**
  - Deposit checks pie change, caller DAI debit, receiver credit, totalSupply and the return value against the dripped chi.
  - Mint checks the same, plus pie, which goes beyond its property.
  - Withdraw and redeem check the owner debit, totalSupply, pie, receiver DAI credit and the return value.
- **`previews_match_operations`.** Neither `rho` nor the timestamp is constrained, so un-dripped Pots are covered. Timestamps below `rho` are covered too: deposit and mint then revert in `Pot.join`, and withdraw, redeem and the previews all use the stored chi.
- **`vault_ops_do_not_affect_other_holders`.** The deposit-side rule covers all four overloads: `deposit(uint256,address)`, `deposit(uint256,address,uint16)`, `mint(uint256,address)` and `mint(uint256,address,uint16)`. The withdraw-side rule covers withdraw and redeem.
- **Aliasing.** No rule excludes receiver, owner or caller being equal to a scene contract or to each other. The only address requires are `spender != owner` and `other != receiver/owner`, and both are part of the property statements.

Minor, no change required: `depositAccounting` and `mintAccounting` exercise only the 2-argument overloads. The referral overloads delegate to them internally, and the property text names only the 2-argument form.

## Required changes
1. Replace the bare trust assumption `requireDaiBalanceBounded(receiver)` with a justified one, the same way `requirePotChiAtLeastRay` is justified. Steps:
   - Add a justification rule, or a pair of rules, that tracks the sum of DaiMock balances with a ghost `sumDaiBalances` plus `Sstore`/`Sload` hooks on `DaiMock.balanceOf` (qualified by the `daiToken` alias, or by `DaiMock`).
   - Prove that every state-changing DaiMock entry point preserves `daiToken.totalSupply() == sumDaiBalances` when called directly with an arbitrary env. The entry points are transfer, transferFrom, approve, increaseAllowance, decreaseAllowance, mint, burn, rely, deny and both permit overloads.
   - Base case: DaiMock's constructor sets all of these to zero. Only DaiMock writes DaiMock storage, so preservation on these entry points also covers calls made through DaiJoinMock and SavingsDai.
   - Then either derive the per-account bound from the sum (an Sload hook `require sumDaiBalances >= bal`, as invariants.spec does for sDAI), or keep the helper and cite the new rule as its justification.
   - Register the rule under `_justification_rules` in erc4626-vault.property_rules.json and update the commentary.
   - If the prover cannot handle this, report the concrete failure and CEX instead of leaving the assumption unjustified.
