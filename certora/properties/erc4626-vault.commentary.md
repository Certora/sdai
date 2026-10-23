# erc4626-vault — commentary (round 1)

Round-1 full unfiltered run (iter 2, rule_sanity basic): https://prover.certora.com/orgs/certora/jobs/3b0aeea4-5664-41bf-a0a7-77b25258d6a1/report — every rule VERIFIED (22 rules incl. envfree static check; all `rule_not_vacuous` sanity children pass).
Iter 1: https://prover.certora.com/orgs/certora/jobs/9f4bb394-0475-4262-a35a-fa3edcc4e00c/report — 3 spurious violations (see below).

## Setup
- Spec `certora/specs/erc4626-vault.spec` imports the standard four files; adds `using DaiMock as daiToken`. Conf = invariants.conf with verify/msg changed; no extra prover_args needed (nonlinear rules solved within default timeouts).
- No new summaries. The scene's `rpowG` ghost function (scene.spec) summarizes both `SavingsDai._rpow` and `Pot._rpow`, so view-side chi estimates and `Pot.drip` agree exactly. Rules compute the expected chi independently from the Pot pre-state via `expectedChi(e)` = `now > rho ? rpowG(dsr, now - rho, RAY) * chi / RAY : chi` and assert that the post-state `pot.chi()` (the chi the operation used) equals it.
- Accounting/attack rules `requireInvariant` the three proven invariants (totalSupplyIsSumOfBalances, sharesBackedByPie, zeroAndSelfHoldNoShares) so the unchecked `_mint`/`_burn` arithmetic cannot wrap.
- No `e.msg.sender != currentContract` restriction was needed: every rule is proven for arbitrary callers, receivers and owners, including aliases to scene contracts.

## Formalization decisions
- previews_match_operations: preview call followed by the operation in the same state and env (same timestamp). The Pot is not required to be dripped; timestamps < rho are not excluded (deposit/mint then revert in Pot.join, withdraw/redeem and the previews both use the stored chi).
- conversions_round_in_vault_favor: directly compares previewMint vs convertToAssets and previewWithdraw vs convertToShares in the same env.
- max_functions_consistent: equality rule for maxRedeem/maxWithdraw/maxDeposit/maxMint, plus two strengthening rules: redeem above maxRedeem and withdraw above maxWithdraw (same block) always revert.
- withdraw_redeem_require_authorization: one parametric rule filtered to withdraw/redeem (dispatch through a CVL helper with explicit args); spender != owner; burned shares = owner's balance decrease must be <= prior allowance; finite allowance reduced by exactly burned, infinite allowance untouched.
- invalid_receiver_rejected: parametric over the four deposit/mint overloads (incl. referral variants); receiver 0 or SavingsDai => revert.
- no_profit_from_deposit_redeem_roundtrip: deposit→redeem of all received shares in one env (caller = receiver = owner) returns <= assets and the caller's DAI balance does not increase; mint→withdraw of the paid assets burns >= minted shares.
- share_price_never_decreases: parametric over all SavingsDai methods; asserts `pot.chi()` does not decrease and `convertToAssets(s)` evaluated in the same block does not decrease. (Comparing across different timestamps is not meaningful: rpowG is uninterpreted, and real rpow rounding makes compounding path-dependent.)
- vault_ops_do_not_affect_other_holders: two parametric rules (deposit-side ops with other != receiver; withdraw-side ops with other != owner).

## Trust assumptions (bare requires)
1. `requirePotChiAtLeastRay()` — `pot.chi() >= RAY`, used only in withdrawAccounting and mintWithdrawRoundtripNoProfit. Iter-1 CEXs started from chi == 0 (CVL ceil-division by zero in the expectation; mint hands out shares for 0 assets). Unreachable: Pot's constructor sets chi = RAY and the justification rule `potChiNeverDecreases` (VERIFIED) shows no Pot entry point (drip, join, exit, both file overloads, cage, rely, deny) lowers chi. Cannot be an invariant here because parametric_contracts = [SavingsDai] and the base case does not run Pot's constructor.
2. `requireDaiSupplyIsSum()` (round 2, replaces the bare `requireDaiBalanceBounded`) — `daiToken.totalSupply() == sumDaiBalances`, used in withdrawAccounting/redeemAccounting. `sumDaiBalances` is a ghost maintained by Sstore/Sload hooks on `daiToken.balanceOf` (separate from invariants.spec's `sumOfBalances`); the Sload hook (`sum >= bal`) then bounds every read balance by totalSupply, which rules out the iter-1 CEX (receiver DAI balance > totalSupply, unchecked DaiMock.mint wrap). Justification: base case — DaiMock's constructor writes no balance, totalSupply = 0, ghost init 0; step — justification rule `daiSupplyIsSumPreserved` calls every state-changing DaiMock entry point directly (transfer, transferFrom, approve, increase/decreaseAllowance, mint, burn, rely, deny, both permits) and asserts preservation. Only DaiMock writes its storage, so this covers calls via DaiJoinMock/SavingsDai. That rule carries one extra require: for distinct accounts p != q, balanceOf(p) + balanceOf(q) <= sum (the pairs (msg.sender, a) and (a, b) touched by transfer/transferFrom) — a direct consequence of the ghost being a sum of non-negative terms, needed because the Sload hook only bounds single balances while transfer adds unchecked.
- Plus the scene's standing assumptions: rpowG never reverts; Pot/Vat are verification models.

## Expected failures / skipped
None.

## Round 2
- Iter 3 (full, unfiltered): https://prover.certora.com/orgs/certora/jobs/b4c84dec-6030-4573-b299-c9a1eadae623/report — the local client lost its connection (HTTP 401 'Server is currently unavailable') before the job finished. Streamed log up to then: daiSupplyIsSumPreserved VERIFIED, all depositOps/withdrawOpsDoNotAffectOthers instances VERIFIED, every `rule_not_vacuous` sanity check reported so far non-vacuous, no assertion violations. Final per-rule statuses must be read from the report.

## Requests
- Structural invariant for the scene: `Pot.chi() >= RAY` (would replace bare require #1; needs a setup where Pot's constructor/state is in scope, e.g. a Pot-verifying conf).

## Pass 2 (scene: DaiMock -> Dai, DaiJoinMock -> DaiJoin)
Final full unfiltered run (pass2 iter 1, rule_sanity basic): https://prover.certora.com/orgs/certora/jobs/653c426b-33ce-490f-a6db-fff70055c773/report. All 23 rules VERIFIED, and all 225 tree nodes, including every `rule_not_vacuous` child, are VERIFIED. The local client disconnected (HTTP 401) before the final summary, so the statuses were read from `treeViewStatus_18.json` in the job's output archive.

Changes:
- `using DaiMock as daiToken` became `using Dai as daiToken`. The methods entries `DaiMock.balanceOf`/`totalSupply` became `Dai.*`. The ghost hooks still go through the `daiToken` alias, which now points at `Dai.balanceOf`. The spec never named DaiJoin, so nothing changed there.
- `daiSupplyIsSumPreserved` now calls every state-changing entry point of the real Dai: transfer, transferFrom, mint, burn, approve, push, pull, move, rely, deny, and the DAI-style `permit(holder, spender, nonce, expiry, allowed, v, r, s)`. DaiMock's increase/decreaseAllowance and its two EIP-2612 permits no longer exist and were dropped.
- **Removed the pairwise require** (`bal(p) + bal(q) <= sum` for distinct p and q) from `daiSupplyIsSumPreserved`. It was needed only because DaiMock's transfer added without a check. Dai's `add` is checked, so an overflowing credit reverts and the rule verifies with only the induction hypothesis.
- **Removed `requireDaiSupplyIsSum()` from withdrawAccounting and redeemAccounting.** In pass 1 it ruled out a spurious success where DaiMock.mint's unchecked `balanceOf[usr] + wad` wrapped. Dai.mint uses the checked `add` for both the balance and totalSupply, so a would-be wrap now reverts. These success-only rules make no claim about reverting paths, so they hold without the assumption, and both VERIFIED without it.
- `requireDaiSupplyIsSum()` now appears only as the induction hypothesis inside `daiSupplyIsSumPreserved`. That rule is kept as a proven fact about the DAI model, but no vault rule depends on it anymore.
- DaiJoin's `live` flag and `exit` (which requires live == 1) only add revert paths to withdraw and redeem. No rule needed a change. `withdrawAboveMaxReverts` and `redeemAboveMaxReverts` are one-directional (above max => revert), so extra reverts cannot break them.

Remaining bare requires:
1. `requirePotChiAtLeastRay()` in withdrawAccounting and mintWithdrawRoundtripNoProfit. It is unchanged from pass 1 and justified by `potChiNeverDecreases` plus Pot's constructor.
2. `spender != owner` and `other != receiver/owner`. These are part of the property statements, unchanged.
3. `requireDaiSupplyIsSum()` as the induction hypothesis of `daiSupplyIsSumPreserved` only.

## Pass 3 (4 new properties)
Final full unfiltered run (pass3 iter 1, rule_sanity basic, msg "erc4626-vault pass3 iter 1"): https://prover.certora.com/orgs/certora/jobs/4552c067-8583-4523-9479-f35e73b6bf30/report. There are 41 rules: the 23 from pass 2 and 18 new ones. 40 are VERIFIED. `exitRejectsZeroReceiver` is VIOLATED, which is the expected finding (below). Statuses were read from `treeViewStatus_26.json` in the job archive: every one of the 281 tree nodes, including every `rule_not_vacuous` child, is VERIFIED except that rule's withdraw and redeem instances. (The streamed log prints "Violated: ...-rule_not_vacuous" lines; that is the sanity sub-check's internal assert-false being violated, i.e. the rule is non-vacuous.) The pass-1/2 rules and helpers are unchanged, and the conf changed only in `msg`. No prover_args were added, and no rule needed splitting beyond the per-function design below. The slowest new rules (monotonic ops, split rules) finished within the ~4-minute job.

### referral_overloads_equivalent
Rules: `depositReferralEquivalent`, `mintReferralEquivalent`.
- Each rule takes `storage init = lastStorage`, calls the referral overload with `@withrevert`, and records `lastReverted`, the return value, `lastStorage`, the receiver's shares, totalSupply, `pot.pie(sDAI)` and the caller's DAI. It then calls the plain overload `at init` with the same env and arguments.
- Asserts:
  - `revertedRef <=> revertedPlain`;
  - on success, equal return values and equal explicit balances;
  - `afterRef == afterPlain`: whole-`storage` equality (docs cvl/expr.html "Comparing storage"), covering every contract's storage, native balances and all ghosts.
- Storage equality is meaningful here because every call in deposit/mint is resolved to linked code. The scene's wildcard NONDETs apply only to UNRESOLVED calls, which occur only in the constructor, so nothing is havoced. The explicit balance asserts are redundant with it and are kept for CEX readability.
- No requires. Return values are compared only under `!reverted` (guideline 16).

### conversions_and_previews_monotonic
Rules: `convertToSharesMonotonic`, `convertToAssetsMonotonic`, `previewDepositMonotonic`, `previewMintMonotonic`, `previewWithdrawMonotonic`, `previewRedeemMonotonic`, `depositMonotonic`, `mintMonotonic`, `withdrawMonotonic`, `redeemMonotonic`.
- The six view rules call f(x) and f(y) in the same state and env and assert `x <= y => f(x) <= f(y)`. The four operation rules call op(x) and op(y) `at init` from one snapshot with the same env and receiver/owner.
- The order is the conclusion's hypothesis (an implication), not a `require`, so no input is dropped.
- They were split per function up front so that each nonlinear query is separate. None timed out.

### no_gain_from_splitting_operations (attack_vector)
Rules: `depositSplitNoGain`, `mintSplitNoGain`, `withdrawSplitNoGain`, `redeemSplitNoGain`.
- Path 1 runs op(a) then op(b) with the same env, receiver and owner. Path 2 runs op(ab) `at init`.
- Each rule asserts on the return values:
  - deposit: shares sum <=;
  - mint: assets sum >=;
  - withdraw: shares sum >=;
  - redeem: assets sum <=.
- Each rule also asserts the corresponding end state:
  - deposit: the receiver's shares after the split are <= after the single op;
  - mint: the caller's DAI after the split is <= after the single op;
  - withdraw: the owner's shares after the split are <= after the single op;
  - redeem: the receiver's DAI after the split is <= after the single op.
- The second op of path 1 runs after the first one dripped (rho == now). It therefore uses the same chi as path 2's single drip, since rpowG is deterministic.
- `requireStructuralInvariants()` is used because shares are minted and burnt.
- **New bare require:** `require to_mathint(ab) == a + b`, one per split rule. It only names the combined amount as a uint256 argument and drops no execution in which both split ops succeed:
  - deposit and withdraw evaluate the checked `amount * RAY`, so each amount is < 2^256/10^27 and the sum fits;
  - mint's two `Pot.join` calls add a and then b to `Pot.Pie` with checked addition;
  - redeem burns a and then b from the owner's balance, so a + b <= the prior balance.
- Like every success-only rule, these say nothing when the combined op reverts while the split ops succeed.

### exit_rejects_invalid_receiver — FINDING (expected to fail)
Rule: `exitRejectsZeroReceiver`. It is parametric over withdraw/redeem, uses `requireStructuralInvariants()` (no other require), calls `@withrevert` with receiver = address(0), and has `assert reverted`. VERIFIED would mean the good property holds. It is **VIOLATED** for both withdraw and redeem.
- **Scenario:** `SavingsDai._burn` never checks `receiver`. It burns the owner's shares, calls `pot.exit(shares)`, then `daiJoin.exit(receiver, assets)`, and `DaiJoin.exit` calls `Dai.mint(address(0), assets)`. Mainnet DAI's mint has no receiver check, so the call succeeds. The DAI is credited to `balanceOf[address(0)]`, which nobody controls, so it is effectively burned.
- **Prover CEXs:** the solver picked the degenerate calls withdraw(0, address(0), owner) and redeem(0, address(0), owner).
- **Witness for the positive case (illustration only):** a companion `satisfy` rule, `exitToZeroReceiverWitness`, is VERIFIED, meaning the scenario is reachable. Nothing on the zero-receiver path depends on chi, so the path is reachable for any chi. The witness state satisfies the structural invariants and chi >= RAY, but its chi is ~5.9e76, so it is not a realistic state. In its witness, caller 0x2380, holding an allowance from owner 0x8200, calls withdraw(12, address(0), 0x8200). The call burns 1 share (owner 9 -> 8, totalSupply 10 -> 9), and `Dai.balanceOf(0)` goes 7 -> 19.
- **Impact:** a user-error footgun. A front-end or integrator passing a zero receiver irrecoverably loses the withdrawn DAI.
  - It is asymmetric with deposit/mint, which reject receiver 0 and SavingsDai itself (`invalidReceiverRejected`).
  - ERC-4626 does not require the check, so the severity is low (robustness/UX).
  - Only the owner or an approved spender can trigger it, and the loss falls on that owner, so it is not a theft vector.
- **Second sink, out of scope:** withdrawing to the SavingsDai contract itself (receiver == sDAI) is also unchecked. DAI minted to sDAI is unrecoverable, because no sDAI function moves out DAI it holds beyond the amount pulled in by `_mint`. This property is scoped to address(0), so the case is only noted here.
- Recorded in `_expected_fail` with reason "finding". The rule is kept unweakened.

### New bare requires (pass 3)
- `require to_mathint(ab) == a + b` in the four split rules, justified above.
- No others. The new rules reuse only `requireStructuralInvariants()` (requireInvariant only) and, in the witness rule only, `requirePotChiAtLeastRay()`, the accepted pass-1 trust assumption backed by `potChiNeverDecreases`. In a satisfy rule, that assumption only restricts the witness to realistic states.

## Pass 3: assumptions now backed by proofs (maker-models)
- requirePotChiAtLeastRay: proven invariant potChiAtLeastRay over all Pot methods from Pot's constructor (run 9e14d9f8); potChiNeverDecreases is its induction step.
- daiSupplyIsSumPreserved base case: proven invariant daiSupplyIsSum from Dai's constructor (run 0e288f36).
Spec comments still describe the pass-2 reasoning; the proofs above supersede it.

### Pass 3 round 2 (judge pass3 round 1: storage-comparison form)
Final full unfiltered run (pass3 iter 2, msg "erc4626-vault pass3 iter 2"): https://prover.certora.com/orgs/certora/jobs/7da047cb-8def-4946-a501-01b673be33ec/report. This run supersedes the iter 1 link above. 40 of the 41 rules are VERIFIED. `exitRejectsZeroReceiver` is VIOLATED, the expected finding. All 281 tree nodes, including every `rule_not_vacuous` child, are VERIFIED except that rule's two method instances (read from `treeViewStatus_24.json`).
- **Referral rules:** in `depositReferralEquivalent` and `mintReferralEquivalent`, the whole-state comparison is now the unconditional, top-level `assert afterRef == afterPlain;`. This is the `assert s1 == s2` form that docs cvl/expr.html "Comparing storage" names as the supported one; nesting a comparison inside an implication is called experimental there. The unconditional form is at least as strong as the old one:
  - if both calls revert, both snapshots are the rolled-back `init` (no persistent ghosts);
  - if exactly one reverts, the preceding `revertedRef <=> revertedPlain` assert fails.
- **Rest of the spec:** unchanged.
- **Documentation:** the `_expected_fail` detail no longer calls the witness state realistic. The zero-receiver path is reachable for any chi, and the witness is an illustration only. The second sink (receiver == SavingsDai) is now noted as out of scope.
