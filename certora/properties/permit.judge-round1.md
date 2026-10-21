VERDICT: ACCEPT

Judge round 1, component `permit`. Reviewed: certora/specs/permit.spec, certora/confs/permit.conf, scene.spec, invariants.spec, src/SavingsDai.sol (`_isValidSignature`, both `permit`s), permit.properties.json, permit.property_rules.json, permit.commentary.md, logs permit_run1-4, CVL docs (types.html, expr.html "ECRecover"). I also checked the run 53186bb4 counterexample myself (Reports/ctpp_permitSignatureFormsEquivalent.txt).

## 1. Code smells
No blocking issue.
- The methods-block entries (`nonces` and `allowance` envfree) are used. I found no type-bound requires and no requires that only stop reverts.
- `permitSignatureFormsSameEffects` is effectively a corollary of other rules. Its `requirePacked` does not tie `signature` to (r, s, v) (see 8). Its second assert (both succeed => same allowance and nonce) therefore follows from `permitEffects`, and its first assert duplicates `permitRevertsOnExpiredOrZeroOwner`. The asserts are not tautological: they read contract state after two real executions. They are redundant, not wrong. The commentary already says the packing constraint has no effect there, so I am not requiring a change.

## 2. Guideline compliance
No issue.
- Every rule ends in asserts. CVL functions end in `return`. The void function has no returns clause.
- `byteOf` uses division and modulo, not bitwise ops (guideline 10).
- The quantifier bodies contain only `ecrecover`, which expr.html explicitly says is supported in quantified expressions (guideline 13).
- mathint is used for the nonce arithmetic. Contract results are uintK.
- Revert rule: the "revert characteristic" form (`<=>`) cannot be stated here. Signature validity depends on the NONDET ERC-1271 call and on a digest CVL cannot recompute. The one-directional `(expired || zeroOwner) => reverted` has no requires, so nothing truncates it.

## 3. Precondition validity
No issue. No rule depends on a structural invariant: nonces and allowances are written only in permit/approve paths and need no global state assumptions. The parametric rules over all SavingsDai methods verified with all sanity checks passing.

## 4. Overconstrained inputs
No blocking issue.
- `noncesNeverDecrease: require nonceBefore < max_uint256`. I do not accept the "unrealistic" argument on its face. Here, though, the evidence is verifiable inside the spec. `nonceChangesOnlyViaPermit` proves, with no requires, that every nonce change is exactly `+1 mod 2^256` and happens only in permit. So reaching max_uint256 needs 2^256-1 successful permits for one owner. The require also excludes exactly the single wrap point, which is the one state where the literal property "never decreases" is false by design (an unchecked `++`). The assumption-free modular statement is already proven. Non-blocking suggestion: replace the require with `assert nonces(holder) >= nonceBefore || (nonceBefore == max_uint256 && nonces(holder) == 0);`, which would make the rule assumption-free.
- `permitEffects`: the only requires (`otherOwner != owner || otherSpender != spender`, `otherNonceHolder != owner`) define what "other" means. They are correct.
- `forall bytes32 d. ecrecover(d, v, r, s) == owner` (used in permitVrsDecodesPackedSignature and permitSignatureFormsEquivalent):
  - It is sound. It constrains only the uninterpreted ecrecover ghost, not contract state.
  - It is satisfiable. The generator added none of the docs' optional axioms; the "uniqueness of signature" axiom would contradict it, and that axiom is absent. rule_sanity basic passed, and a rule_not_vacuous witness exists.
  - It does not trivialize the check. It fixes ecrecover only at the point (·, v, r, s). If the contract's decode produced any (v', r', s') ≠ (v, r, s), ecrecover there is free and the NONDET 1271 fallback can fail, so the rule would be violated. Quantifier grounding substitutes d := digest and cannot reach other (v, r, s).
  - The rule verified even though the 1271 path is pessimistic (NONDET). That also shows the contract's precompile ecrecover is the same ghost as CVL `ecrecover`; if it were not, the assumption would have had no effect and the rule would have failed.
  - Quantifying over every digest is needed because the digest (`"\x19\x01"`-prefixed encodePacked) cannot be recomputed in CVL. It is a strict generalisation of "valid for this digest", so it loses nothing for a decode check.

## 5. Trivializing summaries
No issue.
- `_.isValidSignature => NONDET` is applied to the low-level staticcall (the trace shows "NONDET summary @ scene.spec:31"). This is sound for a view staticcall.
- The summary is pessimistic for the decode rule, which is what gives that rule its meaning.
- It does not weaken `permitEffects`: the effects are stated under `!reverted`, and the frame conditions hold unconditionally.
- On the optional deterministic ghost `isValidSigG(calledContract, digest, keccak256(signature))`: NOT needed, and it would not close the gap. Equivalence on the ERC-1271 path would require relating `keccak256` of the CVL-supplied `bytes` to `keccak256(abi.encodePacked(r, s, v))`. That relation is blocked by the same CVL-`bytes` incoherence described in 8. In the contract, the v-form literally calls the public `permit(bytes)` with the packed bytes, so the 1271 path is structurally identical in both forms. I recommend no scene change.

## 6. Manifest errors
No issue.
- `requirePacked` matches `abi.encodePacked(r, s, v)` and the contract's decode: r in bytes 0..31 big-endian (`mload(sig+0x20)`), s in 32..63 (`mload(sig+0x40)`), v at byte 64 (`byte(0, mload(sig+0x60))`). `byteOf(word, k) = (word / 2^(8*(31-k))) % 256` extracts the most significant byte first, which is correct.
- The expected failure of `permitSignatureFormsEquivalent` is NOT caused by a spec mistake. I checked the run 53186bb4 model myself:
  - The CVL `bytes` value is a bytemap where `signature[i]` = top byte of `map[i]`, and the words at overlapping offsets are not kept coherent.
  - With rWord = 0x9, sWord = 0xd, v = 0xc: `map[0x3f] = 0x0d00..00` (byte 63 = 0x0d, byte 64 = 0x00), `map[0x40] = 0x0cff..ff` (byte 64 = 0x0c), and `map[0x20] = 0x00..0c` (byte 63 = 0x0c).
  - The contract's `mload` at data offset 0x20 therefore reads s' = 0xc ≠ s, ecrecover misses, 1271 is NONDET, and only the bytes form reverts.
- Classification as `prover_limitation` is upheld. The byte-indexing constraints are the only way CVL offers to build a `bytes` value; there is no `abi.encodePacked` in CVL; harnesses are off-limits per the brief; and precise_bitwise_ops was tried. Keeping the rule as a documented expected-fail is acceptable.
- Side observation: the counterexample also has `nonces[owner] = MAX_UINT256` wrapping to 0. That is irrelevant to the failure and consistent with the unchecked increment.

## 7. Meaningful contract interaction
No issue. Every assertion reads contract state (`allowance`, `nonces`, `balanceOf`, `totalSupply`) or `lastReverted` after real calls. The decode rule's verdict depends entirely on the contract's pack/mload/byte/ecrecover path.

## 8. Property coverage
Covered. The remaining gap is acceptable and documented.
- `permit_revert_on_expired_or_zero_owner`: `permitRevertsOnExpiredOrZeroOwner`, both entry points, no requires. Full.
- `permit_effects`: `permitEffects`, both forms.
  - It checks allowance exactly equal to `value`, and `nonces[owner] == (before + 1) mod 2^256` (exactly +1 except at the unreachable wrap, as the unchecked `++` does).
  - It also checks that every other allowance pair, every other owner's nonce, every `balanceOf` and `totalSupply` are unchanged. These are asserted unconditionally, which is stronger than "after success". Full.
- `nonces_only_increase_via_permit`:
  - `nonceChangesOnlyViaPermit` (no requires): a change implies a permit selector and +1 mod 2^256.
  - `permitEffects`: only the owner's nonce moves.
  - `noncesNeverDecrease`: monotonicity outside the wrap point.
  Full.
- `permit_signature_forms_equivalent`:
  - Shown: revert on expired or zero owner for both forms; the v-form's pack-then-decode round trip returns exactly (v, r, s), so a valid ECDSA signature is accepted (`permitVrsDecodesPackedSignature`); and same allowance and nonce when both succeed. The v-form is literally `permit(..., abi.encodePacked(r, s, v))` on the same code path, so these together establish the equivalence on the contract side.
  - Not proven: the bytes form, given externally supplied calldata bytes equal to `encodePacked(r, s, v)`, decodes the same words; and revert equality on the ERC-1271 path.
  - I verified the inexpressibility claim against the docs and the counterexample's bytemap (see 6). A deterministic 1271 ghost would not help (see 5).

## Non-blocking suggestions (not required for acceptance)
1. `noncesNeverDecrease`: drop the bare require and assert the explicit wrap disjunction (see 4), so the rule is assumption-free.
2. `permitSignatureFormsSameEffects`: note in the rule comment, as the commentary already does, that `requirePacked` does not constrain the bytes the contract reads under the current CVL-`bytes` model, so the rule is effectively signature-agnostic.
