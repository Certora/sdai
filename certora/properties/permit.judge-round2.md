VERDICT: ACCEPT

# Judge round 2: permit (certora/specs/permit.spec, job 2affbb9b-31e4-4932-ad68-c8f612984a40, tag permit_iter3)

All three round-1 required changes are implemented, and the recommended change is too. I re-read the spec, the harness, the conf, the commentary and the mapping from disk. I also checked `certora/logs/permit_iter3.results.txt` and the output archive `certora/logs/permit_iter3_out/TarName/Reports/treeView/rule_output_*.json`:
- every rule and invariant instance is VERIFIED;
- the 4 satisfy witnesses are satisfied;
- rule_sanity basic is clean.

## 1. Code smells: no issue
- The methods block is reduced to entries that are used. `totalSupply` and `balanceOf` now come from invariants.spec and are not duplicated.
- The new ghosts `sigHash1271` and `sigLength1271` are both read in asserts.
- No requires on type bounds, no requires that only prevent reverts, and no tautologies. Every assert compares a contract output with an independently computed expectation.

## 2. Guideline compliance: no issue
- In the bytes rule, `keccak256(signature)` is hoisted into a variable. This is legitimate: the grounding typecheck error the generator quoted (keccak256 cannot be evaluated conditionally after a quantified disjunct) is a real restriction. Because `signature` is an immutable rule parameter, hoisting changes no meaning.
- The revert rule is unchanged, and acceptable as in round 1. The commentary now gives the correct reason: the property is worded one-directionally.

## 3. Precondition validity: no issue
- `requireInvariant cachedDomainSeparatorIsEip712()` is now used in both signature rules and in the ECDSA witness. That invariant is proven, including the constructor base case. The base case now runs under invariants.spec's constructor summaries.
- No structural invariant is needed by any permit rule.

## 4. Overconstrained inputs: no issue
- The only bare requires are the four `require !called1271`. They initialise spec-only ghosts, and they are needed so that stale ghost values cannot mask a bad path. Accepted, as in round 1.
- The spec now imports invariants.spec only, as NOTES_FOR_AGENTS.md requires. It uses none of the trusted-governance invariants.
- Non-blocking note: the shared conf sets `optimistic_hashing` with `hashing_length_bound` 1024. The CVL `keccak256(signature)` in the bytes rule and in the 1271 summary is therefore subject to the optimistic length bound. This is a project-wide conf setting, not one the permit generator introduced. sDAI's signature logic depends on the length only through `== 65`, so no permit behaviour is hidden by it. A one-line mention in the commentary would be good, but it is not required.

## 5. Trivializing summaries: no issue
- The summary is still sound: a STATICCALL, an unconstrained bytes4 return, and `ALL`.
- I confirmed the call resolution in the archive for `permitRequiresOwnerSignatureVRS` and its `rule_not_vacuous` run (rule_output_28.json):
  - the call site is `signer.staticcall(abi.encodeWithSelector(IERC1271.isValidSignature.selector, digest, signature))` at SavingsDai.sol:381;
  - it resolves to `CVL/Ghost Function 'erc1271CVL(calledContract,digest,signature)'`, with the comment "callee sighash resolved; declared … to apply to all calls";
  - `callResolutionWarnings` is `[]`.
- `UNRESOLVED` and `AUTO` do not occur in the signature-rule and witness outputs. The `HAVOC` / `HAVOC DEPENDENT` strings that do occur are call-trace labels on the initial and derived state values, not call summaries. No call can havoc the 1271 ghosts.

## 6. Manifest errors: no issue
- Every assert matches EIP-2612, EIP-712 and EIP-1271.
- The nonce wrap is covered, and its witness is satisfied.

## 7. Meaningful contract interaction: no issue, improved
- `permitDigest` is now fully independent of sDAI's code:
  - the ERC-2612 typehash literal;
  - CVL abi.encode hashing of owner, spender, value, the pre-call nonce and deadline;
  - the reference EIP-712 domain for `(block.chainid via harness, sDAI)`;
  - the reference `\x19\x01` envelope.
- The signature rules therefore bind every field and the domain on their own.
- `witnessPermitViaEcdsa` shows the ECDSA comparison is reachable, so the rules are not vacuous.

## 8. Property coverage: no issue
- permit_effects_exact, permit_rejects_expired_and_zero_owner, nonces_change_only_by_permit and domain_separator_bound_to_chain: covered, as in round 1.
- permit_requires_owner_signature: now fully covered.
  - The bytes rule binds the exact bytes forwarded to the wallet (`sigHash1271 == keccak256(signature)`), in addition to the callee, the digest and the magic value.
  - The VRS rule binds the forwarded length (65). Its content is covered by the surjectivity argument, which the commentary now states correctly: every 65-byte string is `abi.encodePacked(r,s,v)` for exactly one (r, s, v), and the VRS rule is quantified over all (v, r, s).
  - `witnessPermitVia1271` shows the binding is reachable.
- The commentary corrections are both made:
  - the bytes-overload justification;
  - the revert-rule reason.

## Required changes
None.

Optional: in the commentary, note that the CVL `keccak256(signature)` is subject to the shared `optimistic_hashing` / `hashing_length_bound` 1024 setting.
