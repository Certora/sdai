> **Pass-1 sections below are SUPERSEDED by the "Pass 2" section**: permitSignatureFormsEquivalent now VERIFIES (SigPacker), and noncesNeverDecrease no longer has a bare require.

# permit: commentary

Final full unfiltered run (iter 4): https://prover.certora.com/orgs/certora/jobs/53186bb4-9791-40ae-a464-965924ea4e01/report
Six of seven rules VERIFIED with rule_sanity basic (every vacuity check passed). `permitSignatureFormsEquivalent` is VIOLATED, expected (prover limitation, see below).

Earlier runs: iter 1 `e5d74496-0be2-43d4-87c7-f7820535d9c2` (full; same picture without the decode rule), iter 2 `c220b675-2786-4387-9ff0-df214202f235` (equivalence only, with precise_bitwise_ops, still violated), iter 3 `7432c203-120b-4f8b-a186-f445d9370458` (decode rule only, verified).

## Conf
- `certora/confs/permit.conf` = invariants.conf with verify/msg changed, plus `"precise_bitwise_ops": true`. `_isValidSignature` decodes v with `byte(0, mload(...))`, and the decode rule depends on that bitwise op being modelled exactly. No loop_iter change was needed: the prover replaced the signature memory copies with bulk "Copy-Loop" steps, and the sanity checks passed for every rule.

## Signature model and trust assumptions
- The prover models `ecrecover` as a deterministic uninterpreted ghost function (docs cvl/expr.html, "ECRecover"). The CVL builtin `ecrecover` is the same function. I did not add the docs' optional ecrecover axioms; no rule needed them.
- `_.isValidSignature` is NONDET (scene.spec): each ERC-1271 staticcall returns a fresh arbitrary value. This is sound for single-execution properties. It cannot express that two executions with the same input get the same answer, which matters for the two-run equivalence (see below).
- No rule assumes a particular signature is valid. Effects rules state their conclusions under `!reverted`.

## Rules
- `permitRevertsOnExpiredOrZeroOwner`: one rule covers both entry points, using the `bytesForm` switch in `callPermitWithRevert`. It asserts `(timestamp > deadline || owner == 0) => reverted` and has no preconditions.
- `permitEffects` (both forms): after success, `allowance[owner][spender] == value` and `nonces[owner] == (before + 1) mod 2^256`, which is exactly what the unchecked `nonces[owner]++` does and equals +1 whenever before < max_uint256. In all cases, reverted or not, no other allowance pair, no other owner's nonce, no balance and not totalSupply change. The only requires make the "other" addresses actually different from the permit's own.
- `noncesNeverDecrease` (parametric over all SavingsDai methods): this rule has the one bare require, `nonceBefore < max_uint256`. Justification: every nonce starts at 0, and the only write is the unchecked `nonces[owner]++` in permit, which `permitEffects` and `nonceChangesOnlyViaPermit` prove advances it by exactly one, with no assumptions. Reaching max_uint256 therefore takes 2^256 - 1 successful permits for one owner, which is infeasible. At that single unreachable value the increment wraps to 0, a "decrease". This is not reachable in practice, so it is a limitation entry, not a finding. No inductive invariant can exclude it, because the state max-1 is itself reachable in principle.
- `nonceChangesOnlyViaPermit` (parametric): any nonce change implies f is one of the two permit selectors and the change is +1 mod 2^256. It has no requires. Combined with `permitEffects` (no other owner's nonce changes), only a successful permit for that owner moves a nonce.
- Equivalence of the two signature forms, three rules:
  - `permitSignatureFormsEquivalent`: this is the literal statement. CVL has no `abi.encodePacked`, but it does allow indexing `bytes` (elements are bytes1, and this typechecks). `requirePacked` pins the 65 bytes exactly (r big-endian, s, v) using division/modulo byte extraction. Both forms then run from `storage init` under the ECDSA-accepts assumption `forall d. ecrecover(d, v, r, s) == owner`, and the rule asserts revert-equality and equal allowance and nonce. It is EXPECTED TO FAIL: prover limitation. In the counterexamples (runs 1, 2, 4), the CVL `bytes` value is modelled as a map from byte offset to 32-byte word, and the map is not coherent across offsets. In run 4, sWord = 0xd and byte 63 = 0x0d, yet the word mloaded at offset 0x20 is 0xc. So the bytes form decodes a different s, ecrecover misses owner, the NONDET ERC-1271 call fails, and only the bytes form reverts. This is not contract behaviour, and precise_bitwise_ops does not change it.
  - `permitVrsDecodesPackedSignature`, the sound replacement. permit(v,r,s) is literally `permit(..., abi.encodePacked(r, s, v))`, so the only thing that can make the forms differ is the pack/decode round trip. Under `forall d. ecrecover(d, v, r, s) == owner` (an assumption on the ecrecover ghost only, needed because the digest cannot be recomputed in CVL: it includes the packed "\x19\x01" prefix), and with deadline, owner and msg.value checks passing, permit(v,r,s) must not revert. If the decode produced anything other than (v, r, s), ecrecover would be evaluated at an unconstrained point and the NONDET 1271 fallback could revert, so the rule would fail. VERIFIED.
  - `permitSignatureFormsSameEffects`: from one pre-state, both forms revert when the deadline has passed or owner is 0, and when both succeed they leave the same allowance and nonce. Because of the limitation above, the `requirePacked` constraint in this rule does not actually tie the bytes to (r, s, v). The assertions hold for every signature, so the rule stays sound and is not vacuous (the sanity check passed).
- Coverage gap: the claim "same revert behaviour when the ERC-1271 path decides" is not proven. In reality both forms pass the same bytes to the same view function in the same state, so they get the same answer. Under the NONDET scene summary the two calls are independent. See the request below.

## Requests (scene)
- Optional: replace the NONDET summary of `_.isValidSignature(bytes32, bytes)` with a deterministic one, for example a ghost function `isValidSigG(calledContract, digest, keccak256(signature))` returning bytes4 (`expect bytes4`). This stays sound, because a staticcall to view code with the same input in the same state is deterministic, and it would make ERC-1271-path equivalence expressible across two executions. It would still not fix the CVL `bytes` construction limitation. A harness exposing `abi.encodePacked(r, s, v)` would, but that is outside this component's deliverables.
- No new structural invariants needed.

## Pass 2

Final full unfiltered run (pass 2 iter 1): https://prover.certora.com/orgs/certora/jobs/ef8a20e2-fa1f-45a5-be68-69418ccd96fb/report
All seven rules VERIFIED with rule_sanity basic ("No errors found by Prover!"). There are no expected failures any more.

### Changes
- `using SigPacker as packer;` was added, with `SigPacker.pack(uint8, bytes32, bytes32)` declared envfree. There is no alias clash: invariants.spec declares only `pot`, and scene.spec declares no aliases.
- `permitSignatureFormsEquivalent` was rewritten and now VERIFIES. It replaces the pass-1 expected-fail version that used CVL byte-indexed `bytes`.
  - The packed signature is now `packed = packer.pack(v, r, s)`. SigPacker computes `abi.encodePacked(r, s, v)` in Solidity, and the result is returned into CVL and passed to `permit(owner, spender, value, deadline, packed)`. Bytes returned from a contract and passed back stay coherent: the bytes form decodes exactly (v, r, s). So the pass-1 limitation, which came from building the 65 bytes element by element in CVL, does not bite on this route. `requirePacked` is no longer used by this rule.
  - From the same `storage init`, the rule runs permit(v, r, s) and permit(bytes). It asserts identical revert status, identical `allowance[owner][spender]` and identical `nonces[owner]`.
  - Assumption: `forall bytes32 d. ecrecover(d, v, r, s) == owner`. This is the same assumption as in pass 1's `permitVrsDecodesPackedSignature`, and it constrains only the uninterpreted ecrecover function.
    - It is non-vacuous: the sanity check passed.
    - It is non-trivialising. If either form decoded anything other than (v, r, s), ecrecover there would be unconstrained, the call would reach the NONDET `isValidSignature` staticcall, and the two runs could disagree.
    - Every digest is quantified because the digest (with the "\x19\x01" prefix) cannot be recomputed in CVL.
- `noncesNeverDecrease` now has no precondition. The bare `require nonceBefore < max_uint256` was removed, and the assertion is `nonces(holder) >= nonceBefore || (nonceBefore == max_uint256 && nonces(holder) == 0)`. It permits exactly the wrap of the unchecked `nonces[owner]++`, nothing else (judge suggestion 1).
- `permitVrsDecodesPackedSignature` and `permitSignatureFormsSameEffects` are unchanged. The second still uses `requirePacked`. As the judge noted, under the CVL-`bytes` model that constraint does not tie the bytes the contract reads to (r, s, v), so the rule is effectively signature-agnostic: both forms revert on an expired deadline or a zero owner, and they have the same effects when both succeed.

### Remaining gap (ERC-1271 path)
- Equivalence is proven when ECDSA decides, that is when ecrecover(digest, v, r, s) == owner.
- When it does not, both forms reach `owner.staticcall(isValidSignature(digest, packed))`. In the real EVM, the two calls are identical: same state (the nonce is incremented before the call in both forms), same digest, same bytes, and a view callee. So they return the same answer.
- In the scene, `_.isValidSignature` is NONDET, so the two executions get independent answers, and equivalence of the revert status cannot be stated there. A deterministic ghost was tried at scene level and reverted (scene.spec note, invariants run 401dc586).
- What is still proven on that path:
  - When both forms succeed, they produce identical effects (`permitSignatureFormsSameEffects`, `permitEffects`).
  - Both forms revert on an expired deadline or a zero owner.
  - The v-form is literally `permit(..., abi.encodePacked(r, s, v))`, so its 1271 call receives exactly the bytes the bytes form would receive.

### Trust assumptions (pass 2)
- ecrecover is the prover's deterministic uninterpreted function. Two rules use the ECDSA-accepts quantifier over digests: the equivalence rule and the decode rule.
- `isValidSignature` is NONDET (scene).
- No other bare requires remain, except the ones in `permitEffects` that define "other" addresses.

### Pass 2 judge note
ERC-1271 gap caveat: even in the real EVM the two entry points reach the isValidSignature staticcall with different gas remaining, so a gas-dependent signer could answer differently; equivalence on the 1271 path is therefore only expected modulo gas-dependent signers. Judge pass 2 round 1: ACCEPT (permit.judge-pass2-round1.md).
