import "summaries/SavingsDai_base_summaries.spec";
import "summaries/SavingsDai_call_resolution.spec";
import "scene.spec";
import "invariants.spec";

// SigPacker (certora/harnesses/SigPacker.sol): pure helper, pack(v, r, s) = abi.encodePacked(r, s, v).
// Alias `packer` does not clash with invariants.spec (`pot`) or scene.spec (no aliases).
using SigPacker as packer;

/*
 * Permit (EIP-2612 / ERC-1271) properties of SavingsDai (batch slug: permit).
 * Properties: certora/properties/permit.properties.json
 *
 * Signature model:
 *  - ecrecover is modelled by the prover as a deterministic uninterpreted (ghost) function
 *    (docs: cvl/expr.html "ECRecover"); the CVL builtin `ecrecover` refers to the same function.
 *  - ERC-1271 `isValidSignature` is NONDET (scene.spec): every staticcall returns a fresh,
 *    arbitrary value. Rules therefore never assume a particular signature is (in)valid; where a
 *    valid permit is needed, they constrain on the permit call not reverting.
 */

methods {
    function nonces(address) external returns (uint256) envfree;
    function allowance(address, address) external returns (uint256) envfree;
    function SigPacker.pack(uint8, bytes32, bytes32) external returns (bytes) envfree;
}

definition TWO_256() returns mathint = 2^256;

/// Calls one of the two permit entry points, with revert allowed; returns whether it reverted.
/// bytesForm == true  -> permit(owner, spender, value, deadline, bytes signature)
/// bytesForm == false -> permit(owner, spender, value, deadline, v, r, s)
function callPermitWithRevert(env e, bool bytesForm, address owner, address spender, uint256 value,
                              uint256 deadline, uint8 v, bytes32 r, bytes32 s, bytes signature) returns bool {
    if (bytesForm) {
        permit@withrevert(e, owner, spender, value, deadline, signature);
    } else {
        permit@withrevert(e, owner, spender, value, deadline, v, r, s);
    }
    return lastReverted;
}

definition isPermit(method f) returns bool =
    f.selector == sig:permit(address,address,uint256,uint256,bytes).selector ||
    f.selector == sig:permit(address,address,uint256,uint256,uint8,bytes32,bytes32).selector;

// ---------------------------------------------------------------------------
// permit_revert_on_expired_or_zero_owner
// ---------------------------------------------------------------------------

/// permit_revert_on_expired_or_zero_owner
/// Both permit entry points revert when the deadline has passed or owner is the zero address,
/// whatever the signature (ECDSA or ERC-1271).
rule permitRevertsOnExpiredOrZeroOwner(env e, bool bytesForm, address owner, address spender,
                                       uint256 value, uint256 deadline, uint8 v, bytes32 r,
                                       bytes32 s, bytes signature) {
    bool expired = e.block.timestamp > deadline;
    bool zeroOwner = owner == 0;

    bool reverted = callPermitWithRevert(e, bytesForm, owner, spender, value, deadline, v, r, s, signature);

    assert (expired || zeroOwner) => reverted;
}

// ---------------------------------------------------------------------------
// permit_effects
// ---------------------------------------------------------------------------

/// permit_effects
/// A successful permit (either form) sets allowance[owner][spender] := value, advances
/// nonces[owner] by one (in uint256 arithmetic, i.e. modulo 2^256, exactly as the unchecked
/// `nonces[owner]++` does; for every nonce < max_uint256 this is exactly +1 - see
/// noncesNeverDecrease for the wrap discussion), and leaves every other allowance, every other
/// nonce, every balance and totalSupply unchanged.
rule permitEffects(env e, bool bytesForm, address owner, address spender, uint256 value,
                   uint256 deadline, uint8 v, bytes32 r, bytes32 s, bytes signature,
                   address otherOwner, address otherSpender, address otherNonceHolder,
                   address anyHolder) {
    require otherOwner != owner || otherSpender != spender;
    require otherNonceHolder != owner;

    mathint nonceBefore = nonces(owner);
    uint256 otherAllowanceBefore = allowance(otherOwner, otherSpender);
    uint256 otherNonceBefore = nonces(otherNonceHolder);
    uint256 balanceBefore = balanceOf(anyHolder);
    uint256 supplyBefore = totalSupply();

    bool reverted = callPermitWithRevert(e, bytesForm, owner, spender, value, deadline, v, r, s, signature);

    assert !reverted => allowance(owner, spender) == value;
    assert !reverted => to_mathint(nonces(owner)) == (nonceBefore + 1) % TWO_256();
    assert allowance(otherOwner, otherSpender) == otherAllowanceBefore;
    assert nonces(otherNonceHolder) == otherNonceBefore;
    assert balanceOf(anyHolder) == balanceBefore;
    assert totalSupply() == supplyBefore;
}

// ---------------------------------------------------------------------------
// nonces_only_increase_via_permit
// ---------------------------------------------------------------------------

/// nonces_only_increase_via_permit (monotonicity part)
/// No SavingsDai method decreases any nonce, except the wrap max_uint256 -> 0 of the unchecked
/// increment, which the assertion names explicitly (no precondition).
rule noncesNeverDecrease(env e, method f, calldataarg args, address holder) {
    uint256 nonceBefore = nonces(holder);

    f(e, args);

    // No assumption: the single permitted "decrease" is the wrap of the unchecked
    // `nonces[owner]++` at max_uint256 (unreachable in practice: it needs 2^256 - 1 successful
    // permits for one owner, each advancing the nonce by exactly one - nonceChangesOnlyViaPermit).
    assert nonces(holder) >= nonceBefore || (nonceBefore == max_uint256 && nonces(holder) == 0);
}

/// nonces_only_increase_via_permit (only-permit / exactly-one part)
/// A nonce changes only through a successful permit, and then by exactly one (mod 2^256).
/// That the changed nonce is the permit's `owner` is established by permitEffects
/// (no other nonce changes in a permit).
rule nonceChangesOnlyViaPermit(env e, method f, calldataarg args, address holder) {
    mathint nonceBefore = nonces(holder);

    f(e, args);

    mathint nonceAfter = nonces(holder);
    assert nonceAfter != nonceBefore => isPermit(f);
    assert nonceAfter != nonceBefore => nonceAfter == (nonceBefore + 1) % TWO_256();
}

// ---------------------------------------------------------------------------
// permit_signature_forms_equivalent
// ---------------------------------------------------------------------------

/// Byte `k` (0 = most significant) of a 256-bit word, as bytes1.
function byteOf(uint256 word, uint256 k) returns bytes1 {
    return to_bytes1(require_uint8((word / 2^(8 * (31 - k))) % 256));
}

/// Requires signature == abi.encodePacked(to_bytes32(rWord), to_bytes32(sWord), v), byte by byte.
/// CVL has no abi.encodePacked, but it does allow indexing a CVL `bytes` value (elements are
/// bytes1), so the 65-byte packed encoding is pinned down exactly: bytes 0..31 = r (big-endian),
/// bytes 32..63 = s, byte 64 = v. This is a definition of the input, not an assumption.
function requirePacked(bytes signature, uint256 rWord, uint256 sWord, uint8 v) {
    require signature.length == 65;
    require signature[0] == byteOf(rWord, 0);
    require signature[1] == byteOf(rWord, 1);
    require signature[2] == byteOf(rWord, 2);
    require signature[3] == byteOf(rWord, 3);
    require signature[4] == byteOf(rWord, 4);
    require signature[5] == byteOf(rWord, 5);
    require signature[6] == byteOf(rWord, 6);
    require signature[7] == byteOf(rWord, 7);
    require signature[8] == byteOf(rWord, 8);
    require signature[9] == byteOf(rWord, 9);
    require signature[10] == byteOf(rWord, 10);
    require signature[11] == byteOf(rWord, 11);
    require signature[12] == byteOf(rWord, 12);
    require signature[13] == byteOf(rWord, 13);
    require signature[14] == byteOf(rWord, 14);
    require signature[15] == byteOf(rWord, 15);
    require signature[16] == byteOf(rWord, 16);
    require signature[17] == byteOf(rWord, 17);
    require signature[18] == byteOf(rWord, 18);
    require signature[19] == byteOf(rWord, 19);
    require signature[20] == byteOf(rWord, 20);
    require signature[21] == byteOf(rWord, 21);
    require signature[22] == byteOf(rWord, 22);
    require signature[23] == byteOf(rWord, 23);
    require signature[24] == byteOf(rWord, 24);
    require signature[25] == byteOf(rWord, 25);
    require signature[26] == byteOf(rWord, 26);
    require signature[27] == byteOf(rWord, 27);
    require signature[28] == byteOf(rWord, 28);
    require signature[29] == byteOf(rWord, 29);
    require signature[30] == byteOf(rWord, 30);
    require signature[31] == byteOf(rWord, 31);
    require signature[32] == byteOf(sWord, 0);
    require signature[33] == byteOf(sWord, 1);
    require signature[34] == byteOf(sWord, 2);
    require signature[35] == byteOf(sWord, 3);
    require signature[36] == byteOf(sWord, 4);
    require signature[37] == byteOf(sWord, 5);
    require signature[38] == byteOf(sWord, 6);
    require signature[39] == byteOf(sWord, 7);
    require signature[40] == byteOf(sWord, 8);
    require signature[41] == byteOf(sWord, 9);
    require signature[42] == byteOf(sWord, 10);
    require signature[43] == byteOf(sWord, 11);
    require signature[44] == byteOf(sWord, 12);
    require signature[45] == byteOf(sWord, 13);
    require signature[46] == byteOf(sWord, 14);
    require signature[47] == byteOf(sWord, 15);
    require signature[48] == byteOf(sWord, 16);
    require signature[49] == byteOf(sWord, 17);
    require signature[50] == byteOf(sWord, 18);
    require signature[51] == byteOf(sWord, 19);
    require signature[52] == byteOf(sWord, 20);
    require signature[53] == byteOf(sWord, 21);
    require signature[54] == byteOf(sWord, 22);
    require signature[55] == byteOf(sWord, 23);
    require signature[56] == byteOf(sWord, 24);
    require signature[57] == byteOf(sWord, 25);
    require signature[58] == byteOf(sWord, 26);
    require signature[59] == byteOf(sWord, 27);
    require signature[60] == byteOf(sWord, 28);
    require signature[61] == byteOf(sWord, 29);
    require signature[62] == byteOf(sWord, 30);
    require signature[63] == byteOf(sWord, 31);
    require signature[64] == to_bytes1(v);
    return;
}

/// permit_signature_forms_equivalent
/// From the same pre-state, permit(owner, spender, value, deadline, v, r, s) and
/// permit(owner, spender, value, deadline, packed) with packed = abi.encodePacked(r, s, v) have the same
/// revert behaviour and leave the same allowance[owner][spender] and nonces[owner].
///
/// packed is built by Solidity (SigPacker.pack, a pure abi.encodePacked(r, s, v)), not in CVL, so the
/// bytes value handed to permit(bytes) is the contract-built packed encoding.
///
/// Scope: the ECDSA path decides. The digest cannot be recomputed in CVL (abi.encodePacked with the
/// 2-byte "\x19\x01" prefix), so (v, r, s) is assumed to recover `owner` for every digest. This
/// constrains only the uninterpreted ecrecover function, not the contract. If either form decoded
/// anything other than (v, r, s) from its bytes, ecrecover would be unconstrained there, the call
/// would fall through to the NONDET ERC-1271 staticcall and the two runs could disagree, so the
/// rule would fail. Not covered: signatures for which ecrecover does not return owner, where the
/// ERC-1271 fallback decides; under the NONDET scene summary the two executions' isValidSignature
/// answers are independent (see permit.commentary.md, Pass 2).
rule permitSignatureFormsEquivalent(env e, address owner, address spender, uint256 value,
                                    uint256 deadline, uint8 v, bytes32 r, bytes32 s) {
    // ECDSA path accepts (see rule comment): an assumption on the ecrecover function only.
    require forall bytes32 d. ecrecover(d, v, r, s) == owner;

    bytes packed = packer.pack(v, r, s);

    storage init = lastStorage;

    permit@withrevert(e, owner, spender, value, deadline, v, r, s) at init;
    bool revertedVrs = lastReverted;
    uint256 allowanceVrs = allowance(owner, spender);
    uint256 nonceVrs = nonces(owner);

    permit@withrevert(e, owner, spender, value, deadline, packed) at init;
    bool revertedBytes = lastReverted;
    uint256 allowanceBytes = allowance(owner, spender);
    uint256 nonceBytes = nonces(owner);

    assert revertedVrs <=> revertedBytes;
    assert allowanceVrs == allowanceBytes;
    assert nonceVrs == nonceBytes;
}

/// permit_signature_forms_equivalent (sound alternative to the byte-level comparison above)
/// permit(v, r, s) packs abi.encodePacked(r, s, v) and hands it to permit(bytes), whose
/// _isValidSignature decodes it with mload/byte and calls ecrecover. If that round trip did not
/// return exactly (v, r, s), ecrecover would be evaluated at a different, unconstrained point and
/// the call could fall through to the (NONDET) ERC-1271 path and revert. So: whenever (v, r, s)
/// recovers to owner (for every digest; the digest is not recomputable in CVL) and the
/// non-signature checks pass, permit(v, r, s) must succeed - and then has permitEffects' effects,
/// exactly those of permit(bytes).
rule permitVrsDecodesPackedSignature(env e, address owner, address spender, uint256 value,
                                     uint256 deadline, uint8 v, bytes32 r, bytes32 s) {
    // ECDSA accepts: an assumption on the ecrecover ghost only (see rule comment).
    require forall bytes32 d. ecrecover(d, v, r, s) == owner;
    bool checksPass = e.block.timestamp <= deadline && owner != 0 && e.msg.value == 0;

    permit@withrevert(e, owner, spender, value, deadline, v, r, s);

    assert checksPass => !lastReverted;
}

/// permit_signature_forms_equivalent (no assumption on the signature path)
/// Whenever both forms succeed from the same pre-state (any signature path, ECDSA or ERC-1271),
/// they produce the same allowance and nonce; and both revert when the deadline has passed or
/// owner is zero.
rule permitSignatureFormsSameEffects(env e, address owner, address spender, uint256 value,
                                     uint256 deadline, uint8 v, uint256 rWord, uint256 sWord,
                                     bytes signature) {
    bytes32 r = to_bytes32(rWord);
    bytes32 s = to_bytes32(sWord);
    requirePacked(signature, rWord, sWord, v);
    bool preconditionFails = e.block.timestamp > deadline || owner == 0;

    storage init = lastStorage;

    permit@withrevert(e, owner, spender, value, deadline, v, r, s) at init;
    bool revertedVrs = lastReverted;
    uint256 allowanceVrs = allowance(owner, spender);
    uint256 nonceVrs = nonces(owner);

    permit@withrevert(e, owner, spender, value, deadline, signature) at init;
    bool revertedBytes = lastReverted;
    uint256 allowanceBytes = allowance(owner, spender);
    uint256 nonceBytes = nonces(owner);

    assert preconditionFails => (revertedVrs && revertedBytes);
    assert (!revertedVrs && !revertedBytes) => (allowanceVrs == allowanceBytes && nonceVrs == nonceBytes);
}
