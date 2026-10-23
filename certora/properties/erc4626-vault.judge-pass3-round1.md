VERDICT: REJECT

Scope: the PASS 3 section of certora/specs/erc4626-vault.spec (lines 488-740), its conf, property_rules.json, the "Pass 3" commentary, the run log, and the archive of job 4552c067 (downloaded; ctpp traces read).

Nothing earlier was altered. I diffed the files against the pass-2 run snapshot (.certora_internal/26_10_21_04_44_01_*/.certora_sources):
- lines 1-485 of the spec are byte-identical;
- scene.spec, invariants.spec, all four harnesses and src/SavingsDai.sol are identical;
- the conf differs only in `msg`.

There is one required change, a small one (criterion 8, backed by criterion 6). Everything else is acceptable.

## 1. Code smells

No issue.
- **Requires.** The only new bare require is `require to_mathint(ab) == a + b`. It is not a type-bound or revert-avoiding require (see criterion 4).
- **Tautologies.** No assert is tautological.
  - The monotonic and split rules compare outputs of two independent contract executions.
  - The referral rules compare two executions from one snapshot.
  - The explicit balance asserts in the referral rules are redundant with the storage comparison. The comment says so and keeps them for counterexample readability, which is harmless.
- **Methods block.** No new methods-block entries were added.

## 2. Guideline compliance

No violations.
- **G16.** Return values of `@withrevert` calls are used only under `!revertedRef`. Because asserts are cumulative, the earlier `revertedRef <=> revertedPlain` assert also guarantees `!revertedPlain` at that point. The typechecker's G16 warnings in the log are therefore addressed.
- **G1.** Every rule ends in assert or satisfy.
- **G3/G4.** Types are used correctly: uint256 for call arguments and results, mathint for sums.
- **G12.** `method f` appears only as a rule parameter. `callWithdrawOpWithRevert` dispatches on the selector, as the accepted pass-1 helpers do.
- **Revert-characteristic preference.** `exitRejectsZeroReceiver` is a one-directional "receiver == 0 => reverted" rule with the receiver fixed to 0. That matches the property's scope, and the rule contains no bare require.

## 3. Precondition validity

No issue.
- Rules that mint or burn shares and whose verdict depends on post-state (the split rules and the finding rule) use `requireStructuralInvariants()`.
- Some rules go without it, which only makes them stronger:
  - the referral, monotonic-view and monotonic-op rules compare return values or whole-state equality, which do not depend on the unchecked `_mint`/`_burn` arithmetic;
  - in particular, the monotonic-op return values are computed before `_mint`/`_burn` runs.
- A spurious starting state can cause no false violation:
  - when chi == 0, the view and withdraw divisions revert, and non-`@withrevert` calls drop those paths;
  - Pot.join requires `now == rho`, so a state with `now < rho` reverts on both sides.

## 4. Overconstrained inputs

The new `require to_mathint(ab) == a + b` is acceptable. I checked each case of the justification against the source:
- **deposit:** `assets * RAY` is evaluated outside `unchecked` (SavingsDai.sol:300), so both a and b are below 2^256/10^27 and their sum fits in a uint256.
- **withdraw:** `_divup(assets * RAY, chi)` has its argument computed in checked context (SavingsDai.sol:342), so the same bound applies.
- **mint:** Pot.join does `Pie = Pie + wad` with 0.8 checked arithmetic (harnesses/Pot.sol), applied twice, so Pie + a + b fits.
- **redeem:** `_burn` requires `balance >= shares` on both calls, and nothing between the two calls credits the owner, so a + b <= the owner's prior balance.

So no path in which both split operations succeed is dropped. The commentary also states that the rules are silent when the split succeeds but the combined operation reverts. That is the honest scope of a success-only rule, and it is consistent with how every other success-only rule here was accepted.

`requirePotChiAtLeastRay()` appears only in the satisfy witness. It is the accepted pass-1 trust assumption, backed by `potChiNeverDecreases`, and in a satisfy rule it can only narrow the witness.

## 5. Trivializing summaries

No issue, and this point matters for the storage comparison.
- The log reports "Summarization for external calls of _.approve / _.vat / _.hope / _.dai is unused". The wildcard UNRESOLVED NONDETs therefore never fired in any rule. Every call in deposit/mint/withdraw/redeem reached linked code, and no havoc can make `afterRef == afterPlain` vacuous (expr.txt warning 1).
- `rpowG` is a deterministic ghost function. Its ghost is shared by both sides of every two-path rule, and both paths drip with the same env. The split rules' claim that the second op of path 1 sees the same chi (rho == now after the first drip) is correct.

## 6. Manifest errors

**Correctness of the rules.** No rule contradicts correct behaviour, and every `at init` is placed correctly:
- the snapshot is taken before the first call;
- the second path is entered with `at init`;
- all reads for path 1 happen before the second path starts.

**The finding is genuine on mainnet-faithful contracts.**
- `_burn` (SavingsDai.sol:241-266) never checks `receiver`.
- `DaiJoin.exit` (harness = mainnet dss join.sol logic) requires only `live == 1`.
- `Dai.mint` (harness = mainnet dai.sol: `balanceOf[usr] = add(...)`, `totalSupply = add(...)`) has no zero-address check.
- The CEX for both methods is a zero-amount call.
- The VERIFIED satisfy witness `exitToZeroReceiverWitness` (trace read from the archive) shows withdraw(12, 0, 0x8200) succeeding with 1 share burned and Dai.balanceOf(0) going 7 -> 19.

**The severity framing is right.**
- It is low severity, a robustness/UX footgun, not a theft vector:
  - only the owner or an approved spender can trigger it;
  - such a spender could already withdraw the funds to itself, so the call adds no new capability;
  - ERC-4626 does not mandate the check.
- The asymmetry with the deposit side, proven in `invalidReceiverRejected`, is a fair note.

**Two cosmetic nits** (not required):
- The witness's chi is about 5.9e76, far from "realistic". The commentary's "from a realistic state" wording in the expected-fail detail is therefore overstated, but the finding rests on code that is plain from the source, not on that witness value.
- The same sink exists for receiver == address(this): DAI minted to sDAI is unrecoverable. The property is scoped to address(0), so this is not a coverage gap. It could be mentioned in the finding.

**One problem: the referral rules nest a storage comparison inside an implication** (`assert !revertedRef => afterRef == afterPlain`).
- expr.txt, "Comparing storage", second warning: "support within the Prover for these comparisons is primarily aimed at assertions of storage equality, e.g., `assert s1 == s2` ... nesting comparisons within other expressions is considered experimental."
- The headline claim of `referral_overloads_equivalent` ("same resulting state", "the ENTIRE scene") rests on the experimental form. The commentary cites this same docs section as its authority without mentioning the warning.
- A VERIFIED result on an experimental encoding is not hard evidence for that claim.

## 7. Meaningful contract interaction

No issue.
- **Monotonic and split rules:** every assert reads contract return values or post-state contract storage (`balanceOf`, `Dai.balanceOf`).
- **Referral rules:** every assert reads return values, `lastReverted` and `lastStorage`.
- **Finding rule:** its assert reads `lastReverted` of a real call.
- **Witness:** its satisfy reads post-state from Dai and SavingsDai.

## 8. Property coverage

Each of the four properties is mapped to rules:
- **conversions_and_previews_monotonic:** 6 view rules plus 4 operation rules. Fully covered.
- **no_gain_from_splitting_operations:** 4 rules. Each asserts on both return values and end state. Fully covered.
- **exit_rejects_invalid_receiver:** `exitRejectsZeroReceiver`, recorded as an expected-fail finding, unweakened, with a witness. Covered.
- **referral_overloads_equivalent:** the revert-equivalence and return-value parts are covered. The "same resulting state" part is backed beyond the four explicit reads only by the nested storage comparison flagged under criterion 6. It is not reliably formalized until that assert uses the supported form.

## Required changes

1. **Use the supported storage-comparison form.** In `depositReferralEquivalent` and `mintReferralEquivalent`, replace `assert !revertedRef => afterRef == afterPlain, ...` with an unconditional `assert afterRef == afterPlain, ...`.
   - This is semantically equivalent and at least as strong:
     - if both calls revert, each `lastStorage` is the rolled-back `init`, ghosts included, since none are persistent (G11);
     - if exactly one reverts, the preceding `revertedRef <=> revertedPlain` assert already fails.
   - Re-run the full unfiltered conf and update the run link and statuses in property_rules.json and the commentary.
   - In the commentary, cite the `assert s1 == s2` form explicitly.
   - If the unconditional form unexpectedly fails, report the CEX rather than reverting to the nested form.

Optional (not required): soften "realistic state" in the `_expected_fail` detail for `exitRejectsZeroReceiver`, since the witness chi is about 5.9e76. Optionally note that receiver == SavingsDai is a second unrecoverable sink.
