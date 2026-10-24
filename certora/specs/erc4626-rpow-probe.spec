import "summaries/SavingsDai_base_summaries.spec";
import "summaries/SavingsDai_call_resolution.spec";
import "scene-real-rpow.spec";

/*
 * PROBE of the real _rpow (component erc4626-vault, property share_price_monotonic_over_time).
 *
 * Every other erc4626-vault spec runs under scene.spec, which replaces _rpow by the uninterpreted
 * ghost rpowG; such a ghost knows nothing about how rpow(x, n) varies with n, so time-
 * monotonicity of the share price cannot be checked there. This spec imports scene-real-rpow.spec
 * (scene.spec minus the two _rpow summaries) and therefore executes SavingsDai's real assembly
 * _rpow. It does not import invariants.spec (which imports scene.spec); no rule here mints or
 * burns, so the structural invariants are not needed.
 *
 * COVERAGE BOUND. The _rpow loop runs floor(log2(n)) times. The conf sets loop_iter =
 * PROBE_LOOP_ITER with optimistic_loop, and every rule restricts the exponent explicitly to
 * n < PROBE_N_BOUND() = 2^PROBE_LOOP_ITER, so no covered execution is cut by the unrolling (the
 * loop runs at most PROBE_LOOP_ITER - 1 times). The satisfy rules *BoundReachable confirm the
 * largest covered exponent, PROBE_N_BOUND() - 1, is actually executed (not pruned by the
 * optimistic unrolling). Exponents >= PROBE_N_BOUND() are NOT covered.
 */

using Pot as pot;
using RpowHarness as rpowH;

methods {
    function Pot.rho() external returns (uint256) envfree;
    function Pot.dsr() external returns (uint256) envfree;
    function Pot.chi() external returns (uint256) envfree;
    function RpowHarness.rpow(uint256, uint256) external returns (uint256) envfree;
    function RpowHarness.rmulStep(uint256, uint256) external returns (uint256) envfree;
}

/// Must equal "loop_iter" in certora/confs/erc4626-rpow-probe.conf.
definition PROBE_LOOP_ITER() returns mathint = 4;
/// Covered exponents (seconds since rho): n < 2^PROBE_LOOP_ITER.
definition PROBE_N_BOUND() returns mathint = 2^PROBE_LOOP_ITER();

// ---------------------------------------------------------------------------
// share_price_monotonic_over_time
// Same storage (convertToAssets is a view, both calls run on the same state), two envs with
// rho <= t1 <= t2 and dsr >= RAY: the DAI value of s shares at t2 is not below its value at t1.
// The first three requires are the property's hypotheses; the fourth is the probe's coverage
// bound (see header). Both calls must succeed (an overflow revert inside _rpow / the products at
// t2 is a liveness question, not a price dip, and is not covered).
// ---------------------------------------------------------------------------

rule convertToAssetsMonotonicOverTime(env e1, env e2, uint256 s) {
    mathint rho = pot.rho();
    require pot.dsr() >= RAY();                                   // hypothesis: non-negative rate
    require to_mathint(e1.block.timestamp) >= rho;                // hypothesis: t1 >= rho
    require e1.block.timestamp <= e2.block.timestamp;             // hypothesis: t1 <= t2
    require e2.block.timestamp - rho < PROBE_N_BOUND();           // probe coverage bound

    uint256 v1 = convertToAssets(e1, s);
    uint256 v2 = convertToAssets(e2, s);

    assert v1 <= v2, "share price (convertToAssets) decreased over time";
}

/// Lemma on the verbatim copy of _rpow (RpowHarness): for x >= RAY, rpow(x, n) is non-decreasing
/// in n over the covered range. Together with the monotonicity of floor(r * chi / RAY) and
/// floor(s * c / RAY) in r and c, this is the arithmetic core of the rule above.
rule rpowMonotoneInN(uint256 x, uint256 n1, uint256 n2) {
    require x >= RAY();                                           // hypothesis: dsr >= RAY
    require n1 <= n2;                                             // hypothesis
    require n2 < PROBE_N_BOUND();                                 // probe coverage bound

    uint256 z1 = rpowH.rpow(x, n1);
    uint256 z2 = rpowH.rpow(x, n2);

    assert z1 <= z2, "rpow(x, n) decreased in n";
}

/// Successor form of the lemma: rpow(x, n) <= rpow(x, n + 1). By induction over the covered range
/// it implies rpowMonotoneInN; it is stated separately because it is a smaller solver query.
rule rpowMonotoneStep(uint256 x, uint256 n) {
    require x >= RAY();                                           // hypothesis: dsr >= RAY
    require n + 1 < PROBE_N_BOUND();                              // probe coverage bound

    uint256 z1 = rpowH.rpow(x, n);
    uint256 z2 = rpowH.rpow(x, assert_uint256(n + 1));

    assert z1 <= z2, "rpow(x, n + 1) < rpow(x, n)";
}

// ---------------------------------------------------------------------------
// Mainnet-range variants: dsr restricted to [RAY, MAINNET_DSR_MAX()]. MAINNET_DSR_MAX() = RAY + 2e19
// is a per-second rate of about 2e-8, i.e. ~88% APY; mainnet's DSR has never exceeded 15% APY
// (dsr ~ RAY + 4.4e18). They were added as smaller solver queries when the unrestricted rules
// timed out at loop_iter 6 (pass 4 iter 1/2); at the final loop_iter they are implied by the
// unrestricted rules above and are kept only as a record.
// ---------------------------------------------------------------------------

definition MAINNET_DSR_MAX() returns mathint = RAY() + 2 * 10^19;

rule convertToAssetsMonotonicOverTimeMainnetDsr(env e1, env e2, uint256 s) {
    mathint rho = pot.rho();
    require pot.dsr() >= RAY();                                   // hypothesis: non-negative rate
    require to_mathint(pot.dsr()) <= MAINNET_DSR_MAX();           // mainnet-range restriction
    require to_mathint(e1.block.timestamp) >= rho;                // hypothesis: t1 >= rho
    require e1.block.timestamp <= e2.block.timestamp;             // hypothesis: t1 <= t2
    require e2.block.timestamp - rho < PROBE_N_BOUND();           // probe coverage bound

    uint256 v1 = convertToAssets(e1, s);
    uint256 v2 = convertToAssets(e2, s);

    assert v1 <= v2, "share price (convertToAssets) decreased over time";
}

rule rpowMonotoneInNMainnetDsr(uint256 x, uint256 n1, uint256 n2) {
    require x >= RAY();                                           // hypothesis: dsr >= RAY
    require to_mathint(x) <= MAINNET_DSR_MAX();                   // mainnet-range restriction
    require n1 <= n2;                                             // hypothesis
    require n2 < PROBE_N_BOUND();                                 // probe coverage bound

    uint256 z1 = rpowH.rpow(x, n1);
    uint256 z2 = rpowH.rpow(x, n2);

    assert z1 <= z2, "rpow(x, n) decreased in n";
}

// ---------------------------------------------------------------------------
// Step lemmas (UNBOUNDED in n). rmulStep(z, x) = round(z * x / RAY) is a verbatim copy of the
// rounded multiplication inside the _rpow loop (RpowHarness.sol); the loop's squaring is the same
// step with z = x. These three facts, all single-multiplication queries with no loop, are what the
// pen-and-paper induction in erc4626-vault.commentary.md ("Pass 4", share_price_monotonic_over_time)
// needs to extend rpow(x, n) <= rpow(x, n + 1) from the bounded check above to every n.
// ---------------------------------------------------------------------------

/// Values >= RAY never shrink under a rounded multiplication by a value >= RAY.
rule rmulStepAtLeastArgs(uint256 a, uint256 b) {
    require a >= RAY() && b >= RAY();                             // hypothesis
    uint256 c = rpowH.rmulStep(a, b);
    assert c >= a && c >= b, "rounded product of values >= RAY is below a factor";
}

/// The rounded multiplication is monotone in both arguments.
rule rmulStepMonotone(uint256 a, uint256 a2, uint256 b, uint256 b2) {
    require a <= a2 && b <= b2;                                   // hypothesis
    uint256 c  = rpowH.rmulStep(a, b);
    uint256 c2 = rpowH.rmulStep(a2, b2);
    assert c <= c2, "rounded multiplication not monotone";
}

/// Multiplying by RAY (the fixed-point 1) is exact.
rule rmulStepRayIdentity(uint256 x) {
    uint256 c = rpowH.rmulStep(RAY(), x);
    assert c == x, "round(RAY * x / RAY) != x";
}

// ---------------------------------------------------------------------------
// Coverage witnesses (satisfy: VERIFIED = reachable). They show the largest covered exponent
// PROBE_N_BOUND() - 1 runs to completion, so loop_iter does not silently prune the covered range.
// ---------------------------------------------------------------------------

rule convertToAssetsBoundReachable(env e, uint256 s) {
    require pot.dsr() > RAY();
    require e.block.timestamp - pot.rho() == PROBE_N_BOUND() - 1;
    uint256 v = convertToAssets(e, s);
    satisfy v > 0;
}

rule rpowBoundReachable(uint256 x) {
    require x > RAY();
    uint256 z = rpowH.rpow(x, assert_uint256(PROBE_N_BOUND() - 1));
    satisfy z > x;
}
