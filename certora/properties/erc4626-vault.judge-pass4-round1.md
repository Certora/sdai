VERDICT: REJECT

Scope: pass-4 additions only.
- Properties `rounding_loss_bounded` and `share_price_monotonic_over_time`.
- The four `roundingLossBounded*` rules in erc4626-vault.spec ("PASS 4").
- The rpow probe: erc4626-rpow-probe.spec, scene-real-rpow.spec, erc4626-rpow-probe.conf, RpowHarness.sol.
- The pass-4 mappings and status entries in erc4626-vault.property_rules.json.
- The "Pass 4" commentary, including the written induction.

All three required changes are text-only (commentary, property text, a spec header comment). No rule, spec logic, conf or harness code has to change, and no re-run is needed.

**Evidence: run statuses.** I read both archives myself.
- Vault run 66877b93 (`treeViewStatus_25.json`): 293 nodes, 288 VERIFIED and 5 VIOLATED.
  - The 5 VIOLATED nodes are all `exitRejectsZeroReceiver`: the rule, its withdraw/redeem instances and their asserts. This is the accepted finding F-2.
  - All four `roundingLossBounded*` rules are VERIFIED, and so are their `rule_not_vacuous` children.
- Probe run 900b3830 (`treeViewStatus_26.json`): 39 of 39 nodes VERIFIED. This includes every `rule_not_vacuous` child and both satisfy witnesses.

**Evidence: run sources match the working copy.**
- These files are byte-identical to the archived `.certora_sources` (diff -q): erc4626-rpow-probe.spec, scene-real-rpow.spec, RpowHarness.sol, erc4626-rpow-probe.conf.
- erc4626-vault.spec is identical to the copy used in run 66877b93.

**Evidence: the verbatim-copy claim.**
- `RpowHarness._rpow` body vs src/SavingsDai.sol lines 119-141, leading whitespace stripped: identical. `RAY = 10 ** 27` is the same constant.
- `rmulStep` is character-for-character the `if mod(n,2) { ... }` branch (lines 132-136), plus the `half` definition.

## 1. Code smells
No blocking issue.
- **Requires.** No type-bound or revert-preventing requires. Every require is either a hypothesis or the coverage bound (see section 3).
- **Asserts.** No tautological asserts.
  - In `roundingLossBoundedDeposit` the third assert (`loss < chi + RAY`) is implied by the second (`loss < chi`). It is kept on purpose as the literal property form; that is documentation, not a smell.
  - Every assert compares contract return values against `pot.chi()`. These are independent expectations, not restatements.
- **Methods block.** All probe methods-block entries are `envfree` and used.
- **Redundant rules.**
  - `rpowMonotoneStep` is implied by `rpowMonotoneInN` (n2 = n1 + 1) in the bounded range.
  - The two `*MainnetDsr` rules are implied by their unrestricted versions.
  - All three are documented as such and filed under `_justification_rules` / the lemma list. Acceptable.
- **Comment inaccuracy (part of R1).** The RpowHarness comment and the commentary both justify "squaring == rmulStep(x, x)" by "every x in the loop is != 0".
  - That is false in general: x = 1 squares to round(1/RAY) = 0 inside the loop.
  - The equivalence nevertheless holds for every x. With x = 0, `div(0, 0) = 0 == x`, so the squaring does not revert; `rmulStep(0, 0)` does not revert either, because of the `iszero(iszero(x))` guard. In the induction every x_k >= RAY anyway.
  - The justification should be corrected, but the conclusion stands.

## 2. Guideline compliance
No violations.
- No `@withrevert` without a `lastReverted` check, and no `lastReverted` misuse.
- The non-`@withrevert` calls deliberately restrict to successful executions. The rules and the commentary say so: an overflow at t2 is a liveness question and out of scope.
- Constants use `definition`s (`PROBE_LOOP_ITER`, `PROBE_N_BOUND`, `MAINNET_DSR_MAX`).
- The single `requirePotChiAtLeastRay()` is a helper backed by a proven invariant.
- `to_mathint` is used redundantly in a few requires (G19). This is cosmetic and not flagged.

## 3. Precondition validity (every bare require)
**Vault spec, pass-4 rules.**
- The only precondition is `requirePotChiAtLeastRay()` in `roundingLossBoundedWithdraw`.
  - It is backed by the proven maker-models invariant `potChiAtLeastRay`, accepted in earlier rounds.
  - It is genuinely needed: with chi == 0, `withdraw(0, ...)` returns `_divup(0, 0) = 0` without dividing, and `0 < chi` fails.
  - The commentary's case analysis for chi == 0 in the other three rules is correct: deposit divides by zero; mint and redeem give loss 0.
- No structural invariants are assumed. The bounds hold in every start state, so leaving them out only strengthens the rules.

**Probe spec.**
- `pot.dsr() >= RAY()` / `x >= RAY()`: the property's own hypothesis ("with dsr >= RAY").
- `e1.block.timestamp >= rho`: valid. `Pot.drip` sets `rho = now` and requires `now >= rho`, and block time never decreases, so rho <= now in every reachable state. The rule still covers t1 == rho, the stored-chi branch.
- `t1 <= t2` / `n1 <= n2`: the property's hypothesis ("a later timestamp").
- `t2 - rho < PROBE_N_BOUND()` / `n2 < PROBE_N_BOUND()` / `n + 1 < PROBE_N_BOUND()`: the coverage bound. It is not an assumption about reachable states, and it is reported as the coverage limit. Acceptable, because the property text itself asks for "bounded exponents (state the bound)".
- `dsr/x <= RAY + 2e19` appears only in the two record rules, which nothing depends on.
- **Witnesses.** `dsr > RAY`, `t - rho == 15` and `x > RAY` only select the scenario. `t - rho == 15` is a mathint comparison, so there is no wrap.
- **Optimistic loop.**
  - The `_rpow` loop body runs floor(log2 n) times, i.e. at most 3 times for n < 16.
  - loop_iter 4 is therefore never reached on a covered path, so the optimistic unwinding assumption never removes a covered execution. (It would in fact cover n < 32. The stated bound is conservative.)
  - The iteration count depends only on n, not on x. So the n = 15 witnesses (`convertToAssetsBoundReachable` through SavingsDai and `rpowBoundReachable` through the harness, both VERIFIED) show the deepest covered unrolling is reachable, not pruned.

## 4. Property faithfulness

### rounding_loss_bounded
All four bounds are exact characterisations of the code:
- deposit: shares = floor(assets*RAY/chi), so loss = (assets*RAY) mod chi, in [0, chi).
- mint: assets = ceil(shares*chi/RAY), so loss is in [0, RAY).
- withdraw: shares = ceil(assets*RAY/chi), so loss is in [0, chi).
- redeem: floor, so loss is in [0, RAY).

Other checks:
- The asserts use the contract's return values and the post-call `pot.chi()`. That is the chi the operation used: the operation drips first when the Pot is stale, join/exit never write chi, and the existing accounting rules tie post-call chi to the dripped value.
- VERIFIED therefore means the property holds as intended, plus the `>= 0` halves, which the property text does not require.

**Deposit wording.** The generator is right that the literal integer-division reading is false. I checked one counterexample by hand:
- chi = 1.9 RAY, assets = 3 gives shares = floor(3/1.9) = 1.
- Then assets - floor(shares*chi/RAY) = 3 - 1 = 2, which is not < floor(chi/RAY) + 1 = 2.
- Realistic chi values (just above RAY) admit analogous counterexamples.

So the rule is faithful to the rational reading, and that reading is clearly the intended one: "less than one share's worth", and the other three bounds are already stated in scaled-integer form. But the canonical property text currently admits a false reading, and the report will quote it. Amend the text (R2).

### share_price_monotonic_over_time
**Bounded part.** Machine-checked and faithful:
- The rule runs the real `convertToAssets` and the real assembly `_rpow`. No `_rpow` summary is present in the probe scene: the summaries/ files are empty or comment-only, and scene-real-rpow.spec has no `_rpow` entry.
- It runs on one storage state with two timestamps rho <= t1 <= t2, t2 - rho < 16, dsr >= RAY, and both calls succeeding.
- This is exactly the property for exponents < 16 s. The bound is honestly stated in the spec header, the commentary and `_status.probe.coverage`.

**Unbounded written induction (checked step by step).**
- **Model.** `_rpow`, x != 0: z := x if b_0 else RAY. Then for k = 1..m it sets x_k := r(x_{k-1}, x_{k-1}), and z := r(z, x_k) if b_k. The commentary's model is correct.
- **Base cases.**
  - x == 0 is excluded by x >= RAY.
  - n = 0 vs 1 is the j = 0 case: RAY <= x_0.
  - Even n starts at z = RAY and odd n at z = x_0. Both are handled by R_0 = RAY and R_1 = x_0.
  - R_1 = x_0 is also r(RAY, x_0), by `rmulStepRayIdentity`.
- **Point 1.** x_k >= RAY: by induction with `rmulStepAtLeastArgs`. Correct.
- **Point 2.** n+1's accumulator after bit j is x_j: z = RAY until bit j, then r(RAY, x_j) = x_j (`rmulStepRayIdentity`). Correct.
- **Point 3.** R_j <= x_j:
  - R_0 = RAY <= x_0;
  - R_1 = x_0 <= r(x_0, x_0) = x_1 (`rmulStepAtLeastArgs`);
  - R_{i+1} = r(R_i, x_i) <= r(x_i, x_i) = x_{i+1} (`rmulStepMonotone`).
  - Correct. x_{i+1}, for i + 1 <= j, is computed in n+1's run because n+1 has bit j set.
- **Point 4.** For k > j the bits agree, the x_k sequence is shared, and monotonicity in the first argument carries the order. The top-bit-differs case (n = 2^j - 1) has no k > j. Correct.

So the **adjacent** claim holds: if x >= RAY and rpow(x,n), rpow(x,n+1) both succeed, then rpow(x,n) <= rpow(x,n+1). It follows from the three lemmas, together with the (correct) equivalence of the squaring's and rmulStep's overflow guards.

**Gap (R1).** The step from adjacent to arbitrary n1 <= n2 is not argued.
- The commentary concludes "non-decreasing in n over any range of exponents on which it does not revert".
- The property (and the rule) instead assume only that the **two endpoint** calls succeed.
- Chaining rpow(n1) <= rpow(n1+1) <= ... <= rpow(n2) needs every intermediate rpow(x,n) to succeed, and nothing in the write-up establishes that.
- The gap is closable, and the conclusion is true. The missing lemma is: **rpow(x,n+1) succeeds ⇒ rpow(x,n) succeeds**, for x >= RAY. Why it holds:
  - n's squarings are a prefix of n+1's squarings (m(n) <= m(n+1)), and they are the identical computations.
  - Both overflow guards of a rounded multiply are monotone in the operands: `a*b >= 2^256` and `a*b + half >= 2^256`.
  - In Point 3, r(R_i, x_i) has operands <= those of the squaring x_{i+1}, which n+1's run computed. So it does not overflow.
  - In Point 4, r(z_n, x_k) has operands <= those of r(z_{n+1}, x_k), which n+1's run computed.
  - By downward induction, success at n2 gives success at every n <= n2, and the chain goes through.
  - The convertToAssets wrappers are checked 0.8 arithmetic. Their products are monotone in rpow, so success at t2 likewise implies success at t1.
- This step is pen-and-paper reasoning about the overflow guards. The lemmas `rmulStepMonotone` and `rmulStepAtLeastArgs` are proven only on non-reverting calls, so it is not covered by them. It must be written down and labelled as unchecked.

## 5. Coverage claims
- **Mappings.**
  - `rounding_loss_bounded` maps to the four rules. Complete.
  - `share_price_monotonic_over_time` maps to the bounded rules plus the three unbounded step lemmas. Complete for the property as worded ("bounded exponents (state the bound)").
  - Witnesses and record rules are correctly kept out of the mapping, under `_justification_rules`.
- **Bound.** "Machine-checked only for t - rho < 16 s" is accurate and prominently stated. Note how weak this is in practice: it is roughly one block after a drip. The unbounded claim therefore rests on the written argument, which is why R1 is required rather than optional.
- **scene-real-rpow.spec vs the new scene.spec.**
  - scene.spec now models `isValidSignature` with the deterministic ghost `isValidSigG`. scene-real-rpow.spec was cut from the old scene and keeps `NONDET`.
  - **This does not affect the probe.** It has no parametric rules (only `envfreeFuncsStaticCheck`). `convertToAssets` is a view that never reaches `_isValidSignature`, and the harness functions are pure.
  - But the header's claim "IDENTICAL to scene.spec except that it does NOT summarize ... _rpow" is now false (R3).
- **Vault run 66877b93 predates the scene.spec change.** Its archived scene.spec still has `_.isValidSignature => NONDET`.
  - The four rounding rules never reach `isValidSignature` (deposit/mint/withdraw/redeem do not verify signatures), so their verdicts carry over.
  - For the prior parametric rules that include `permit` (e.g. `sharePriceNeverDecreases`), the recorded statuses were produced under the old scene. Outside this pass's scope, but before any "current spec" claim is made, the final report should either re-run erc4626-vault.conf with the new scene or state which scene the 66877b93 statuses refer to.
- The history (loop_iter 6 TIMEOUTs; iter 5 infrastructure failure) is recorded honestly.

## Required changes
- **R1. Close the induction gap.** In erc4626-vault.commentary.md "Pass 4", add the success-propagation lemma ("rpow(x,n+1) succeeds ⇒ rpow(x,n) succeeds", from the prefix-of-squarings and operand-monotone overflow guards argued in section 4) and the downward induction that turns the adjacent claim into "rpow(x,n2) succeeds ⇒ rpow(x,n1) <= rpow(x,n2) for all n1 <= n2". State it as unchecked pen-and-paper reasoning. Alternatively, weaken the stated unbounded claim to "for n1 <= n2 such that every rpow(x,n), n1 <= n <= n2, succeeds". Also correct the "x is never 0 inside the loop" justification in the commentary (and, as a comment-only change, in RpowHarness.sol): the guard equivalence holds for all x, including 0, and every x_k >= RAY here anyway.
- **R2. Amend the deposit clause** of `rounding_loss_bounded` in erc4626-vault.properties.json so it cannot be read with integer division. For example: "for deposit, assets*RAY - shares*chi < chi + RAY (i.e. assets - shares*chi/RAY < chi/RAY + 1 in exact arithmetic; less than one share's worth plus 1 wei)". Or state the tight bound `< chi` that is actually proven.
- **R3. Fix the scene-real-rpow.spec header.** It should say the file derives from the pre-pass-4 scene.spec and keeps `isValidSignature => NONDET`, which is sound and irrelevant to the probe (no rule reaches `_isValidSignature`). Or re-sync the file with the current scene.spec minus `_rpow`; that requires a probe re-run. Correcting the comment needs no re-run.
