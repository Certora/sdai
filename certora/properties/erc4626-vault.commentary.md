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

## Pass 4 (2 new properties)

### Runs
- **Authoritative, pass-4 barrier** (current scene.spec with the deterministic `isValidSigG` ERC-1271 model): https://prover.certora.com/orgs/certora/jobs/ec591a60-33da-4080-a457-b98759d0e908/report. Full unfiltered, rule_sanity basic; 45 rules, 288/293 nodes VERIFIED, the other 5 are `exitRejectsZeroReceiver` (F-2). The iter-1 run below used the pass-3 scene.
- **erc4626-vault.conf** (msg "erc4626-vault pass4 iter 1"), full unfiltered, rule_sanity basic: https://prover.certora.com/orgs/certora/jobs/66877b93-b486-4b26-b282-dde6f3a02ac3/report. 45 rules: 44 VERIFIED, `exitRejectsZeroReceiver` VIOLATED (the accepted pass-3 finding). From `treeViewStatus_25.json`: 293 nodes, all VERIFIED (every `rule_not_vacuous` child included) except that rule's withdraw/redeem instances and their assert nodes. Pass 4 only appended the four `roundingLossBounded*` rules; all earlier rules, helpers and the conf (except `msg`) are unchanged.
- **erc4626-rpow-probe.conf** (separate spec + conf, see below), final full unfiltered run (msg "erc4626-rpow-probe pass4 iter 6"): https://prover.certora.com/orgs/certora/jobs/900b3830-8881-4fca-8499-cab51af8aadf/report. All 39 tree nodes VERIFIED, including every `rule_not_vacuous` child. Iter 4 (32cac59c) had identical rules; only a spec comment changed afterwards. Iter 5 (720b5c6a) died with a server-side "Could not find job results" error and produced no archive.

### rounding_loss_bounded
Rules: `roundingLossBoundedDeposit`, `roundingLossBoundedMint`, `roundingLossBoundedWithdraw`, `roundingLossBoundedRedeem`.
- Each calls the operation and takes the **contract's return value**. It reads `chi = pot.chi()` after the call: this is the operation's chi, because the operation drips first when the Pot is stale, and join/exit never write chi. `depositAccounting` & co. already prove that this post-call chi equals the independently computed dripped value.
- Bounds are asserted on the exact rational loss scaled by RAY, in mathint with no CVL division:
  - deposit: `0 <= assets*RAY - shares*chi < chi` (tight). The property's literal form `assets - shares*chi/RAY < chi/RAY + 1` is the rational statement `assets*RAY - shares*chi < chi + RAY`, which is asserted as well. A literal integer-division reading (`floor(chi/RAY) + 1`) would be false when chi/RAY is not an integer. The rational form is what the property means, and the tight `< chi` implies it.
  - mint: `0 <= assets*RAY - shares*chi < RAY`.
  - withdraw: `0 <= shares*chi - assets*RAY < chi`.
  - redeem: `0 <= shares*chi - assets*RAY < RAY`.
  - The `>= 0` halves additionally show that the rounding never favours the user.
- **Preconditions:** none, except `requirePotChiAtLeastRay()` in the withdraw rule. That precondition is now backed by the proven maker-models invariant `potChiAtLeastRay` (run 9e14d9f8). It is needed because, with chi == 0, `withdraw(0, ...)` returns `_divup(0, 0) == 0` without dividing, and `0 < chi` is then false. With chi == 0, deposit reverts (division by zero), and mint and redeem satisfy their bounds trivially.
- `requireStructuralInvariants()` is not used. The asserts involve only return values and chi, so leaving the invariants out only widens the set of start states.
- All four rules are VERIFIED, and their sanity checks are non-vacuous.
- **New bare requires:** none. `requirePotChiAtLeastRay()` is the existing, proven-backed assumption.

### share_price_monotonic_over_time (PROBE of the real `_rpow`)
**Files:**
- `certora/specs/erc4626-rpow-probe.spec`
- `certora/confs/erc4626-rpow-probe.conf`: the erc4626-vault conf plus `certora/harnesses/RpowHarness.sol` in `files` and `loop_iter: 4`
- `certora/specs/scene-real-rpow.spec`: scene.spec without the two `_rpow` summaries and without the `rpowG` ghost. The NONDET entries are unchanged.
- `certora/harnesses/RpowHarness.sol`

The probe does not import invariants.spec, because invariants.spec imports scene.spec. No probe rule mints or burns.

**RpowHarness:**
- `rpow(x, n)` wraps `_rpow`, whose body is a **verbatim copy** of `SavingsDai._rpow`, extracted from src/SavingsDai.sol with sed.
- `rmulStep(z, x)` is a verbatim copy of the loop's rounded multiplication `z := round(z*x/RAY)` (the `if mod(n,2)` branch). The squaring step is the same computation with z = x. Its overflow check `iszero(eq(div(xx,x),x))` is equivalent for every x, including x = 0 (EVM div(0,0) = 0, so neither check fires). (Pass-4 judge R1: an earlier version wrongly argued "x is never 0 in the loop"; x = 1 squares to 0.)

**Coverage bound (honest statement):** `loop_iter = 4`, with `optimistic_loop` kept true.
- The loop runs floor(log2 n) times. Every bounded rule also requires the exponent `n < 2^4 = 16` (`PROBE_N_BOUND()`), so no covered execution is cut by unrolling.
- The satisfy witnesses `convertToAssetsBoundReachable` (SavingsDai, t - rho = 15, dsr > RAY) and `rpowBoundReachable` (harness, n = 15) are VERIFIED, so the largest covered exponent really executes.
- **Only exponents n = t - rho < 16 seconds are machine-checked end-to-end through the real code.** Larger n are covered only by the step lemmas plus the written induction below.

**Rules (all VERIFIED in the final run):**
- `convertToAssetsMonotonicOverTime(e1, e2, s)` reads the same storage (convertToAssets is a view).
  - Requires `dsr >= RAY`, `rho <= t1 <= t2`, and `t2 - rho < 16`.
  - Asserts `convertToAssets(e1, s) <= convertToAssets(e2, s)`.
  - The first three requires are the property's hypotheses; the fourth is the coverage bound.
  - It runs the real SavingsDai code, including the `t1 == rho` branch, which uses the stored chi.
- `rpowMonotoneInN(x, n1, n2)`: `x >= RAY`, `n1 <= n2 < 16` ⇒ `rpow(x,n1) <= rpow(x,n2)` (harness).
- `rpowMonotoneStep(x, n)`: `x >= RAY`, `n + 1 < 16` ⇒ `rpow(x,n) <= rpow(x,n+1)`.
- **Step lemmas, unbounded:**
  - `rmulStepAtLeastArgs`: a, b >= RAY ⇒ round(ab/RAY) >= a, b.
  - `rmulStepMonotone`: the rounded product is monotone in both arguments.
  - `rmulStepRayIdentity`: round(RAY*x/RAY) == x.
- `convertToAssetsMonotonicOverTimeMainnetDsr` and `rpowMonotoneInNMainnetDsr` add `dsr <= RAY + 2e19` (about 88% APY, above any historical DSR). They were added as smaller queries when the unrestricted rules timed out at loop_iter 6. At loop_iter 4 the unrestricted rules imply them, so they are kept only as a record, under `_justification_rules`.

**History and timeouts (recorded honestly):**
- **iter 1** (loop_iter 6, n < 64): `convertToAssetsMonotonicOverTime` and `rpowMonotoneInN` hit **TIMEOUT**. Both witnesses were VERIFIED. The streamed log was cut off by the 900 s client limit, so statuses were read from `treeViewStatus_496.json` in the job archive.
- **iter 2** (loop_iter 6, rule-filtered): `rpowMonotoneInNMainnetDsr` reported "Solver timed out", so bounding dsr does not rescue n < 64.
- **iter 3** (loop_iter 3, n < 8): all VERIFIED.
- **iter 4 and iter 6** (loop_iter 4, n < 16, with the step lemmas): all VERIFIED. Iter 5 hit an infrastructure error.
- loop_iter 5 was not attempted. Because loop_iter 6 timed out on both formulations, the unbounded coverage instead comes from the lemmas.

**Unbounded argument (pen and paper over the machine-checked step lemmas).**
Notation: r(a,b) = round(ab/RAY), with x_0 = x and x_{k+1} = r(x_k, x_k). For n with bits b_0..b_m, `_rpow` starts with z = x_0 if b_0 else RAY, and for k = 1..m, if b_k then z := r(z, x_k).

Claim: if x >= RAY and both rpow(x, n) and rpow(x, n+1) succeed, then rpow(x, n) <= rpow(x, n+1).

Let j be the number of trailing 1-bits of n. Then n and n+1 agree on the bits above j; n has bit j = 0, and n+1 has bit j = 1 and zeros below it.
1. Every x_k >= RAY, by `rmulStepAtLeastArgs`.
2. After bit j, n+1's accumulator is x_j. For j = 0 it is x_0. For j >= 1 it is r(RAY, x_j) = x_j, by `rmulStepRayIdentity`.
3. After bit j, n's accumulator is R_j, where R_0 = RAY, R_1 = x_0 and R_{i+1} = r(R_i, x_i). By induction, R_j <= x_j:
   - RAY <= x_0;
   - x_0 <= r(x_0, x_0) = x_1, by `rmulStepAtLeastArgs`;
   - R_{i+1} = r(R_i, x_i) <= r(x_i, x_i) = x_{i+1}, by `rmulStepMonotone`.

   Both products are computed by the two successful runs.
4. For k > j the bits agree, and z := r(z, x_k) preserves the order (`rmulStepMonotone`). n+1 has a higher top bit than n only when n = 2^j - 1, and then no k > j remains.

So rpow(x, n) <= rpow(x, n+1) whenever both succeed.

**Intermediate success (pen and paper; pass-4 judge R1).** Chaining the step from n1 to n2 needs every intermediate rpow(x, n) to succeed. Lemma: for x >= RAY, if rpow(x, n+1) succeeds then rpow(x, n) succeeds.
- The reverts in `_rpow` are overflow guards on a product a*b and on a*b + half. Each guard fires iff the exact product exceeds a threshold, so it is monotone: if a*b <= a'*b' and a'*b' passes, a*b passes.
- Squarings: n's run squares x_0..x_{m-1} (m = top bit of n), a prefix of the squarings n+1's run performs (its top bit is >= m). Same operands, so they pass.
- Accumulator steps k < j (only n has bits there): the product is R_k * x_k <= x_k * x_k (point 3), and x_k * x_k is the squaring n+1's run performs to obtain x_{k+1} (k+1 <= j <= top bit of n+1), so it passes.
- Step k = j: only n+1 multiplies there (n's bit j is 0).
- Steps k > j (bits agree): n's accumulator is <= n+1's (points 2-4), and the multiplier x_k is the same, so the product is <= one that passed.
- Downward induction from n2 then gives success of every rpow(x, n), n1 <= n <= n2, so the adjacent steps chain.

This lemma is not machine-checked: the `rmulStep*` lemmas are proven only on non-reverting calls. With it, rpow(x, n1) <= rpow(x, n2) whenever x >= RAY, n1 <= n2 and rpow(x, n2) succeeds. A revert requires an exact product of at least about 2^256 = 1.16e77, i.e. an accrued factor of about 1.2e23 over RAY (about 380 years at 15% APY); the same bound applies to convertToAssets' `rpow * chi`. (Pass-4 judge round 2, N1: an earlier figure, 3e11, was the size of one squaring operand, not the accrued factor.)

The share price is convertToAssets(t) = floor(s * C(t) / RAY), with C(t) = floor(rpow(dsr, t - rho) * chi / RAY) for t > rho and C(rho) = chi. Since rpow >= RAY for dsr >= RAY (points 1 and 2), C(rho) <= C(t). Since floors of products with non-negative factors are monotone, the share price inherits rpow's monotonicity in t. This composition step, and the whole chain for t - rho < 16, is machine-checked by `convertToAssetsMonotonicOverTime`. The induction itself is not machine-checked; it is written here for the judge to verify.

**Result:** no non-monotonicity was found, so there is no finding. A Python brute force of the same algorithm (20k random x in [RAY, 2*RAY], n < 1024) also found no dip.

### New bare requires (pass 4)
- **Probe hypotheses:** `dsr >= RAY`, `t1 >= rho` and `t1 <= t2` (as `x >= RAY` and `n1 <= n2` in the harness rules) restate the property's own premises.
- **Coverage bound:** `n < PROBE_N_BOUND()` defines the probe's stated range. It is not an assumption about reachable states, and is reported as the coverage limit.
- **Mainnet-range records:** `dsr/x <= RAY + 2e19` appears only in the two record rules.
- **Witnesses:** the satisfy witnesses' `dsr > RAY`, `t - rho == 15` and `x > RAY` only select the witness.
- **Vault rules:** none were added to the erc4626-vault rules.
