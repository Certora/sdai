import "summaries/SavingsDai_base_summaries.spec";
import "summaries/SavingsDai_call_resolution.spec";
import "scene.spec";
import "invariants.spec";

/*
 * Maker integration of SavingsDai (component slug: maker-integration).
 * Properties: certora/properties/maker-integration.properties.json
 *
 * `pot` (alias of the Pot model) comes from invariants.spec.
 *
 * Liveness rules are stated as `op@withrevert(...); assert !lastReverted;` under NAMED
 * preconditions (the CVL functions `pre_*` below). Each precondition describes a fact about a
 * live, correctly configured mainnet Maker deployment; they are part of the property statement
 * ("in a live Maker system, X never reverts"), not trust assumptions about unreachable states.
 * Each rule uses only the preconditions its own call path needs (see commentary).
 */

using Vat as vatC;
using DaiJoin as daiJoinC;
using Dai as daiToken;

methods {
    function Pot.chi() external returns (uint256) envfree;
    function Pot.rho() external returns (uint256) envfree;
    function Pot.dsr() external returns (uint256) envfree;
    function Pot.Pie() external returns (uint256) envfree;
    function Pot.vow() external returns (address) envfree;
    function Vat.can(address, address) external returns (uint256) envfree;
    function Vat.dai(address) external returns (uint256) envfree;
    function Vat.sin(address) external returns (uint256) envfree;
    function Vat.debt() external returns (uint256) envfree;
    function Vat.vice() external returns (uint256) envfree;
    function Vat.wards(address) external returns (uint256) envfree;
    function DaiJoin.live() external returns (uint256) envfree;
    function Dai.wards(address) external returns (uint256) envfree;
    function Dai.balanceOf(address) external returns (uint256) envfree;
    function Dai.totalSupply() external returns (uint256) envfree;
    function Dai.allowance(address, address) external returns (uint256) envfree;
}

// ---------------------------------------------------------------------------
// Helpers: what Pot.drip will compute when a vault operation runs in env e
// ---------------------------------------------------------------------------

/// rpow(dsr, now - rho) as drip computes it (scene ghost rpowG); RAY when no drip happens
/// (now <= rho), so that chiAfterDrip below is uniform.
function dripFactor(env e) returns mathint {
    uint256 rho = pot.rho();
    if (e.block.timestamp > rho) {
        return rpowG(pot.dsr(), assert_uint256(e.block.timestamp - rho), RAY());
    }
    return RAY();
}

/// The rate accumulator the vault operation uses: drip's rmul(rpow(dsr, now - rho), chi) when
/// now > rho, the stored chi otherwise.
function chiAfterDrip(env e) returns mathint {
    return (dripFactor(e) * pot.chi()) / RAY();
}

/// The rad drip passes to vat.suck: Pie * (chi_new - chi_old) (0 when no drip happens).
function suckRad(env e) returns mathint {
    return pot.Pie() * (chiAfterDrip(e) - pot.chi());
}

function requireStructuralInvariants() {
    requireInvariant totalSupplyIsSumOfBalances();
    requireInvariant sharesBackedByPie();
    requireInvariant zeroAndSelfHoldNoShares();
    return;
}

// ---------------------------------------------------------------------------
// Named liveness preconditions (facts about a live mainnet Maker deployment)
// ---------------------------------------------------------------------------

/// P_noEther: the vault functions are non-payable; a liveness claim is about calls sending no ETH.
function pre_noEther(env e) {
    require e.msg.value == 0;
    return;
}

/// P_daiJoinLive: DaiJoin has not been caged (emergency shutdown). DaiJoin.exit requires it.
function pre_daiJoinLive() {
    require daiJoinC.live() == 1;
    return;
}

/// P_hopeDaiJoin: vat.can(sDAI, daiJoin) == 1, set by sDAI's constructor (`vat.hope(daiJoin)`)
/// and never revoked (rule setupApprovalsPreserved). scene.spec NONDETs the constructor's hope,
/// so it is stated here. DaiJoin.exit moves Vat dai out of sDAI on sDAI's behalf.
function pre_hopeDaiJoin() {
    require vatC.can(currentContract, daiJoinC) == 1;
    return;
}

/// P_hopePot: vat.can(sDAI, pot) == 1, set by sDAI's constructor (`vat.hope(pot)`), never revoked
/// (setupApprovalsPreserved). Pot.join moves Vat dai out of sDAI on sDAI's behalf.
function pre_hopePot() {
    require vatC.can(currentContract, pot) == 1;
    return;
}

/// P_daiJoinAllowance: Dai.allowance(sDAI, daiJoin) == max, set by sDAI's constructor
/// (`dai.approve(daiJoin, max)`), never lowered (setupApprovalsPreserved). DaiJoin.join burns
/// sDAI's DAI.
function pre_daiJoinAllowance() {
    require daiToken.allowance(currentContract, daiJoinC) == max_uint256;
    return;
}

/// P_daiJoinMints: DaiJoin is a ward of the DAI token (mainnet: the only minter of DAI).
function pre_daiJoinMints() {
    require daiToken.wards(daiJoinC) == 1;
    return;
}

/// P_potSucks: Pot is a ward of the Vat (mainnet: needed for drip's vat.suck).
function pre_potSucks() {
    require vatC.wards(pot) == 1;
    return;
}

/// P_dsrNonNegative: dsr >= RAY (the savings rate is not negative). Mainnet dsr has always been
/// >= RAY. This is the precondition that the probe redeemDoesNotDependOnDrip drops.
function pre_dsrNonNegative() {
    require pot.dsr() >= RAY();
    return;
}

/// P_rpowMonotone: mathematical property of the real _rpow (not of the deployment): for
/// x >= RAY, rpow(x, n, RAY) >= RAY (each rounded squaring/multiplication of values >= RAY stays
/// >= RAY). The scene models _rpow by the uninterpreted ghost rpowG, which does not know this.
/// It is vacuous when dsr < RAY.
function pre_rpowMonotone(env e) {
    require pot.dsr() >= RAY() => dripFactor(e) >= RAY();
    return;
}

/// P_timeNotBeforeRho: block.timestamp >= Pot.rho (rho is the timestamp of a past drip).
function pre_timeNotBeforeRho(env e) {
    require e.block.timestamp >= pot.rho();
    return;
}

/// P_chiPositive: Pot.chi >= RAY (initialised to RAY, drip never decreases it; cf. the
/// justification rule potChiNeverDecreases in erc4626-vault.spec). Mainnet chi ~ 1.05e27.
function pre_chiAtLeastRay() {
    require pot.chi() >= RAY();
    return;
}

/// P_PieCoversSdaiPie: Pot.Pie >= Pot.pie[sDAI]. In the real Pot, Pie is the sum of all pie.
function pre_PieCoversSdaiPie() {
    require pot.Pie() >= pot.pie(currentContract);
    return;
}

/// P_potSolvent: Pot's Vat dai covers sDAI's claim: vat.dai(pot) >= chi * pie[sDAI]. In the real
/// system vat.dai(pot) == chi * Pie (join/exit move exactly chi*wad, drip sucks Pie*dchi).
function pre_potSolvent() {
    require vatC.dai(pot) >= pot.chi() * pot.pie(currentContract);
    return;
}

/// P_daiBacked: DaiJoin's Vat dai backs the whole ERC-20 DAI supply:
/// vat.dai(daiJoin) >= RAY * Dai.totalSupply (DaiJoin.exit locks RAY*wad before minting wad,
/// join releases RAY*wad after burning wad).
function pre_daiBacked() {
    require vatC.dai(daiJoinC) >= RAY() * daiToken.totalSupply();
    return;
}

/// P_daiSupplyCoversHolders: DAI totalSupply is the sum of all DAI balances, so it is at least
/// the sum of the caller's and sDAI's balances (counted once if they coincide).
function pre_daiSupplyCoversHolders(address caller) {
    require daiToken.totalSupply() >=
        daiToken.balanceOf(caller) + (caller != currentContract ? daiToken.balanceOf(currentContract) : 0);
    return;
}

/// P_dripNoOverflow: drip's checked arithmetic and vat.suck's counters do not overflow:
/// rpow * chi (drip's rmul) and sin[vow] / vice / debt + rad all fit in uint256. Mainnet:
/// rpow, chi ~ 1e27 (product ~1e54); Pie ~ 1e27 wad, so rad ~ 1e52; debt ~ 5e54 rad;
/// max_uint256 ~ 1.16e77. (dai[pot] + rad is bounded per rule in P_exitNoOverflow /
/// P_joinNoOverflow, which also implies drip's checked `Pie * dchi` does not overflow.)
function pre_dripNoOverflow(env e) {
    require e.block.timestamp > pot.rho() => dripFactor(e) * pot.chi() <= max_uint256;
    require vatC.sin(pot.vow()) + suckRad(e) <= max_uint256;
    require vatC.vice() + suckRad(e) <= max_uint256;
    require vatC.debt() + suckRad(e) <= max_uint256;
    return;
}

/// P_exitNoOverflow: the counters credited when `assets` DAI leave the vault do not overflow:
/// vat.dai(pot) after the drip, vat.dai(sDAI) + chi*shares (Pot.exit), vat.dai(daiJoin) +
/// RAY*assets (DaiJoin.exit), Dai.totalSupply + assets and Dai.balanceOf(receiver) + assets
/// (Dai.mint). Mainnet: all Vat dai < 1e56 rad, DAI supply ~5e27 wad.
function pre_exitNoOverflow(env e, mathint shares, mathint assets, address receiver) {
    require vatC.dai(pot) + suckRad(e) <= max_uint256;
    require vatC.dai(currentContract) + chiAfterDrip(e) * shares <= max_uint256;
    require vatC.dai(daiJoinC) + RAY() * assets <= max_uint256;
    require daiToken.totalSupply() + assets <= max_uint256;
    require daiToken.balanceOf(receiver) + assets <= max_uint256;
    return;
}

/// P_joinNoOverflow: the counters credited by a deposit of `assets` (minting `shares`) do not
/// overflow: vat.dai(sDAI) + RAY*assets (DaiJoin.join), Pot.Pie + shares (Pot.join), and
/// vat.dai(pot) + rad + chi*shares (drip's suck then Pot.join's move).
function pre_joinNoOverflow(env e, mathint shares, mathint assets) {
    require vatC.dai(currentContract) + RAY() * assets <= max_uint256;
    require pot.Pie() + shares <= max_uint256;
    require vatC.dai(pot) + suckRad(e) + chiAfterDrip(e) * shares <= max_uint256;
    return;
}

/// All exit-side preconditions except P_dsrNonNegative (shared by the redeem/withdraw liveness
/// rules and the drip probe). `shares`/`assets` are upper bounds on what the call burns/pays.
function pre_liveExitExceptDsr(env e, mathint shares, mathint assets, address receiver) {
    pre_noEther(e);
    pre_daiJoinLive();
    pre_hopeDaiJoin();
    pre_daiJoinMints();
    pre_potSucks();
    pre_rpowMonotone(e);
    pre_PieCoversSdaiPie();
    pre_potSolvent();
    pre_dripNoOverflow(e);
    pre_exitNoOverflow(e, shares, assets, receiver);
    return;
}

// ---------------------------------------------------------------------------
// setup_approvals_preserved
// ---------------------------------------------------------------------------

rule setupApprovalsPreserved(method f, env e, calldataarg args) {
    bool hopeJoinBefore = vatC.can(currentContract, daiJoinC) == 1;
    bool hopePotBefore = vatC.can(currentContract, pot) == 1;
    bool allowanceBefore = daiToken.allowance(currentContract, daiJoinC) == max_uint256;

    f(e, args);

    assert hopeJoinBefore => vatC.can(currentContract, daiJoinC) == 1, "sDAI's Vat hope for DaiJoin revoked";
    assert hopePotBefore => vatC.can(currentContract, pot) == 1, "sDAI's Vat hope for Pot revoked";
    assert allowanceBefore => daiToken.allowance(currentContract, daiJoinC) == max_uint256,
        "sDAI's DAI allowance to DaiJoin lowered";
}

// ---------------------------------------------------------------------------
// owner_can_always_redeem
// ---------------------------------------------------------------------------

/// An owner can redeem their whole share balance in a live Maker system.
rule ownerCanRedeemAll(env e, address receiver) {
    requireStructuralInvariants();
    address owner = e.msg.sender;
    uint256 shares = balanceOf(owner);
    mathint assets = (shares * chiAfterDrip(e)) / RAY();

    pre_liveExitExceptDsr(e, shares, assets, receiver);
    pre_dsrNonNegative();

    redeem@withrevert(e, shares, receiver, owner);
    assert !lastReverted, "owner's redeem of full balance reverted in a live Maker system";
}

/// An owner can withdraw maxWithdraw(owner) in a live Maker system (and maxWithdraw itself does
/// not revert).
rule ownerCanWithdrawMax(env e, address receiver) {
    requireStructuralInvariants();
    address owner = e.msg.sender;
    uint256 shares = balanceOf(owner);
    // maxWithdraw(owner) == floor(balance * chi / RAY); withdraw burns at most `shares`.
    mathint assets = (shares * chiAfterDrip(e)) / RAY();

    pre_liveExitExceptDsr(e, shares, assets, receiver);
    pre_dsrNonNegative();

    uint256 maxAssets = maxWithdraw@withrevert(e, owner);
    bool maxReverted = lastReverted;
    withdraw@withrevert(e, maxAssets, receiver, owner);
    bool withdrawReverted = lastReverted;

    assert !maxReverted, "maxWithdraw reverted in a live Maker system";
    assert !withdrawReverted, "owner's withdraw of maxWithdraw reverted in a live Maker system";
}

// ---------------------------------------------------------------------------
// redeem_does_not_depend_on_drip (probe)
// ---------------------------------------------------------------------------

/// Same as ownerCanRedeemAll but WITHOUT P_dsrNonNegative: an owner should still be able to
/// leave when governance sets dsr < RAY (as direct Pot depositors can, via Pot.exit, which does
/// not require rho == now).
rule redeemDoesNotDependOnDrip(env e, address receiver) {
    requireStructuralInvariants();
    address owner = e.msg.sender;
    uint256 shares = balanceOf(owner);
    mathint assets = (shares * chiAfterDrip(e)) / RAY();

    pre_liveExitExceptDsr(e, shares, assets, receiver);

    redeem@withrevert(e, shares, receiver, owner);
    assert !lastReverted, "owner's redeem blocked although dsr < RAY only affects drip";
}

// ---------------------------------------------------------------------------
// deposit_liveness
// ---------------------------------------------------------------------------

rule depositLiveness(env e, uint256 assets, address receiver) {
    address caller = e.msg.sender;
    mathint chiNow = chiAfterDrip(e);
    mathint shares = chiNow > 0 ? (assets * RAY()) / chiNow : 0;

    // The call: a valid receiver, a caller with enough DAI and DAI allowance to sDAI.
    require receiver != 0 && receiver != currentContract;
    require daiToken.balanceOf(caller) >= assets;
    require daiToken.allowance(caller, currentContract) >= assets;

    // The live Maker system.
    pre_noEther(e);
    pre_timeNotBeforeRho(e);
    pre_chiAtLeastRay();
    pre_hopePot();
    pre_daiJoinAllowance();
    pre_potSucks();
    pre_dsrNonNegative();
    pre_rpowMonotone(e);
    pre_PieCoversSdaiPie();
    pre_daiBacked();
    pre_daiSupplyCoversHolders(caller);
    pre_dripNoOverflow(e);
    pre_joinNoOverflow(e, shares, assets);

    deposit@withrevert(e, assets, receiver);
    assert !lastReverted, "deposit reverted in a live Maker system";
}

// ---------------------------------------------------------------------------
// vault_never_pays_rounding_from_own_vat_balance
// ---------------------------------------------------------------------------

/// No SavingsDai method (in particular deposit/mint/withdraw/redeem and their referral
/// overloads) decreases sDAI's own Vat dai balance.
rule vaultNeverPaysRoundingFromOwnVatBalance(method f, env e, calldataarg args) {
    mathint vatDaiBefore = vatC.dai(currentContract);

    f(e, args);

    assert vatC.dai(currentContract) >= vatDaiBefore, "sDAI's own Vat dai balance decreased";
}
