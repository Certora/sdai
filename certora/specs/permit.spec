// Permit component of Savings Dai (sDAI): EIP-2612 permit (both overloads), nonces and the EIP-712 domain.
// Property list: certora/properties/permit.properties.json. Commentary: certora/properties/permit.commentary.md.
import "invariants.spec";

using Eip712Reference as eip712Ref;

methods {
    function nonces(address) external returns (uint256) envfree;
    function allowance(address, address) external returns (uint256) envfree;
    function deploymentChainId() external returns (uint256) envfree;

    // Independent reference implementation of the EIP-712 formulas (certora/harnesses/Eip712Reference.sol).
    function Eip712Reference.domainSeparator(uint256, address) external returns (bytes32) envfree;
    function Eip712Reference.digest(bytes32, bytes32) external returns (bytes32) envfree;

    // EIP-1271 check: sDAI does `owner.staticcall(isValidSignature(digest, signature))`. The owner is an
    // arbitrary address, so its code is unknown. The summary returns an ARBITRARY bytes4 (sound for any
    // owner code: a staticcall cannot change state, and any return value is allowed) and records the call in
    // ghosts so that rules can see who was asked, about which digest and signature bytes, and what was answered.
    // ALL: applied to every call site, so no call escapes the recording (more return values than a concrete
    // callee could produce is an over-approximation, hence still sound for every rule below).
    function _.isValidSignature(bytes32 digest, bytes signature) external
        => erc1271CVL(calledContract, digest, signature) expect bytes4 ALL;
}

// ---------------------------------------------------------------------------------------------------------
// Constants (from the EIP-712 / ERC-2612 standards; checked with keccak offline, see commentary).
// solc folds keccak256 of a string literal into this literal in sDAI's bytecode, so the Prover sees the
// same 32-byte constant in the contract.
// ---------------------------------------------------------------------------------------------------------
definition PERMIT_TYPEHASH_ERC2612() returns bytes32 =
    to_bytes32(0x6e71edae12b1b97f4d1f60370fef10105fa2faae0126114a169c64845d6126c9);
// bytes4(keccak256("isValidSignature(bytes32,bytes)")), the EIP-1271 magic value.
definition ERC1271_MAGIC() returns bytes4 = to_bytes4(0x1626ba7e);

definition isPermit(method f) returns bool =
    f.selector == sig:permit(address, address, uint256, uint256, bytes).selector
    || f.selector == sig:permit(address, address, uint256, uint256, uint8, bytes32, bytes32).selector;

// ---------------------------------------------------------------------------------------------------------
// EIP-1271 call recording.
// ---------------------------------------------------------------------------------------------------------
ghost bool called1271;
ghost address callee1271;
ghost bytes32 digest1271;
ghost bytes4 ret1271;
ghost bytes32 sigHash1271;   // keccak256 of the signature bytes passed to isValidSignature
ghost uint256 sigLength1271; // their length

function erc1271CVL(address callee, bytes32 digest, bytes signature) returns bytes4 {
    bytes4 ret;     // unconstrained: the owner's isValidSignature may answer anything
    called1271 = true;
    callee1271 = callee;
    digest1271 = digest;
    ret1271 = ret;
    sigHash1271 = keccak256(signature);
    sigLength1271 = signature.length;
    return ret;
}

// ERC-2612 permit digest, computed independently of sDAI's permit code: hashStruct(Permit) in CVL
// (keccak256 of a list of primitives = keccak256(abi.encode(...)), expr.html "Hashing"), and the EIP-712
// envelope "\x19\x01" ++ domainSeparator ++ structHash via the reference harness. The domain separator is
// the EIP-712 reference separator for the current chain id and sDAI's address (not sDAI's DOMAIN_SEPARATOR
// code); rules using this function requireInvariant cachedDomainSeparatorIsEip712, so that sDAI's cached
// immutable is the deployment-chain separator rather than an arbitrary value.
function permitDigest(env e, address owner, address spender, uint256 value, uint256 nonce, uint256 deadline)
    returns bytes32
{
    bytes32 structHash = keccak256(PERMIT_TYPEHASH_ERC2612(), owner, spender, value, nonce, deadline);
    return eip712Ref.digest(eip712Ref.domainSeparator(eip712Ref.chainId(e), savingsDai), structHash);
}

// Calls one of the two permit overloads (the (v,r,s) one forwards to the bytes one with abi.encodePacked(r,s,v)).
function callPermit(env e, bool useVRS, address owner, address spender, uint256 value, uint256 deadline,
                    bytes signature, uint8 v, bytes32 r, bytes32 s) {
    if (useVRS) {
        permit(e, owner, spender, value, deadline, v, r, s);
    } else {
        permit(e, owner, spender, value, deadline, signature);
    }
}

// =========================================================================================================
// permit_effects_exact
// =========================================================================================================
rule permitEffectsExact(env e, bool useVRS, address owner, address spender, uint256 value, uint256 deadline,
                        bytes signature, uint8 v, bytes32 r, bytes32 s,
                        address otherOwner, address otherSpender, address otherNonceHolder, address holder) {
    mathint nonceBefore = nonces(owner);
    uint256 otherAllowanceBefore = allowance(otherOwner, otherSpender);
    uint256 otherNonceBefore = nonces(otherNonceHolder);
    uint256 balanceBefore = balanceOf(holder);
    uint256 supplyBefore = totalSupply();

    callPermit(e, useVRS, owner, spender, value, deadline, signature, v, r, s);

    assert allowance(owner, spender) == value, "permit sets allowance[owner][spender] = value";
    assert to_mathint(nonces(owner)) == (nonceBefore + 1) % 2^256, "owner's nonce goes from n to n+1 mod 2^256";
    assert (otherOwner != owner || otherSpender != spender)
        => allowance(otherOwner, otherSpender) == otherAllowanceBefore, "no other allowance changes";
    assert otherNonceHolder != owner => nonces(otherNonceHolder) == otherNonceBefore, "no other nonce changes";
    assert balanceOf(holder) == balanceBefore, "no balance changes";
    assert totalSupply() == supplyBefore, "totalSupply does not change";
}

// =========================================================================================================
// permit_rejects_expired_and_zero_owner
// =========================================================================================================
rule permitRejectsExpiredOrZeroOwner(env e, bool useVRS, address owner, address spender, uint256 value,
                                     uint256 deadline, bytes signature, uint8 v, bytes32 r, bytes32 s) {
    bool expired = e.block.timestamp > deadline;
    if (useVRS) {
        permit@withrevert(e, owner, spender, value, deadline, v, r, s);
    } else {
        permit@withrevert(e, owner, spender, value, deadline, signature);
    }
    bool reverted = lastReverted;

    assert expired => reverted, "permit reverts after the deadline";
    assert owner == 0 => reverted, "permit reverts for the zero owner";
}

// =========================================================================================================
// permit_requires_owner_signature
// =========================================================================================================
// (v, r, s) overload: the signature bytes are abi.encodePacked(r, s, v), 65 bytes, so the ECDSA branch must
// be exactly ecrecover(digest, v, r, s).
rule permitRequiresOwnerSignatureVRS(env e, address owner, address spender, uint256 value, uint256 deadline,
                                     uint8 v, bytes32 r, bytes32 s) {
    // Ghost bookkeeping, not a protocol assumption: "no EIP-1271 call has been recorded yet in this rule".
    require !called1271, "fresh recording before the call under test";
    requireInvariant cachedDomainSeparatorIsEip712();
    bytes32 digest = permitDigest(e, owner, spender, value, nonces(owner), deadline);

    permit(e, owner, spender, value, deadline, v, r, s);

    // The bytes sent to the wallet are abi.encodePacked(r, s, v); a CVL bytes value with that content cannot be
    // built, so the 1271 branch binds their length (65). Content is covered by the parsing argument in the
    // commentary (every 65-byte string is abi.encodePacked(r, s, v) for exactly one (r, s, v)).
    assert ecrecover(digest, v, r, s) == owner
        || (called1271 && callee1271 == owner && digest1271 == digest && ret1271 == ERC1271_MAGIC()
            && sigLength1271 == 65),
        "permit succeeded without an ECDSA signature by owner or an EIP-1271 approval by owner of the digest";
}

// bytes overload: the ECDSA branch is stated as "signature has 65 bytes and SOME (v, r, s) recovers owner from
// the exact EIP-712 digest". This loses nothing: every 65-byte string is abi.encodePacked(r, s, v) for exactly
// one (r, s, v), and both overloads run the same _isValidSignature over those memory bytes, so the rule above,
// quantified over all (v, r, s), checks the exact (r, s, v) parsing for every 65-byte signature. The 1271
// branch binds the exact bytes forwarded to the wallet (keccak256 of them, injective per hashing.html).
rule permitRequiresOwnerSignatureBytes(env e, address owner, address spender, uint256 value, uint256 deadline,
                                       bytes signature) {
    // Ghost bookkeeping, not a protocol assumption: "no EIP-1271 call has been recorded yet in this rule".
    require !called1271, "fresh recording before the call under test";
    requireInvariant cachedDomainSeparatorIsEip712();
    bytes32 digest = permitDigest(e, owner, spender, value, nonces(owner), deadline);

    permit(e, owner, spender, value, deadline, signature);

    // Hoisted: keccak256 may not be evaluated conditionally after a quantified disjunct (grounding.html).
    bytes32 sigHash = keccak256(signature);
    assert (signature.length == 65
            && (exists uint8 v. exists bytes32 r. exists bytes32 s. ecrecover(digest, v, r, s) == owner))
        || (called1271 && callee1271 == owner && digest1271 == digest && ret1271 == ERC1271_MAGIC()
            && sigHash1271 == sigHash),
        "permit succeeded without an ECDSA signature by owner or an EIP-1271 approval by owner of the digest";
}

// =========================================================================================================
// nonces_change_only_by_permit
// =========================================================================================================
// Every sDAI method other than the two permits leaves every nonce unchanged.
rule noncesChangeOnlyByPermit(env e, method f, calldataarg args, address a) filtered { f -> !isPermit(f) } {
    uint256 before = nonces(a);
    f(e, args);
    assert nonces(a) == before, "only permit changes nonces";
}

// A permit changes only its owner's nonce, by exactly +1 mod 2^256 (so a consumed nonce is never re-issued
// before 2^256 permits by that owner).
rule permitChangesOnlyOwnerNonce(env e, bool useVRS, address owner, address spender, uint256 value,
                                 uint256 deadline, bytes signature, uint8 v, bytes32 r, bytes32 s, address a) {
    mathint before = nonces(a);
    callPermit(e, useVRS, owner, spender, value, deadline, signature, v, r, s);
    assert to_mathint(nonces(a)) == (a == owner ? (before + 1) % 2^256 : before),
        "permit increments exactly its owner's nonce";
}

// =========================================================================================================
// domain_separator_bound_to_chain
// =========================================================================================================
// Component-local invariant (immutables only, so preservation is trivial; the base case runs sDAI's
// constructor): the cached separator is the EIP-712 separator of the deployment chain and sDAI's address.
invariant cachedDomainSeparatorIsEip712()
    savingsDai._DOMAIN_SEPARATOR == eip712Ref.domainSeparator(savingsDai.deploymentChainId, savingsDai);

// CVL's env has no chainid field (docs cvl/types.html "The env type"), so the chain id is read with the
// harness view eip712Ref.chainId(); the Prover gives block.chainid one unconstrained value per rule, so the
// rule covers every chain id, the deployment one and every other one.
rule domainSeparatorBoundToChain(env e) {
    requireInvariant cachedDomainSeparatorIsEip712();
    uint256 chainId = eip712Ref.chainId(e);
    bytes32 ds = DOMAIN_SEPARATOR(e);

    assert chainId == deploymentChainId() => ds == savingsDai._DOMAIN_SEPARATOR,
        "on the deployment chain the cached separator is returned";
    assert chainId != deploymentChainId() => ds != savingsDai._DOMAIN_SEPARATOR,
        "on any other chain the separator differs from the cached one";
    assert ds == eip712Ref.domainSeparator(chainId, savingsDai),
        "the separator is the EIP-712 separator for the current chain id and sDAI's address";
}

// =========================================================================================================
// Reachability witnesses (satisfy): the premises of the implications above are reachable, so the VERIFIED
// results are not vacuous in the cases that matter. rule_sanity "basic" only checks that each rule has
// SOME path; these show the specific paths.
// =========================================================================================================
// A permit can succeed through the ECDSA branch (CVL's ecrecover is the one the contract's precompile call
// uses) without any EIP-1271 call.
rule witnessPermitViaEcdsa(env e, address owner, address spender, uint256 value, uint256 deadline,
                           uint8 v, bytes32 r, bytes32 s) {
    require !called1271, "fresh recording before the call under test";
    requireInvariant cachedDomainSeparatorIsEip712();
    bytes32 digest = permitDigest(e, owner, spender, value, nonces(owner), deadline);
    permit(e, owner, spender, value, deadline, v, r, s);
    satisfy ecrecover(digest, v, r, s) == owner && !called1271;
}

// A permit can succeed through the EIP-1271 branch (the summary is applied to the staticcall).
rule witnessPermitVia1271(env e, address owner, address spender, uint256 value, uint256 deadline,
                          bytes signature) {
    require !called1271, "fresh recording before the call under test";
    permit(e, owner, spender, value, deadline, signature);
    satisfy called1271 && callee1271 == owner && ret1271 == ERC1271_MAGIC() && sigHash1271 == keccak256(signature);
}

// A permit can succeed on a nonce of 2^256 - 1, i.e. the wrap to 0 is covered by permitEffectsExact
// rather than excluded by an assumption.
rule witnessPermitAtMaxNonce(env e, bool useVRS, address owner, address spender, uint256 value,
                             uint256 deadline, bytes signature, uint8 v, bytes32 r, bytes32 s) {
    uint256 before = nonces(owner);
    callPermit(e, useVRS, owner, spender, value, deadline, signature, v, r, s);
    satisfy before == max_uint256 && nonces(owner) == 0;
}

// The chain id can differ from the deployment chain id, so the "other chain" branch of
// domainSeparatorBoundToChain is reachable.
rule witnessOtherChain(env e) {
    satisfy eip712Ref.chainId(e) != deploymentChainId();
}
