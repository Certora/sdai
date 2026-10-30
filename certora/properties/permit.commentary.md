# Permit component: commentary (generator round 2)

Spec: `certora/specs/permit.spec`. Conf: `certora/confs/permit.conf`. The conf is the base conf plus the standard overlay, with one new file, `certora/harnesses/Eip712Reference.sol`. `certora/confs/permit_tc.conf` is the same conf plus `compilation_steps_only`, used for typechecks.

## Runs
| tag | job | result |
|---|---|---|
| permit_iter1 | 26c5aa64-d48b-4570-b549-10639da31f2a | all VERIFIED (no witnesses yet) |
| permit_iter2 (round 1 final) | cb0643b9-5660-4783-a8c5-4851a0de97e2 | all VERIFIED; rejected by the judge (sig not bound, did not import invariants.spec) |
| permit_iter3 (round 2 final, unfiltered) | 2affbb9b-31e4-4932-ad68-c8f612984a40 | **all VERIFIED**: 15 rules/invariants, 38 instances of noncesChangeOnlyByPermit, 14 of cachedDomainSeparatorIsEip712, all satisfy witnesses satisfied, rule_sanity basic clean |

Report: https://app.certora.com/orgs/certora/jobs/2affbb9b-31e4-4932-ad68-c8f612984a40/report

There are no expected failures and no skipped properties.

## Setup
The spec has `import "invariants.spec";` only. That file brings the summaries, the aliases, the links and the constructor-call summaries. The base case of `cachedDomainSeparatorIsEip712` therefore runs sDAI's constructor under the shared constructor summaries; before round 2 those calls were havocked. No structural invariant is needed by any permit rule.

## Call resolution (permit_iter3)
I read the Rule Call Resolution data in the output archive (`Reports/treeView/rule_output_*.json`) for:
- `permitRequiresOwnerSignatureVRS` and `permitRequiresOwnerSignatureBytes`, including their `rule_not_vacuous` sanity runs;
- `witnessPermitVia1271` and `witnessPermitViaEcdsa`.

In each one:
- the only external call inside `SavingsDai.permit` (either overload) is `signer.staticcall(abi.encodeWithSelector(IERC1271.isValidSignature.selector, digest, signature))` at SavingsDai.sol:381;
- that call is resolved to `CVL/Ghost Function 'erc1271CVL(calledContract,digest,signature)'`;
- `callResolutionWarnings` is empty, and there is no unresolved, AUTO or HAVOC call.

Two other kinds of call need no resolution. The ecrecover precompile is modelled by the builtin ghost. The harness calls (`eip712Ref.*`, `nonces`) are made directly from CVL. So nothing can havoc the non-persistent 1271 ghosts.

## Decisions per property
- **permit_effects_exact**: `permitEffectsExact` covers both overloads through `callPermit(useVRS, ...)`. It asserts:
  - the allowance is exactly `value`;
  - the nonce is `(n+1) % 2^256`, as a mathint, with no bound on n;
  - an arbitrary other allowance pair, another nonce holder, a holder's balance and totalSupply are all unchanged.

  `witnessPermitAtMaxNonce` shows that a successful permit at nonce `max_uint256` wrapping to 0 is reachable, so the wrap is checked and not assumed away.
- **permit_rejects_expired_and_zero_owner**: `permitRejectsExpiredOrZeroOwner` covers both overloads with `@withrevert`. It asserts `expired => lastReverted` and `owner == 0 => lastReverted`. It is one-directional because the property is worded one-directionally ("permit reverts when ..."). A full `<=>` characterisation is not what the property asks for.
- **permit_requires_owner_signature**:
  - The digest is computed independently of sDAI's permit code:
    - hashStruct uses CVL `keccak256(PERMIT_TYPEHASH, owner, spender, value, nonce, deadline)`. The docs (expr.html, "Hashing") say a list of primitives is hashed as abi.encode.
    - The envelope `keccak256("\x19\x01" ++ ds ++ structHash)` needs abi.encodePacked, which CVL's keccak256 does not support. expr.html says only "a single bytes parameter" or "a list of primitive parameters" are accepted. So the envelope comes from the reference harness `Eip712Reference.digest`.
    - The domain separator is the reference `Eip712Reference.domainSeparator(chainId(), sDAI)`, not sDAI's `DOMAIN_SEPARATOR()` code. The signature rules `requireInvariant cachedDomainSeparatorIsEip712()`, a proven invariant, so sDAI's cached immutable is the deployment-chain separator and not an arbitrary value. The signature rules therefore bind the domain to EIP-712 on their own.
  - `PERMIT_TYPEHASH_ERC2612` is the ERC-2612 constant `0x6e71…26c9`, which I recomputed offline with keccak. solc folds `keccak256("Permit(...)")` into this literal in sDAI's bytecode (checked by compiling: the constant occurs in the runtime bytecode), so the Prover sees the same value.
  - `permitRequiresOwnerSignatureVRS` asserts that success implies one of two things:
    - `ecrecover(digest, v, r, s) == owner`;
    - a recorded EIP-1271 call to `owner` with exactly `digest`, with signature bytes of length 65, that returned `0x1626ba7e`.
  - `permitRequiresOwnerSignatureBytes` asserts that success implies one of two things:
    - `signature.length == 65` and SOME (v, r, s) recovers owner from the exact digest;
    - a recorded EIP-1271 call to `owner` with exactly `digest` and exactly the caller's `signature` bytes that returned the magic value. The bytes are compared as `keccak256` of the recorded bytes against `keccak256(signature)`; keccak is injective per hashing.html.
  - Why the existential ECDSA branch in the bytes rule loses nothing:
    - every 65-byte string equals `abi.encodePacked(r, s, v)` for exactly one (r: 32 bytes, s: 32 bytes, v: 1 byte);
    - both overloads run the same internal `_isValidSignature` over those memory bytes;
    - so the VRS rule, quantified over all (v, r, s), checks the exact (r, s, v) parsing for every 65-byte signature, and the bytes rule adds the exact digest and the exact forwarded bytes.
  - In the VRS rule the 1271 branch binds the forwarded length (65), but not the content. A CVL `bytes` value equal to `abi.encodePacked(r, s, v)` cannot be built, and the parsing argument above covers the content.
  - In the bytes rule, `keccak256(signature)` is hoisted into a variable before the assert. Inline, the typechecker rejects it: "The rhs ... may have side-effects (in [keccak256(signature)]) so must be evaluated only conditionally, dependent on the evaluation of the lhs ... But this lhs contains a quantified expression". The error cites docs prover/approx/grounding.html "Limitations on grounding".
  - CVL's `ecrecover` is the same ghost function as the contract's precompile call (expr.html "ECRecover"). Two things confirm this here: the VRS rule verifies, and `witnessPermitViaEcdsa` is satisfiable with the 1271 branch unused.
- **nonces_change_only_by_permit**:
  - `noncesChangeOnlyByPermit` is a parametric rule over every sDAI method except the two permits (38 instances). It asserts that an arbitrary nonce is unchanged.
  - `permitChangesOnlyOwnerNonce` asserts that a permit (either overload) changes `nonces[a]` to `(n+1) % 2^256` when `a == owner`, and leaves it unchanged otherwise. Together these give "never re-issued short of 2^256 permits".
- **domain_separator_bound_to_chain**:
  - CVL's `env` has no `chainid` field (types.html, "The env type"), so two envs with different chainids cannot be compared directly. Instead, the rule reads `block.chainid` through the harness view `Eip712Reference.chainId()`. It is unconstrained, so the rule covers every chain id.
  - The rule `domainSeparatorBoundToChain` asserts three things:
    - on the deployment chain, `DOMAIN_SEPARATOR() == _DOMAIN_SEPARATOR`, read with direct immutable access;
    - on any other chain, `DOMAIN_SEPARATOR() != _DOMAIN_SEPARATOR`;
    - on every chain, `DOMAIN_SEPARATOR() == EIP-712 separator(chainid, sDAI)`.
  - In a rule the immutable `_DOMAIN_SEPARATOR` is otherwise arbitrary. So the component-local invariant `cachedDomainSeparatorIsEip712` (`_DOMAIN_SEPARATOR == Eip712Reference.domainSeparator(deploymentChainId, sDAI)`) is proven from the constructor and required with `requireInvariant`. Distinctness then follows from the hashing model, which docs prover/approx/hashing.html describes as "injective with large gaps".
  - `witnessOtherChain` shows that the non-deployment branch is reachable.
  - The rule `domainSeparatorDiffersAcrossChains` was removed: a single rule cannot have two chain ids.

## Harness `certora/harnesses/Eip712Reference.sol` (new file, no source edits)
The harness is a pure or view reference implementation of the EIP-712 formulas, written from the standards. It has three functions:
- `domainSeparator(chainId, verifyingContract)`;
- `digest(ds, structHash)`;
- `chainId()`.

The name and version are hashed at runtime, as `keccak256(bytes(CONSTANT))`, the same way sDAI does it. This matters because the Prover does not compute real Keccak values. A literal hash constant in the spec would not equal a runtime hash of `"Savings Dai"`, and hashes are assumed never to equal code constants. I checked by compiling that solc folds only the type-hash literals, in both contracts.

## Summaries
- `function _.isValidSignature(bytes32 digest, bytes signature) external => erc1271CVL(calledContract, digest, signature) expect bytes4 ALL;`
  - The callee is an arbitrary owner address with unknown code. The summary returns an unconstrained `bytes4` and records the callee, the digest, `keccak256(signature)`, `signature.length` and the return value in ghosts.
  - Soundness: a STATICCALL cannot change state, and any return value is allowed, so this is an over-approximation of every possible owner.
  - What it does not model: a reverting callee, or a callee returning data that is not 32 bytes long. In the code both of these only make `_isValidSignature` return false. They cannot make permit succeed, so no success path is lost.
  - `ALL` makes the summary apply at every call site, so no call escapes the recording.
  - It applies to sDAI's low-level staticcall; see the Call resolution section above.
- No other new summaries. The imports bring the shared rpow summary and links.

## Every bare `require`
- `require !called1271` appears in `permitRequiresOwnerSignatureVRS`, `permitRequiresOwnerSignatureBytes`, `witnessPermitViaEcdsa` and `witnessPermitVia1271`. It initialises spec-only ghost bookkeeping: no EIP-1271 call has been recorded yet in the rule. It constrains no contract state.
- There are no other bare requires. The only `requireInvariant` is of the local, proven `cachedDomainSeparatorIsEip712`. No structural invariant or trusted-governance assumption from invariants.spec is used.

## Structural-invariant requests
None.
- Note (judge round 2): the conf's optimistic_hashing with hashing_length_bound 1024 means CVL keccak256(signature) covers signatures up to 1024 bytes; sDAI's logic depends on signature length only via == 65, so no permit behaviour is hidden.
