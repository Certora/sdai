/*
 * Scene-wide summaries shared by every SavingsDai spec.
 *
 * _rpow: both SavingsDai._rpow(x, n) (base RAY) and Pot._rpow(x, n, base) are the same
 * fixed-point exponentiation by squaring (an assembly loop). They are replaced by one
 * deterministic uninterpreted ghost function so that (a) no loop unrolling bound restricts the
 * elapsed time `now - rho`, and (b) SavingsDai's view-side chi estimate and Pot.drip's chi agree
 * exactly, as they do in the real code (identical algorithm, Pot always passes base = RAY).
 * Trust assumption: the real _rpow reverts on overflow; the summary never reverts.
 *
 * isValidSignature: ERC-1271 signer contracts are arbitrary external code reached through a
 * staticcall, so they cannot change state. The answer is modelled by the deterministic
 * uninterpreted ghost function isValidSigG(signer, digest) (signer = calledContract), returning
 * the raw bytes4 word that _isValidSignature compares with the ERC-1271 magic value. Two
 * executions that make the same staticcall (same signer, same digest) therefore get the same
 * answer, which is what lets a rule compare permit(v,r,s) with permit(bytes) on the 1271 path.
 * Trust assumptions (PASS 4, see permit.commentary.md "Pass 4"):
 *  - the answer ignores the signature bytes and the signer's state: any two staticcalls in one
 *    rule with the same (signer, digest) agree. No rule calls permit twice for the same
 *    (owner, digest) with different signature bytes or with the signer's state changed between
 *    the calls, so no rule is over-constrained by this (grep of certora/specs, pass 4);
 *  - the signer never reverts and always returns 32 bytes; a non-magic bytes4 already makes
 *    _isValidSignature return false exactly as a revert / short return would, so every outcome
 *    of _isValidSignature stays reachable;
 *  - gas-dependent signers (gasleft()) are not modelled.
 * (Pass 2 tried a ghost of (signer, digest, keccak256(signature)) via a CVL function taking
 * `bytes`; the prover then reported impossible storage changes inside permit(bytes) (invariants
 * run 401dc586). This model passes no `bytes` into CVL.)
 *
 * hope / approve / vat / dai (wildcard, UNRESOLVED policy only): these apply only to calls whose
 * target the prover cannot resolve, which in this scene happens solely in SavingsDai's
 * constructor (daiJoin/vat/dai are still arbitrary constructor arguments there). Every resolved
 * (linked) call keeps its real implementation. During construction SavingsDai has no deployed
 * code, so no callee can re-enter it; NONDET therefore cannot hide any change to SavingsDai
 * state, Pot.pie or CVL ghosts; it only stops the default havoc from wiping ghosts in the
 * invariant base case. It DOES drop the constructor's real writes to Vat.can and
 * Dai.allowance, so no invariant reading those may rely on this summary for its base case.
 */

definition RAY() returns uint256 = 10^27;

ghost rpowG(uint256, uint256, uint256) returns uint256;

// ERC-1271 answer of signer contract `signer` for `digest` (deterministic, see header).
ghost isValidSigG(address, bytes32) returns bytes4;

methods {
    function SavingsDai._rpow(uint256 x, uint256 n) internal returns (uint256) => rpowG(x, n, RAY());
    function Pot._rpow(uint256 x, uint256 n, uint256 base) internal returns (uint256) => rpowG(x, n, base);
    function _.isValidSignature(bytes32 digest, bytes) external => isValidSigG(calledContract, digest) expect bytes4;
    function _.hope(address) external => NONDET;
    function _.approve(address, uint256) external => NONDET;
    function _.vat() external => NONDET;
    function _.dai() external => NONDET;
}
