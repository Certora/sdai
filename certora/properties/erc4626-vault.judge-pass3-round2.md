VERDICT: ACCEPT

Scope: this round re-checks the single required change and the two optional nits from pass 3 round 1, and looks for regressions.

**Evidence: what changed between the two runs.** I diffed the round-1 run sources (`.certora_internal/26_10_23_19_22_03_863747c7f9/.certora_sources`, job 4552c067) against the round-2 sources (`.certora_internal/26_10_23_19_44_15_3975375bae/.certora_sources`, job 7da047cb).
- The only spec change is in `depositReferralEquivalent` and `mintReferralEquivalent`. In each, `assert !revertedRef => afterRef == afterPlain, ...` became a top-level `assert afterRef == afterPlain, ...`, with a two-line explanatory comment added.
- The conf differs only in `msg` ("pass3 iter 2").
- Nothing else changed: no other spec, harness, source or conf change.
- The working-copy spec has the same md5 as the run-2 snapshot (d70765bd...), so the run reflects the current file.

**Evidence: run results.** From log certora/logs/erc4626-vault_pass3_run2.log (job 7da047cb):
- 41 rules, 40 Verified. Both referral rules are listed as `Verified:` (lines 139-140).
- Their `-rule_not_vacuous` sanity sub-checks print "Violated", which in that streamed form means the rule is non-vacuous (lines 184 and 190).
- The final error lists only `exitRejectsZeroReceiver` (withdraw and redeem), the expected finding.
- The wildcard summaries are reported unused, so the storage comparison is not trivialized by havoc.

## 1. Code smells
No issue. The change removes an implication around the storage assert and adds no require or tautology. The explicit balance asserts remain and are documented as kept for readable counterexamples.

## 2. Guideline compliance
No violations.
- Return values of `@withrevert` calls are still read only under `!revertedRef` (G16).
- The new assert reads only `storage` variables, which are defined on every path, so dropping the guard is legal.
- Every rule still ends in assert or satisfy.

## 3. Precondition validity
Unchanged from round 1 (accepted). The referral rules still assume nothing, so they are as strong as possible.

## 4. Overconstrained inputs
Unchanged. The only constrained input is `require ab == a + b` in the split rules, accepted in round 1, and the diff shows it untouched.

## 5. Trivializing summaries
No issue.
- Every external call in the four referral entry points reaches linked code: the log reports `_.approve`, `_.vat`, `_.hope` and `_.dai` unused.
- `rpowG` is a deterministic ghost function shared by both paths.
- So `afterRef == afterPlain` is not made trivially true or false by NONDET havoc.

## 6. Manifest errors
Resolved.
- **Supported form.** The storage comparison now uses the supported top-level `assert s1 == s2` form (expr.txt, "Comparing storage"), not the experimental nested form.
- **Strength.** The unconditional form is at least as strong as the old one:
  - if both calls revert, both snapshots are the rolled-back `init` (no persistent ghosts);
  - if exactly one reverts, the preceding `<=>` assert already fails;
  - the in-spec comment and the commentary state exactly this.
- **Wording nits.** Both optional nits were applied:
  - the `_expected_fail` detail now says the witness chi (~5.9e76) is "not a realistic value", that the zero-receiver path does not depend on chi, and that the witness is an illustration only;
  - receiver == SavingsDai is noted as a second, out-of-scope sink.
- **Wording kept.** Commentary line 106 still says `requirePotChiAtLeastRay()` "restricts the witness to realistic states". That describes the chi >= RAY trust assumption, not the witness's chi value, so it is not a contradiction.
- **Finding.** The `exitRejectsZeroReceiver` finding and its severity framing are unchanged and still correct.

## 7. Meaningful contract interaction
No issue. The referral rules assert on return values, `lastReverted` and the full `lastStorage` of real calls.

## 8. Property coverage
Each of the four properties is mapped to rules:
- **referral_overloads_equivalent:** now fully formalized. Revert equivalence, return-value equality and whole-scene state equality are all asserted, the last through the supported storage-comparison form.
- **conversions_and_previews_monotonic:** covered as in round 1, rules unchanged.
- **no_gain_from_splitting_operations:** covered as in round 1, rules unchanged.
- **exit_rejects_invalid_receiver:** recorded as an expected-fail finding with a VERIFIED witness, unchanged.

**Records.**
- property_rules.json points to job 7da047cb, with matching statuses and a note describing iter 2.
- The commentary adds a "Pass 3 round 2" section with the new link and says it supersedes the iter-1 link that remains in the earlier section. That is acceptable as history.

**Unchecked claim.** I could not re-read `treeViewStatus_24.json`: the local zip holds only the job inputs, and the output archive is not present locally. The streamed log is consistent with the claimed node statuses.

## Required changes
None.
