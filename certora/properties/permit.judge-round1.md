VERDICT: REJECT

# Judge round 1: permit (certora/specs/permit.spec, job cb0643b9-5660-4783-a8c5-4851a0de97e2)

The core of the spec is sound and much of it is good:
- The digest is computed independently and compared with permit's inline digest.
- The EIP-1271 summary is a sound over-approximation, and the witnesses prove it fires.
- The nonce wrap is exercised, not assumed away.

The rejection is for two reasons:
1. A coverage gap: the `sig` argument passed to `isValidSignature` is never bound.
2. Non-conformance with the shared setup: the spec does not import invariants.spec.

There are also two corrections to the commentary.

The docs claims, checked against docs.certora.com:
- `expr.html` "Hashing": CVL `keccak256` accepts only "a single bytes parameter" or "a list of primitive parameters", and the list form replicates `keccak256(abi.encode(...))`. There is no way to build an `abi.encodePacked("\x19\x01", ds, h)` bytes value in CVL. Confirmed, so the `digest` harness is needed.
- `types.html` "The env type": the fields are msg.sender, msg.value, block.{number, timestamp, basefee, coinbase, difficulty, gaslimit} and tx.origin, and "the remaining solidity global variables are not accessible from CVL". There is no chainid. Confirmed, so the `chainId()` harness view is needed.
- `prover/approx/hashing.html`: Keccak is modelled as "an arbitrary function that is injective with large gaps", and hashes never collide with constants in the code. This justifies the "other chain ⇒ different separator" step, and the matching of CVL `keccak256(typehash, …)` with the contract's bounded `hash(abi.encode(…))`. The match is also confirmed empirically, because the VRS rule verifies and `witnessPermitViaEcdsa` is satisfiable.
- `expr.html` "ECRecover": CVL's `ecrecover` is a ghost function, it is "equivalent to" the Solidity call, and it may be used under quantifiers. This confirms the `exists v r s. ecrecover(...)` in the bytes rule.
- `methods.html`: wildcard entries default to UNRESOLVED, so `ALL` is correct here. Unresolved calls get AUTO / HAVOC summaries, which havoc non-persistent ghosts. This is relevant to item 1 of the required changes.

## 1. Code smells: no issue
- No requires on type bounds, and no requires that only prevent reverts.
- Every methods-block entry is used:
  - the envfree entries are read by the rules;
  - the `isValidSignature` entry is the recording summary.
- No asserts are tautological:
  - every assert compares a contract output (allowance, nonces, the permit-internal digest seen through `ecrecover` and the 1271 ghosts, `DOMAIN_SEPARATOR()`) with an expectation computed independently;
  - `Eip712Reference` is the EIP-712 formula. The only things it shares with sDAI are the domain name/version strings, which are the specified domain values, not implementation logic. This falls under the "independently-computed expectation" carve-out.

## 2. Guideline compliance: no blocking issue
- All 23 guidelines are respected:
  - mathint is used for the nonce arithmetic, with `% 2^256` and `^` used correctly as exponentiation;
  - `lastReverted` is captured immediately after the `@withrevert` call, and `expired` is computed before it;
  - the wildcard summary has `expect bytes4`;
  - `method` is declared as a rule parameter;
  - the CVL function ends with `return`.
- `permitRejectsExpiredOrZeroOwner` is a single rule, implication-only. The property is worded one-directionally ("permit reverts when …"), so a `<=>` characterisation is not required by criterion 8. The rule contains no bare `require`, so nothing truncates it. This is acceptable.
- One correction to the commentary's reason for not writing `<=>`: the reason is NOT inexpressibility. For the VRS overload, the revert condition is fully stateable with the 1271 ghosts:
  `lastReverted <=> expired || owner == 0 || e.msg.value != 0 || !(ecrecover(digest,v,r,s) == owner || ret1271 == MAGIC)`.
  This is optional. Do not block on it.

## 3. Precondition validity: no issue
- No rule depends on a structural state invariant:
  - permit touches only `nonces[owner]` and `allowance[owner][spender]`;
  - the domain rule uses `requireInvariant cachedDomainSeparatorIsEip712`, which is proven.
- Spurious start states with an arbitrary `_DOMAIN_SEPARATOR` are harmless in the signature rules. `permitDigest` reads the same `DOMAIN_SEPARATOR()` that permit inlines, and the separator is tied to EIP-712 by the domain rule. The composition is valid. A recommended (non-blocking) alternative is under Required changes.
- `cachedDomainSeparatorIsEip712` base case: without invariants.spec, the constructor's `daiJoin.vat()`, `daiJoin.dai()`, `vat.hope` and `dai.approve` calls are unresolved and havoc. That does not make the base case unsound:
  - `deploymentChainId` and `_DOMAIN_SEPARATOR` are immutables computed from `block.chainid`, `address(this)` and constant strings;
  - none of these depends on the havocked return values or storage.

  It is still not the shared, faithful constructor model (see criterion 4 and required change 1).

## 4. Overconstrained inputs: no issue with the requires; one setup non-conformance
- I checked every bare `require`. There are four occurrences of `require !called1271`: the VRS and bytes signature rules and two witnesses.
  - They constrain spec-only bookkeeping, not contract state.
  - They are necessary: non-persistent ghosts start unconstrained, so a stale `called1271/callee1271/digest1271/ret1271` could otherwise satisfy the disjunct and MASK a bad success path.
  - Accepted.
- There are no other requires, preserved blocks, or trusted-governance assumptions.
- Non-conformance: certora/NOTES_FOR_AGENTS.md says component specs must `import "invariants.spec";` ONLY, and must not import the summaries or the call-resolution file again. invariants.spec is now importable and proven (job 1080ee77-…). permit.spec still imports `SavingsDai_call_resolution.spec` directly. This must be fixed (required change 1):
  - for consistency with the shared setup and the alias/link definitions;
  - so that the local invariant's constructor base case runs under the shared constructor summaries rather than havoc.

## 5. Trivializing summaries: no issue (with one confirmation required)
`_.isValidSignature(bytes32, bytes) => erc1271CVL(calledContract, digest) expect bytes4 ALL` is sound:
- the call is a STATICCALL, so the callee cannot change state;
- the return value is unconstrained, so it over-approximates every owner code, including EOAs, which really return empty data and therefore `false`. That over-approximation is harmless for "success ⇒ condition" rules;
- callee reverts and wrong-length returns make `_isValidSignature` return false, so dropping them loses no success path.

The unconstrained return does not trivialise the rule. The assert still requires that:
- the call went to `owner`;
- the call carried exactly the independent digest;
- the answer was exactly `0x1626ba7e`.

So a wrong callee, a wrong or stale digest, a wrong magic constant, or ignoring the result would all be caught. `witnessPermitVia1271` being satisfied proves that the summary is applied to the low-level `staticcall(abi.encodeWithSelector(...))`.

Residual concern: the 1271 ghosts are non-persistent. If any call inside permit were left unresolved, its HAVOC would havoc these ghosts and could spuriously satisfy the 1271 disjunct. The witness shows the summary fires on at least one path, but the commentary should state, from the report's Rule Call Resolution panel, that the permit rules have no unresolved or havocked calls (required change 1).

## 6. Manifest errors: no issue
- Every assert matches the obviously-correct behaviour of EIP-2612, EIP-712 and EIP-1271:
  - the old nonce goes into the digest;
  - the nonce increments by +1 mod 2^256;
  - the separator is cached only on the deployment chain.
- The nonce wrap is handled correctly. `(nonceBefore + 1) % 2^256` is computed in mathint with no bound on the nonce, and `witnessPermitAtMaxNonce` shows that `max_uint256 → 0` is reachable on a successful permit. Nothing is hidden.

## 7. Meaningful contract interaction: no issue
- The digest is built from:
  - CVL `keccak256(PERMIT_TYPEHASH_ERC2612, owner, spender, value, nonces(owner) [pre-call], deadline)`, where the typehash is the standard ERC-2612 literal, not read from sDAI;
  - plus `Eip712Reference.digest`, which is the EIP-712 `\x19\x01` envelope.
- The digest therefore binds owner, spender, value, the pre-call nonce and deadline. By injectivity, any permuted, missing or stale field in sDAI's inline computation gives a different digest, and the uninterpreted `ecrecover` / `digest1271` comparison fails. The domain is bound through `DOMAIN_SEPARATOR(e)`, and `domainSeparatorBoundToChain` proves it equals `Eip712Reference.domainSeparator(block.chainid, sDAI)` on every chain.
- The harness is a standards reference, not a copy of permit:
  - it does not call sDAI;
  - its only shared constants are the domain strings, which are the specified values.

  This is acceptable.
- All the other rules assert on contract reads.

## 8. Property coverage: one gap
- permit_effects_exact: covered by `permitEffectsExact` (both overloads) and `witnessPermitAtMaxNonce`.
- permit_rejects_expired_and_zero_owner: covered by `permitRejectsExpiredOrZeroOwner` (both overloads, `@withrevert`). One direction, as the property is worded.
- permit_requires_owner_signature: PARTIAL. The property says "owner's `isValidSignature(digest, sig)` returns the magic value". The spec binds the callee, the digest and the return value, but never `sig`. A contract that forwards a different or truncated byte string to the wallet would pass both signature rules. This IS expressible:
  - a summary's `bytes` parameter can be passed to the CVL function;
  - `keccak256` accepts "a single bytes parameter" (`expr.html` "Hashing"), so the summary can record `keccak256(signature)` and `signature.length` in ghosts.

  The bytes-overload weakening is accepted on the substance, but the commentary's reason is wrong and must change:
  - The commentary claims that "CVL cannot read the bytes". That overstates it: a harness view that splits a 65-byte `bytes` into (r, s, v) could be called from CVL.
  - The weakening is valid for another reason. Every 65-byte string equals `abi.encodePacked(r, s, v)` for exactly one (r: 32 bytes, s: 32 bytes, v: 1 byte), and both overloads run the same internal `_isValidSignature` over memory bytes.
  - So `permitRequiresOwnerSignatureVRS`, quantified over all (v, r, s), already checks the exact parsing for every 65-byte signature. Together with the bytes rule's exact digest check, the conjunction covers the property.
  - The commentary must state this surjectivity argument instead of the inexpressibility claim.
- nonces_change_only_by_permit: covered by `noncesChangeOnlyByPermit` (all 38 non-permit sDAI methods, with `parametric_contracts` = SavingsDai, matching "every sDAI method") and `permitChangesOnlyOwnerNonce`.
- domain_separator_bound_to_chain: covered by `cachedDomainSeparatorIsEip712`, `domainSeparatorBoundToChain` and `witnessOtherChain`. The chainid inexpressibility in env is confirmed in the docs. Reading `block.chainid` through a harness view in the same rule is a correct substitute for comparing two envs. Assert 3 implies the separator is a function of the chain id, and injectivity gives distinctness across chains.

## Required changes
1. **Shared setup.**
   - Replace the three direct imports with `import "invariants.spec";`, as NOTES_FOR_AGENTS.md requires.
   - Remove the now-duplicate `totalSupply()` and `balanceOf(address)` envfree entries.
   - Keep using the `savingsDai` alias, which invariants.spec inlines, and do not redeclare it.
   - Re-run the full, unfiltered conf with rule_sanity basic.
   - In the commentary, delete the "Import deviation" section. Instead, state that `cachedDomainSeparatorIsEip712`'s base case now runs under the shared constructor summaries.
   - From the new report's Rule Call Resolution panel, confirm that in `permitRequiresOwnerSignatureVRS` and `permitRequiresOwnerSignatureBytes` the only external call in permit is the summarized `isValidSignature` (plus the ecrecover precompile), with no unresolved or havocked call that could havoc the non-persistent 1271 ghosts.
2. **Bind `sig` in the EIP-1271 branch (criterion 8).**
   - Pass `signature` into `erc1271CVL` and record `keccak256(signature)` and `signature.length` in ghosts.
   - In `permitRequiresOwnerSignatureBytes`, add to the 1271 disjunct the conjunct that the recorded hash equals `keccak256(signature)`.
   - In `permitRequiresOwnerSignatureVRS`, add the conjunct that the recorded length is 65. A CVL `bytes` value equal to `abi.encodePacked(r,s,v)` cannot be built in CVL, and the length plus the parsing argument in item 3 suffices.
   - If passing `bytes` into the CVL summary function or hashing it does not typecheck, report the exact error and the docs section, rather than silently dropping the binding.
3. **Commentary correction (criterion 8).**
   - Replace "CVL cannot read the bytes of `signature`" as the justification for the bytes-overload weakening. Use the surjectivity argument: every 65-byte string is `abi.encodePacked(r, s, v)` for a unique (r, s, v), so the VRS rule covers the parsing for all 65-byte signatures, and the bytes rule covers the exact digest.
   - In the revert section, drop the claim that `<=>` is inexpressible. Say instead that the property is one-directional.

Recommended, not blocking: in `permitDigest`, use `eip712Ref.domainSeparator(eip712Ref.chainId(e), savingsDai)` together with `requireInvariant cachedDomainSeparatorIsEip712()` instead of sDAI's own `DOMAIN_SEPARATOR(e)`. The signature rules would then bind the domain to EIP-712 on their own, without composing with the domain rule.
