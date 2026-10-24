VERDICT: ACCEPT

Round 2 of the pass-4 judgement (erc4626-vault, MakerDAO sDAI). Scope:
- the round-1 required changes R1-R3 (all text-only);
- the round-1 remark that vault run 66877b93 used the old scene.spec.

## R1: intermediate success and the "x is never 0" justification. ADDRESSED.

I checked the new "Intermediate success" paragraph (commentary "Pass 4") against the verbatim `_rpow` in src/SavingsDai.sol lines 119-141 (= RpowHarness._rpow).

**Guard monotonicity**
- Each rounded multiply `t := a*b; t' := t + half` has two reverts:
  - `div(t,b) != a` with `b != 0`, or `div(t,a) != a` for the squaring. This fires iff the exact a*b >= 2^256. When b = 0 it never fires, and a*b = 0.
  - `lt(t', t)`. Given no wrap in a*b, this fires iff the exact a*b + half >= 2^256.
- So a step reverts iff the exact a*b >= 2^256 - half. That is monotone in the exact product, as the commentary states.

**Squarings**
- Iteration i of n's loop squares x_{i-1}, for i = 1..m(n) with m = floor(log2 n).
- m(n) <= m(n+1), and the x_k sequence depends only on x. So n's squarings are a prefix of n+1's, with identical operands. Correct.

**Accumulator steps k < j** (bits 1..j-1 are set in n only)
- The product is R_k * x_k, and R_k <= x_k. So it is at most x_k * x_k.
- x_k * x_k is the squaring n+1 performs to obtain x_{k+1}, and k+1 <= j <= m(n+1). Hence no revert.
- The order R_{k+1} <= x_{k+1} then follows from `rmulStepMonotone`, applied to two calls now known not to revert.
- The commentary cites "point 3" for R_k <= x_k. Strictly, point 3 and this lemma are one interleaved induction over k: no revert at step k, then the order at k+1, then no revert at step k+1. This is implicit but sound. Not a required change.
- Edge case n = 2^j - 1: m(n) = j-1 and m(n+1) = j, so every needed squaring x_k^2 (k <= j-1) is in n+1's run. Covered.

**Step k = j**
- Only n+1 multiplies there: r(RAY, x_j), or z = x_0 when j = 0. Correct.

**Steps k > j**
- The bits agree and the multiplier x_k is shared. The accumulators satisfy z_n <= z_{n+1}: the base case is R_j <= x_j, and the order is preserved by monotonicity.
- So n's product is at most a product that passed in n+1's run.

**Downward induction**
- Success of rpow(x, n2) gives success of every rpow(x, n) with n1 <= n <= n2, and the adjacent inequalities chain.
- The lemma is clearly labelled as not machine-checked.

**Wrapper**
- No wrapper success propagation is needed: the property and `convertToAssetsMonotonicOverTime` assume both convertToAssets calls succeed.
- Their rpow values are then the endpoints of the chain, and floors of non-negative products are monotone.

**"x is never 0" fix**
- The commentary (RpowHarness bullet) and the RpowHarness.sol comment now say the two overflow checks are equivalent for every x, with div(0,0) = 0 for x = 0. Correct.
- I compared the working-copy RpowHarness.sol with the probe archive (gen4/probe4, run 900b3830). The only difference is these two comment lines. Code is identical, so the probe result still applies.

## R2: deposit wording of rounding_loss_bounded. ADDRESSED.
- The description now reads: "for deposit, assets*RAY - shares*chi < chi (exact arithmetic; less than one share's worth)".
- This is exactly the tight assert `loss < chi` in `roundingLossBoundedDeposit` (erc4626-vault.spec:766-773), with `loss = assets*RAY - shares*chi` in mathint.
- It can no longer be read with integer division.
- The mint, withdraw and redeem clauses also match their rules.

## R3: scene-real-rpow.spec header. ADDRESSED.
- The header now says three things:
  - the file was cut from the pass 1-3 scene.spec;
  - it keeps `isValidSignature => NONDET`, while scene.spec moved to the `isValidSigG` ghost at the pass-4 barrier;
  - this is irrelevant to the probe, which has no parametric rules and never reaches `_isValidSignature`.
- All three statements are accurate.
- The non-comment content is identical to the probe archive, so the change is comment-only and needs no re-run.

## Barrier re-run on the new scene.spec (round-1 remark). RESOLVED.
Job ec591a60-33da-4080-a457-b98759d0e908 (msg "erc4626vault pass4 barrier"). The log ends EXIT 1, "Prover found violations".

I downloaded the archive and read `treeViewStatus_27.json` (the latest):
- **Totals:** 45 rules, 293 nodes. 288 VERIFIED and 5 VIOLATED.
- **The 5 VIOLATED nodes** are all `exitRejectsZeroReceiver`: the rule, its withdraw and redeem instances, and their asserts. This is accepted finding F-2.
- **Everything else is VERIFIED.** That includes all four `roundingLossBounded*` rules, `sharePriceNeverDecreases` and every `rule_not_vacuous` child.

The run used the current files. In the archive's `.certora_sources`, these are byte-identical to the working copy:
- scene.spec (with `isValidSigG`);
- erc4626-vault.spec;
- invariants.spec.

So the erc4626-vault statuses now hold under the current scene.

## Non-blocking remarks (should be fixed before the final report)
- **N1. Factual error in the new R1 text.** It says "A revert requires a product of at least 2^256, i.e. an accrued factor of about 3e11 (about 190 years at 15% APY)."
  - 3e11 is sqrt(2^256 / RAY^2): the factor each operand of a revert-triggering squaring must have. It is not the accrued factor.
  - The largest product in rpow(x, n) is at most about x^n * RAY. So a revert needs an accrued factor x^n of about 2^256 / RAY^2 ≈ 1.2e23, which is about 380 years at 15% APY.
  - The same threshold applies to convertToAssets' checked `rpow * chi`.
  - The error understates the safe range, so nothing unsound is claimed, but the number is wrong.
- **N2. Barrier run not recorded.** The commentary "Pass 4 / Runs" still cites only run 66877b93, which ran on the old scene. Add barrier run ec591a60 (288/293 VERIFIED; only `exitRejectsZeroReceiver` = F-2 VIOLATED; current scene.spec) as the authoritative erc4626-vault run.
