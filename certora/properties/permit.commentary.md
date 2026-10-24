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

### Remaining gap (ERC-1271 path) - CLOSED in pass 4, see below
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

## Pass 4 (deterministic ERC-1271 model; probed, then applied to scene.spec at the pass-4 barrier)

Goal: close the ERC-1271 gap in `permit_signature_forms_equivalent` without editing the shared scene.spec.

### Probe files
- `certora/specs/scene-1271.spec`: a copy of scene.spec. Only the isValidSignature entry, its header comment and one ghost differ:
  ```
  ghost isValidSigG(address, bytes32) returns bytes4;
  function _.isValidSignature(bytes32 digest, bytes) external => isValidSigG(calledContract, digest) expect bytes4;
  ```
  No `bytes` value goes into CVL. The pass-2 attempt passed `bytes` into CVL (`keccak256(signature)` in a CVL function), and that is what broke the invariants.
- `certora/specs/invariants-1271-probe.spec`: identical to invariants.spec except that it imports scene-1271.spec. Conf: `certora/confs/invariants-1271-probe.conf`.
- `certora/specs/permit-1271.spec`: identical to permit.spec except for three things: it imports scene-1271.spec and invariants-1271-probe.spec, its header comment differs, and it adds three PASS 4 rules. Conf: `certora/confs/permit-1271.conf`, which is permit.conf with verify and msg changed.

### New rules (permit-1271.spec)
- `permitSignatureFormsEquivalentAnyPath` makes no assumption at all. It runs permit(v,r,s) and permit(packer.pack(v,r,s)) from one snapshot. It asserts the same revert status, the same `allowance[owner][spender]` and the same `nonces[owner]`. This covers both the ECDSA path and the 1271 path.
- `permitSignatureFormsEquivalent1271Path` makes the same assertion under `forall d. ecrecover(d,v,r,s) != owner`, so the 1271 staticcall decides in both runs. That require constrains only the uninterpreted ecrecover function.
- `permit1271PathDecidedBySignerGhost` is a model check. ECDSA is ruled out, the ghost answer for `owner` is fixed (`accept`) on every digest, and the non-signature checks pass. Then permit reverts exactly when `!accept`. This shows three things:
  - the summary is really applied to SavingsDai's low-level `owner.staticcall(...)`;
  - the `expect bytes4` encoding matches the magic-value comparison;
  - the 1271-path equivalence is therefore not passing for an unrelated reason.
- The pass-2 ECDSA-path rule `permitSignatureFormsEquivalent` is kept unchanged.

### Runs (full, unfiltered, rule_sanity basic)
- permit-1271, iter 2: https://prover.certora.com/orgs/certora/jobs/cde4dfd2-73b6-4c6f-b028-6f6b7cbc3b3c/report
  - All 10 rules VERIFIED, and every vacuity check passed. Log: "No errors found by Prover!".
  - Iter 1 had the same result before the model-check rule was added: d748b0ef-a80c-4677-bbc7-4feb24d44f21.
- invariants-1271-probe, iter 1: https://prover.certora.com/orgs/certora/jobs/175a9bd1-6698-4b2b-866b-d6087df68054/report
  - All 3 invariants VERIFIED on every method, including both permits. Log: "No errors found by Prover!".
  - None of the impossible-storage-change violations seen in pass-2 run 401dc586 appeared. The scene change is viable.

### Soundness of keying on (signer, digest)
- **Read-only callee.** The real callee is reached through `staticcall`, so it cannot change any state. Its return value depends only on the call's inputs, the global state, and gas.
- **Every outcome stays reachable.** The ghost is an arbitrary function of (signer, digest), so for any single call every bytes4 answer is possible. The summary never reverts and always returns 32 bytes. A non-magic bytes4 makes `_isValidSignature` return false, exactly as a revert or short return would. So every outcome of `_isValidSignature` is still reachable in any one execution.
- **What it over-constrains.** It forces two calls in the same rule with equal (signer, digest) to agree, even if they passed different signature bytes or the signer's state changed between them.
- **When that matters.** The digest contains `nonces[owner]`, and a successful permit increments that nonce. So two permit calls can reach the same (owner, digest) only in these cases:
  - (a) both start from the same snapshot (`at init`);
  - (b) the first call reverted;
  - (c) the nonce wrapped after 2^256 permits.
- **Grep of certora/specs** for permit callers in every spec:
  - `permit.spec` / `permit-1271.spec` use two `at init` permit calls in `permitSignatureFormsEquivalent` and the new rules (same bytes: the v-form builds `abi.encodePacked(r,s,v)` = `packer.pack(v,r,s)`), and in `permitSignatureFormsSameEffects`. That last rule uses arbitrary, possibly different `signature` bytes, but it only asserts things that hold for any ghost answers: both runs revert on an expired deadline or zero owner, and if both succeed the effects are equal. Making the answers equal only removes behaviours, and its assertions do not depend on which signature is valid. It is therefore not weakened in a way that hides a bug in the contract's handling of different bytes; the bytes-sensitivity of the decode is covered by the ECDSA-path rules.
  - `erc20-token.spec` calls permit once per parametric step (`callWithArgs`).
  - `erc4626-vault.spec` calls only `Dai.permit`, which has no ERC-1271 path.
  - `invariants.spec` and `maker-integration.spec` make single parametric calls.
  - No rule calls permit twice for the same (owner, digest) with different signatures, or with the signer's state changed in between, and then asserts something that depends on the two answers differing.
- **Trust assumptions added.**
  - The ERC-1271 answer is independent of the signature bytes and of the signer's state within one rule.
  - Gas-dependent signers (`gasleft()`) are not modelled; this is the pass-2 judge caveat.
  - A wildcard summary also gives an answer for scene contracts that have no isValidSignature. This is an over-approximation: it allows acceptance where the real call would fail, so it adds behaviours and is safe for these assertions.

### Barrier (done)
Applied: scene-1271.spec copied to scene.spec, the three rules moved into permit.spec, and the probe files (scene-1271.spec, permit-1271.spec, invariants-1271-probe.spec and their confs) deleted. Barrier runs on the new scene: permit https://prover.certora.com/orgs/certora/jobs/ea39b316-5410-46c1-97ad-52c869560d91/report (all 273 nodes VERIFIED), invariants https://prover.certora.com/orgs/certora/jobs/32094aa6-2ac4-4400-a415-4d31cf9aa9b3/report (all VERIFIED). Judge: permit.judge-pass4-round1.md, ACCEPT.

### Barrier request (as filed)
Apply the scene-1271 diff to scene.spec. Then:
- move the three PASS 4 rules into permit.spec, and update permit.spec's header comment (it still says NONDET);
- re-run every spec that imports scene.spec: invariants, permit, erc20-token, erc4626-vault, maker-integration, sanity-linked, maker-models/pot-invariants.

maker-models constructor.spec and dai-invariants.spec do not import scene.spec and need no re-run.
