/*
 * maker-models / setup-third-party (pass 4): property third_parties_cannot_revoke_sdai_setup.
 *
 * SavingsDai's constructor establishes vat.can(sDAI, daiJoin) == 1, vat.can(sDAI, pot) == 1 and
 * dai.allowance(sDAI, daiJoin) == max (constructorWiresMakerSystem), and no SavingsDai method
 * undoes that (maker-integration setupApprovalsPreserved). This spec closes the remaining gap:
 * calls made DIRECTLY to the Vat / Dai (and, beyond the brief, to Pot / DaiJoin, which call into
 * the Vat and the Dai with themselves as msg.sender) by any account other than sDAI.
 *
 * Verified contract: Vat (only so that the conf has a main contract); parametric_contracts =
 * [Vat, Dai, Pot, DaiJoin], so the parametric rule runs every entry point of all four.
 * The addresses sdai, join, potAddr are fully arbitrary (they need not be the scene contracts).
 *
 * scene.spec is imported only for Pot._rpow => rpowG (the summary every spec runs under, keeping
 * Pot.drip's assembly loop out of the way); its wildcard UNRESOLVED entries never apply here,
 * since all calls of Pot/DaiJoin are resolved by the conf links to the scene Vat / Dai.
 */
import "../scene.spec";

using Vat as vatC;
using Dai as daiC;

methods {
    function Vat.can(address, address) external returns (uint256) envfree;
    function Dai.allowance(address, address) external returns (uint256) envfree;
}

/// Assumption K (cryptographic): sdai has no ECDSA private key, i.e. no (digest, v, r, s) recovers
/// to it. The prover models the ecrecover precompile (in contract code and in CVL alike) as one
/// uninterpreted function (expr.html "ECRecover"), so without K the model lets Dai.permit "recover"
/// ANY holder, sDAI included (witnessed by permitBySdaiReachableWithoutKeyAssumption below).
/// Justification: sDAI is a contract; its address is keccak256(rlp(deployer, nonce))[12:], and a
/// private key whose public key hashes to that address exists to anyone's knowledge only with
/// probability ~2^-160 per attempt (finding one is a 160-bit preimage search). Note K is about the
/// address sdai only; it is NOT true for an arbitrary EOA, for which permit can of course revoke.
function requireNoEcdsaKey(address who) {
    require forall bytes32 h. forall uint8 v. forall bytes32 r. forall bytes32 s.
        ecrecover(h, v, r, s) != who;
    return;
}

/// third_parties_cannot_revoke_sdai_setup: no call by an account other than sdai to any Vat, Dai,
/// Pot or DaiJoin entry point revokes sdai's Vat hope for join / pot or lowers sdai's max DAI
/// allowance to join.
rule thirdPartiesCannotRevokeSdaiSetup(method f, env e, calldataarg args,
                                       address sdai, address join, address potAddr) {
    // Carve-out: calls BY sDAI are exactly the calls SavingsDai's own methods make, and those are
    // covered by maker-integration setupApprovalsPreserved (all SavingsDai methods, any caller).
    require e.msg.sender != sdai;
    requireNoEcdsaKey(sdai); // assumption K (see above)

    bool hopeJoinBefore = vatC.can(sdai, join) == 1;
    bool hopePotBefore = vatC.can(sdai, potAddr) == 1;
    bool allowanceBefore = daiC.allowance(sdai, join) == max_uint256;

    f(e, args);

    assert hopeJoinBefore => vatC.can(sdai, join) == 1, "third party revoked sdai's Vat hope for join";
    assert hopePotBefore => vatC.can(sdai, potAddr) == 1, "third party revoked sdai's Vat hope for pot";
    assert allowanceBefore => daiC.allowance(sdai, join) == max_uint256,
        "third party lowered sdai's max DAI allowance to join";
}

/// Witness that assumption K is load-bearing in the model (not a property of the code): without
/// K, the prover's uninterpreted ecrecover lets a third party call Dai.permit(holder = sdai,
/// allowed = false) and zero sdai's allowance to join. Expected SATISFIED.
rule permitBySdaiReachableWithoutKeyAssumption(env e, address sdai, address join, uint256 nonce,
                                               uint256 expiry, uint8 v, bytes32 r, bytes32 s) {
    require e.msg.sender != sdai;
    require daiC.allowance(sdai, join) == max_uint256;

    daiC.permit(e, sdai, join, nonce, expiry, false, v, r, s);

    satisfy daiC.allowance(sdai, join) < max_uint256;
}

/// Under K, every Dai.permit with holder = sdai reverts (whatever the caller and arguments), so
/// permit is excluded as a revocation route by the code's own signature check, not by a filter.
rule permitBySdaiRevertsUnderKeyAssumption(env e, address sdai, address spender, uint256 nonce,
                                           uint256 expiry, bool allowed, uint8 v, bytes32 r, bytes32 s) {
    requireNoEcdsaKey(sdai);

    daiC.permit@withrevert(e, sdai, spender, nonce, expiry, allowed, v, r, s);

    assert lastReverted, "permit with holder = sdai succeeded although sdai has no key";
}
