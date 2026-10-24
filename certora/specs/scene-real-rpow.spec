/*
 * Variant of scene.spec for the rpow probe (erc4626-rpow-probe, pass 4).
 *
 * Cut from the PASS 1-3 scene.spec. It does NOT summarize SavingsDai._rpow / Pot._rpow: the
 * probe runs the real assembly exponentiation (loop unrolled to the conf's loop_iter, see
 * erc4626-rpow-probe.spec), so the rpowG ghost is not declared. It still models isValidSignature
 * as NONDET, whereas scene.spec switched to the deterministic isValidSigG ghost at the pass-4
 * barrier. This does not matter for the probe: it has no parametric rules, and convertToAssets
 * and the pure harness never reach _isValidSignature. The other entries match scene.spec:
 *
 * isValidSignature: ERC-1271 signer contracts are arbitrary external code reached through a
 * staticcall, so they cannot change state; a NONDET return value is a sound model.
 *
 * hope / approve / vat / dai (wildcard, UNRESOLVED policy only): these apply only to calls whose
 * target the prover cannot resolve, which in this scene happens solely in SavingsDai's
 * constructor. Every resolved (linked) call keeps its real implementation.
 */

definition RAY() returns uint256 = 10^27;

methods {
    function _.isValidSignature(bytes32, bytes) external => NONDET;
    function _.hope(address) external => NONDET;
    function _.approve(address, uint256) external => NONDET;
    function _.vat() external => NONDET;
    function _.dai() external => NONDET;
}
