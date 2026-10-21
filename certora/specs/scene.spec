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
 * staticcall, so they cannot change state; a NONDET return value is a sound model.
 *
 * hope / approve / vat / dai (wildcard, UNRESOLVED policy only): these apply only to calls whose
 * target the prover cannot resolve, which in this scene happens solely in SavingsDai's
 * constructor (daiJoin/vat/dai are still arbitrary constructor arguments there). Every resolved
 * (linked) call keeps its real implementation. During construction SavingsDai has no deployed
 * code, so no callee can re-enter it; NONDET therefore cannot hide any change to SavingsDai
 * state, Pot.pie or CVL ghosts; it only stops the default havoc from wiping ghosts in the
 * invariant base case. It DOES drop the constructor's real writes to Vat.can and
 * DaiMock.allowance, so no invariant reading those may rely on this summary for its base case.
 */

definition RAY() returns uint256 = 10^27;

ghost rpowG(uint256, uint256, uint256) returns uint256;

methods {
    function SavingsDai._rpow(uint256 x, uint256 n) internal returns (uint256) => rpowG(x, n, RAY());
    function Pot._rpow(uint256 x, uint256 n, uint256 base) internal returns (uint256) => rpowG(x, n, base);
    function _.isValidSignature(bytes32, bytes) external => NONDET;
    function _.hope(address) external => NONDET;
    function _.approve(address, uint256) external => NONDET;
    function _.vat() external => NONDET;
    function _.dai() external => NONDET;
}
