VERDICT: ACCEPT

Judge, component `permit`, pass 4 round 1. The main subject is the scene change to `_.isValidSignature`.

**What I reviewed**
- certora/specs/scene.spec
- certora/specs/permit.spec (PASS 4 block)
- certora/specs/invariants.spec
- every spec that imports scene.spec
- src/SavingsDai.sol: `_isValidSignature` and both `permit`s
- permit.properties.json and permit.property_rules.json (`_pass4_probe`)
- permit.commentary.md ("Pass 4")
- the pass-2 verdict
- cvl-writing.md (judge checklist) and cvl-pitfalls.md (summaries)

**File identity checks (by diff)**
- scene.spec is byte-identical to scene-1271.spec.
- permit.spec differs from permit-1271.spec only in its imports and header comment.
- invariants.spec differs from invariants-1271-probe.spec only in its import and header comment.
- permit.conf and invariants.conf differ from the probe confs only in `verify` and `msg`.
- So the probe runs are valid evidence for the barrier configuration.

**Evidence: probe runs, downloaded and checked in treeViewStatus**
- permit-1271, run cde4dfd2 (final treeViewStatus_23):
  - all 10 rules are VERIFIED;
  - every `rule_not_vacuous` check is VERIFIED;
  - so is `envfreeFuncsStaticCheck`.
- invariants-1271-probe, run 175a9bd1 (treeViewStatus_10):
  - `totalSupplyIsSumOfBalances`, `sharesBackedByPie` and `zeroAndSelfHoldNoShares` are VERIFIED, base case and step;
  - the base-case vacuity and non-trivial-postcondition checks are VERIFIED.
- In alertReport.json of cde4dfd2:
  - the scene summaries `_.hope`, `_.approve`, `_.vat` and `_.dai` are flagged "unused";
  - `_.isValidSignature` is not flagged, so it was applied.

**Barrier runs: still in progress when I judged.** permit is ea39b316 and invariants is 32094aa6. Their logs show only "Job submitted", so this verdict rests on the identical probe runs. The ACCEPT holds only if both barrier runs come back all-VERIFIED with vacuity checks passing. Any difference from the probe means re-judging.

## 1. Code smells
No blocking issue.
- **`formsAgree` is a clean helper.**
  - It calls the pure `packer.pack` before taking the snapshot.
  - Both runs use `at init`.
  - It returns a single conjunction.
  - The three new rules are minimal and have no stray requires.
- **Stale comments (non-blocking, fix in the doc pass).** These now contradict the scene:
  - The doc comment of `permitSignatureFormsEquivalent` says a mis-decode "would fall through to the NONDET ERC-1271 staticcall and the two runs could disagree", and calls the two executions' answers "independent".
  - The doc comment of `permitVrsDecodesPackedSignature` says "(NONDET) ERC-1271 path".

  The scene is now deterministic, so these sentences are wrong (see 4 for what still holds).

## 2. Guideline compliance
No issue.
- **The summary follows the pitfalls guidance.**
  - It uses the wildcard receiver (`_.`), so it reaches the call to the arbitrary `owner` address.
  - It has the `expect bytes4` clause, which matches the callee's true return type.
  - It uses `calledContract` to stand for the signer.
  - No `bytes` value goes into CVL. That avoids the pass-2 failure mode (run 401dc586).
- **The ghost is non-persistent.** Any havoc from an unresolved call would also havoc the signer's answers, which is the right behaviour for "signer state changed".
- **No `persistent` misuse.**
- **Quantified requires only use ecrecover and the ghost function.** Both are allowed inside quantifiers.

## 3. Precondition validity
No issue.
- **`permitSignatureFormsEquivalentAnyPath` has no precondition.**
- **`permitSignatureFormsEquivalent1271Path`** requires `forall d. ecrecover(d,v,r,s) != owner`.
  - This constrains only the uninterpreted ecrecover, at the single point (v,r,s).
  - It is satisfiable, and its vacuity check passed.
  - Its purpose is to force the 1271 branch to be exercised, not to prune a counterexample.
- **`permit1271PathDecidedBySignerGhost`** requires the same thing, plus a fixed answer for `owner` on every digest.
  - Both constraints are on uninterpreted functions only, and each is satisfiable for either value of `accept`.
  - `checksPass` sits on the left of the implication, not in a `require`.

## 4. Property faithfulness
`permit_signature_forms_equivalent` is now proven on every signature path. The only caveats are the stated trust assumptions.

**`permitSignatureFormsEquivalentAnyPath` is the literal property with no assumption.**
- Same pre-state, v-form against `abi.encodePacked(r,s,v)` built by Solidity.
- Asserts the same revert status, the same `allowance[owner][spender]` and the same `nonces[owner]`.
- This closes the 1271 gap that the pass-2 verdict recorded.

**`permit1271PathDecidedBySignerGhost` confirms the summary is really wired in.** It shows three things:
- the summary reaches SavingsDai's low-level `owner.staticcall(abi.encodeWithSelector(...))`;
- the bytes4 is decoded as the magic-value comparison expects;
- the outcome of permit depends on the ghost.

Why the result is conclusive:
- `accept` is free, so both directions are proven.
- If the summary had not applied, the staticcall result would be unconstrained and the `accept => !lastReverted` direction would fail.
- The alert report agrees.

**Decode-bug coverage after the change.**
- With a deterministic 1271 model, a decode bug shared by both forms would no longer make the equivalence rules fail. Both forms go through the same `_isValidSignature`, and two runs with the same wrong (v,r,s) now get the same 1271 answer. The pass-2 remark "still holds if both forms decode the same wrong tuple" no longer applies to `permitSignatureFormsEquivalent`.
- This is not a coverage loss for the property. Decode correctness is still pinned by `permitVrsDecodesPackedSignature`:
  - it asserts that ECDSA accepts and the checks pass, therefore no revert;
  - after a mis-decode, ecrecover is evaluated at an unconstrained point and `isValidSigG(owner, digest)` is unconstrained, so a revert is reachable and the rule would fail.
- So it remains a genuine check. Keep it in the mapping, as the proposed `proposed_property_rules_after_barrier` does.

**Mapping and description.**
- The mapping proposal (six rules) is appropriate.
- The extended description in permit.properties.json states the model accurately.

**Gas caveat.** The pass-2 gas caveat (gas-dependent signers) is carried into the scene header as a trust assumption. Good.

## 5. Scene-change soundness
Sound for every spec that imports scene.spec. The model removes no reachable outcome of `_isValidSignature` within a single execution. The cross-call determinism it adds is faithful to a STATICCALL wherever it is exercised.

**a. Does the summary apply to the low-level call?** Yes.
- The selector is built by `abi.encodeWithSelector(IERC1271.isValidSignature.selector, ...)`, and the target is the symbolic `owner`.
- The call is therefore unresolved, and the wildcard's default UNRESOLVED policy applies.
- Evidence: the alert report does not mark it unused, and the model-check rule VERIFIES.

**b. Return-data shapes and reverts that become unreachable.**
- Under the summary these become unreachable:
  - callee revert (`success == false`);
  - return data shorter or longer than 32 bytes;
  - a 32-byte word whose low 28 bytes are non-zero;
  - out-of-gas inside the callee, including the 63/64 gas-burn griefing that could make permit itself OOG.
- In `_isValidSignature`, each of these yields `false`. That is exactly the result of any non-magic bytes4 from the ghost, which stays reachable. So the set of `_isValidSignature` outcomes, {true, false}, is unchanged, and state after the call is unaffected because the callee is a staticcall.
- The only behaviour truly lost is gas exhaustion. The prover does not model gas anyway, and the header lists it as an assumption.

**c. Over-approximation for targets without ERC-1271.**
- For an EOA owner, or `owner` equal to a scene contract with no `isValidSignature` (SavingsDai, Pot, Vat, Dai, DaiJoin, SigPacker), the real call always yields false. The ghost may return the magic value instead.
- This only adds behaviours. It is sound for safety assertions, and no rule relies on 1271 rejection for such owners.

**d. Ignoring the signature bytes.** I grepped every spec under certora/specs and certora/specs/maker-models.

`SavingsDai.permit` is reached:
- once per path in erc20-token.spec (`callWithArgs`, parametric `f`);
- once per parametric step in invariants.spec, maker-integration.spec, sanity-linked.spec, maker-models/setup-third-party.spec and pot-invariants.spec;
- twice only in permit.spec.

The multi-call `at init` rules in erc4626-vault.spec use deposit, mint, withdraw and redeem, which never reach `isValidSignature`. `Dai.permit` there and in setup-third-party uses ecrecover only, and no harness or mock in the scene calls `isValidSignature`.

The two-permit rules in permit.spec, checked one by one:

| Rule | Bytes in the two runs | Effect of the model |
|---|---|---|
| `permitSignatureFormsEquivalent`, `...AnyPath`, `...1271Path` | Identical: v-form `abi.encodePacked(r,s,v)` = `packer.pack(v,r,s)` | Ignoring the bytes loses nothing. |
| `permitSignatureFormsSameEffects` | May differ (its `requirePacked` is known not to tie the bytes) | Equal answers only prune behaviours. Its assertions (both revert on expired deadline or zero owner; equal effects when both succeed) hold for every answer pair, so nothing is hidden. |

No rule makes two calls with different bytes and the same (owner, digest) and then asserts something sensitive to the answers differing. **Not an over-constraint in the current spec set.**

**e. Determinism across calls.**
- A STATICCALL cannot modify state, so with the same input and the same world state its answer is a function of the input. Gas is the exception, and it is excluded.
- Two permit calls can share (owner, digest) only in three cases:
  - both start from one snapshot (`at init`), so the signer state is identical;
  - the first reverted, so nothing it did persists;
  - the nonce wrapped after 2^256 permits.
- The signer's state could change between such calls only through a state-changing call to the signer. SavingsDai makes none to `owner`. An unresolved havoc would also havoc the non-persistent ghost.
- **Determinism is a faithful model here.**

**f. Invariants.**
- The ghost is unconstrained, so each parametric permit step sees an arbitrary bytes4. That is a superset of the real behaviour.
- The constructor makes no `isValidSignature` call.
- The pass-2 breakage (impossible storage changes in `permit(bytes)`) came from passing `bytes` into a CVL function. This model avoids it.
- Probe 175a9bd1 confirms: all three invariants VERIFIED on every method, both permits included.
- The barrier invariants run (32094aa6) must reproduce this.

## Required before closing pass 4 (bookkeeping, not spec changes)
1. Wait for barrier runs ea39b316 (permit) and 32094aa6 (invariants), plus the other scene importers. All must be VERIFIED, with vacuity checks passing.
2. Then promote `_pass4_probe.proposed_property_rules_after_barrier` into the main `permit_signature_forms_equivalent` mapping, and update `_status` to the barrier run.

## Non-blocking remarks
1. Update the stale "NONDET" wording in the doc comments of `permitSignatureFormsEquivalent` and `permitVrsDecodesPackedSignature`.
   - Under the deterministic model, the first rule's non-trivialisation argument covers only a decode mismatch between the two forms.
   - A decode bug shared by both forms is caught by `permitVrsDecodesPackedSignature`.
2. Update permit.commentary.md:
   - "Pass 4" still says "probe ... without editing the shared scene.spec" and points to scene-1271.spec / permit-1271.spec.
   - The Pass 2 "Remaining gap (ERC-1271 path)" section should be marked as closed by Pass 4.
3. Optionally add `satisfy accept && !lastReverted` alongside `permit1271PathDecidedBySignerGhost`, to witness the success branch explicitly. The current assertion already implies it whenever `checksPass` is satisfiable.
4. After the barrier, consider deleting the probe files (scene-1271.spec, permit-1271.spec, invariants-1271-probe.spec and their confs). That avoids two diverging copies of the scene.
