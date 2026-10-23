import "summaries/SavingsDai_base_summaries.spec";
import "summaries/SavingsDai_call_resolution.spec";
import "scene.spec";
import "invariants.spec";

/*
 * ERC-4626 vault behaviour of SavingsDai (component slug: erc4626-vault).
 * Properties: certora/properties/erc4626-vault.properties.json
 *
 * `pot` (alias of the Pot model) comes from invariants.spec.
 */

using Dai as daiToken;

methods {
    function allowance(address, address) external returns (uint256) envfree;
    function maxRedeem(address) external returns (uint256) envfree;
    function maxDeposit(address) external returns (uint256) envfree;
    function maxMint(address) external returns (uint256) envfree;
    function Pot.chi() external returns (uint256) envfree;
    function Pot.rho() external returns (uint256) envfree;
    function Pot.dsr() external returns (uint256) envfree;
    function Dai.balanceOf(address) external returns (uint256) envfree;
    function Dai.totalSupply() external returns (uint256) envfree;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// The rate accumulator a vault operation executed in `e` must use, computed independently from
/// the PRE-state of the Pot: if the Pot is stale (now > rho) it is drip's
/// rmul(rpow(dsr, now - rho), chi), otherwise the stored chi. rpowG is the scene's ghost model
/// of _rpow (scene.spec), shared with both the contract code and this expectation.
function expectedChi(env e) returns mathint {
    uint256 rho = pot.rho();
    uint256 chi = pot.chi();
    uint256 dsr = pot.dsr();
    if (e.block.timestamp > rho) {
        return (rpowG(dsr, assert_uint256(e.block.timestamp - rho), RAY()) * chi) / RAY();
    }
    return to_mathint(chi);
}

/// Structural invariants needed whenever shares are minted or burnt (unchecked arithmetic in
/// _mint/_burn is safe only under them).
function requireStructuralInvariants() {
    requireInvariant totalSupplyIsSumOfBalances();
    requireInvariant sharesBackedByPie();
    requireInvariant zeroAndSelfHoldNoShares();
}

/// Trust assumption (Pot model state): the rate accumulator is at least RAY. Pot's constructor
/// sets chi = RAY, and the only writer of chi afterwards is drip, which reverts unless the new
/// value is >= the old one (checked `tmp - chi`). The prover cannot establish this as an invariant
/// here (parametric_contracts is SavingsDai and the base case does not run Pot's constructor), so
/// the monotonicity half is proven by the justification rule `potChiNeverDecreases` below, which
/// calls every state-changing Pot entry point. Needed only where chi == 0 makes the ceil-division
/// expectation undefined (division by zero) or lets mint hand out shares for 0 assets.
function requirePotChiAtLeastRay() {
    require pot.chi() >= RAY();
    return;
}

// ---------------------------------------------------------------------------
// DAI token sum of balances (ghost + hooks on Dai.balanceOf, via the daiToken alias).
// Separate ghost from invariants.spec's sumOfBalances (which tracks SavingsDai.balanceOf).
// Pass 2: the real Dai uses checked add/sub everywhere, so no vault rule needs this anymore
// (see commentary); it is kept as a proven fact about the DAI model.
// ---------------------------------------------------------------------------

ghost mathint sumDaiBalances {
    init_state axiom sumDaiBalances == 0;
}

hook Sstore daiToken.balanceOf[KEY address a] uint256 newBal (uint256 oldBal) {
    sumDaiBalances = sumDaiBalances + newBal - oldBal;
}

// Every individual balance is one (non-negative) term of the sum.
hook Sload uint256 bal daiToken.balanceOf[KEY address a] {
    require sumDaiBalances >= to_mathint(bal);
}

/// DAI totalSupply equals the sum of all DAI balances. Used only as the induction hypothesis of
/// `daiSupplyIsSumPreserved`. Base case: Dai's constructor writes no balance and leaves
/// totalSupply = 0 (and the ghost's init_state is 0).
function requireDaiSupplyIsSum() {
    require to_mathint(daiToken.totalSupply()) == sumDaiBalances;
    return;
}

definition isDepositOp(method f) returns bool =
    f.selector == sig:deposit(uint256, address).selector ||
    f.selector == sig:deposit(uint256, address, uint16).selector ||
    f.selector == sig:mint(uint256, address).selector ||
    f.selector == sig:mint(uint256, address, uint16).selector;

definition isWithdrawOp(method f) returns bool =
    f.selector == sig:withdraw(uint256, address, address).selector ||
    f.selector == sig:redeem(uint256, address, address).selector;

/// Calls the deposit-side operation `f` (deposit/mint, with or without referral).
function callDepositOp(method f, env e, uint256 amount, address receiver, uint16 referral) {
    if (f.selector == sig:deposit(uint256, address).selector) {
        deposit(e, amount, receiver);
    } else if (f.selector == sig:deposit(uint256, address, uint16).selector) {
        deposit(e, amount, receiver, referral);
    } else if (f.selector == sig:mint(uint256, address).selector) {
        mint(e, amount, receiver);
    } else {
        mint(e, amount, receiver, referral);
    }
    return;
}

/// Same as callDepositOp but with revert recording; returns lastReverted.
function callDepositOpWithRevert(method f, env e, uint256 amount, address receiver, uint16 referral) returns bool {
    if (f.selector == sig:deposit(uint256, address).selector) {
        deposit@withrevert(e, amount, receiver);
    } else if (f.selector == sig:deposit(uint256, address, uint16).selector) {
        deposit@withrevert(e, amount, receiver, referral);
    } else if (f.selector == sig:mint(uint256, address).selector) {
        mint@withrevert(e, amount, receiver);
    } else {
        mint@withrevert(e, amount, receiver, referral);
    }
    return lastReverted;
}

/// Calls the withdraw-side operation `f` (withdraw/redeem).
function callWithdrawOp(method f, env e, uint256 amount, address receiver, address owner) {
    if (f.selector == sig:withdraw(uint256, address, address).selector) {
        withdraw(e, amount, receiver, owner);
    } else {
        redeem(e, amount, receiver, owner);
    }
    return;
}

// ---------------------------------------------------------------------------
// deposit_accounting
// ---------------------------------------------------------------------------

rule depositAccounting(env e, uint256 assets, address receiver) {
    requireStructuralInvariants();

    mathint chiExpected   = expectedChi(e);
    mathint balBefore     = balanceOf(receiver);
    mathint supplyBefore  = totalSupply();
    mathint pieBefore     = pot.pie(currentContract);
    mathint callerDaiBefore = daiToken.balanceOf(e.msg.sender);

    uint256 shares = deposit(e, assets, receiver);

    mathint chi = pot.chi();
    assert chi == chiExpected, "deposit must use the dripped Pot accumulator";
    assert to_mathint(shares) == (assets * RAY()) / chi, "shares != floor(assets*RAY/chi)";
    assert to_mathint(balanceOf(receiver)) == balBefore + shares, "receiver not credited exactly shares";
    assert to_mathint(totalSupply()) == supplyBefore + shares, "totalSupply not increased by shares";
    assert to_mathint(daiToken.balanceOf(e.msg.sender)) == callerDaiBefore - assets, "caller DAI not debited exactly assets";
    assert to_mathint(pot.pie(currentContract)) == pieBefore + shares, "Pot pie not increased by shares";
}

// ---------------------------------------------------------------------------
// mint_accounting
// ---------------------------------------------------------------------------

rule mintAccounting(env e, uint256 shares, address receiver) {
    requireStructuralInvariants();

    mathint chiExpected   = expectedChi(e);
    mathint balBefore     = balanceOf(receiver);
    mathint supplyBefore  = totalSupply();
    mathint pieBefore     = pot.pie(currentContract);
    mathint callerDaiBefore = daiToken.balanceOf(e.msg.sender);

    uint256 assets = mint(e, shares, receiver);

    mathint chi = pot.chi();
    assert chi == chiExpected, "mint must use the dripped Pot accumulator";
    assert to_mathint(assets) == (shares * chi + RAY() - 1) / RAY(), "assets != ceil(shares*chi/RAY)";
    assert to_mathint(balanceOf(receiver)) == balBefore + shares, "receiver not credited exactly shares";
    assert to_mathint(totalSupply()) == supplyBefore + shares, "totalSupply not increased by shares";
    assert to_mathint(daiToken.balanceOf(e.msg.sender)) == callerDaiBefore - assets, "caller DAI not debited exactly assets";
    assert to_mathint(pot.pie(currentContract)) == pieBefore + shares, "Pot pie not increased by shares";
}

// ---------------------------------------------------------------------------
// withdraw_accounting
// ---------------------------------------------------------------------------

rule withdrawAccounting(env e, uint256 assets, address receiver, address owner) {
    requireStructuralInvariants();
    requirePotChiAtLeastRay();

    mathint chiExpected   = expectedChi(e);
    mathint ownerBefore   = balanceOf(owner);
    mathint supplyBefore  = totalSupply();
    mathint pieBefore     = pot.pie(currentContract);
    mathint receiverDaiBefore = daiToken.balanceOf(receiver);

    uint256 shares = withdraw(e, assets, receiver, owner);

    mathint chi = pot.chi();
    assert chi == chiExpected, "withdraw must use the dripped Pot accumulator";
    assert to_mathint(shares) == (assets * RAY() + chi - 1) / chi, "shares != ceil(assets*RAY/chi)";
    assert to_mathint(balanceOf(owner)) == ownerBefore - shares, "owner not debited exactly shares";
    assert to_mathint(totalSupply()) == supplyBefore - shares, "totalSupply not decreased by shares";
    assert to_mathint(pot.pie(currentContract)) == pieBefore - shares, "Pot pie not decreased by shares";
    assert to_mathint(daiToken.balanceOf(receiver)) == receiverDaiBefore + assets, "receiver not credited exactly assets DAI";
}

// ---------------------------------------------------------------------------
// redeem_accounting
// ---------------------------------------------------------------------------

rule redeemAccounting(env e, uint256 shares, address receiver, address owner) {
    requireStructuralInvariants();

    mathint chiExpected   = expectedChi(e);
    mathint ownerBefore   = balanceOf(owner);
    mathint supplyBefore  = totalSupply();
    mathint pieBefore     = pot.pie(currentContract);
    mathint receiverDaiBefore = daiToken.balanceOf(receiver);

    uint256 assets = redeem(e, shares, receiver, owner);

    mathint chi = pot.chi();
    assert chi == chiExpected, "redeem must use the dripped Pot accumulator";
    assert to_mathint(assets) == (shares * chi) / RAY(), "assets != floor(shares*chi/RAY)";
    assert to_mathint(balanceOf(owner)) == ownerBefore - shares, "owner not debited exactly shares";
    assert to_mathint(totalSupply()) == supplyBefore - shares, "totalSupply not decreased by shares";
    assert to_mathint(pot.pie(currentContract)) == pieBefore - shares, "Pot pie not decreased by shares";
    assert to_mathint(daiToken.balanceOf(receiver)) == receiverDaiBefore + assets, "receiver not credited exactly assets DAI";
}

// ---------------------------------------------------------------------------
// withdraw_redeem_require_authorization
// ---------------------------------------------------------------------------

/// For withdraw and redeem by a caller other than owner: the burned shares (owner's balance
/// decrease) must be covered by the allowance, and a finite allowance is reduced by exactly that
/// amount (an infinite one is untouched).
rule withdrawRedeemRequireAllowance(method f, env e, uint256 amount, address receiver, address owner)
    filtered { f -> isWithdrawOp(f) }
{
    requireStructuralInvariants();
    address spender = e.msg.sender;
    require spender != owner; // the property is about third-party spenders; owner == caller needs no allowance

    mathint allowanceBefore = allowance(owner, spender);
    mathint ownerBefore     = balanceOf(owner);

    callWithdrawOp(f, e, amount, receiver, owner);

    mathint burned         = ownerBefore - balanceOf(owner);
    mathint allowanceAfter = allowance(owner, spender);

    assert allowanceBefore >= burned, "spent more shares than allowed";
    assert allowanceBefore == max_uint256 => allowanceAfter == max_uint256, "infinite allowance consumed";
    assert allowanceBefore != max_uint256 => allowanceAfter == allowanceBefore - burned, "finite allowance not reduced by burned shares";
}

// ---------------------------------------------------------------------------
// invalid_receiver_rejected
// ---------------------------------------------------------------------------

rule invalidReceiverRejected(method f, env e, uint256 amount, address receiver, uint16 referral)
    filtered { f -> isDepositOp(f) }
{
    bool reverted = callDepositOpWithRevert(f, e, amount, receiver, referral);
    assert (receiver == 0 || receiver == currentContract) => reverted, "deposit/mint to zero or self succeeded";
}

// ---------------------------------------------------------------------------
// previews_match_operations
// (Same state, same env, so same block.timestamp; the Pot may be stale or not.)
// ---------------------------------------------------------------------------

rule previewDepositMatchesDeposit(env e, uint256 assets, address receiver) {
    requireStructuralInvariants();
    uint256 preview = previewDeposit(e, assets);
    uint256 shares  = deposit(e, assets, receiver);
    assert preview == shares, "previewDeposit != deposit";
}

rule previewMintMatchesMint(env e, uint256 shares, address receiver) {
    requireStructuralInvariants();
    uint256 preview = previewMint(e, shares);
    uint256 assets  = mint(e, shares, receiver);
    assert preview == assets, "previewMint != mint";
}

rule previewWithdrawMatchesWithdraw(env e, uint256 assets, address receiver, address owner) {
    requireStructuralInvariants();
    uint256 preview = previewWithdraw(e, assets);
    uint256 shares  = withdraw(e, assets, receiver, owner);
    assert preview == shares, "previewWithdraw != withdraw";
}

rule previewRedeemMatchesRedeem(env e, uint256 shares, address receiver, address owner) {
    requireStructuralInvariants();
    uint256 preview = previewRedeem(e, shares);
    uint256 assets  = redeem(e, shares, receiver, owner);
    assert preview == assets, "previewRedeem != redeem";
}

// ---------------------------------------------------------------------------
// conversions_round_in_vault_favor
// ---------------------------------------------------------------------------

rule previewMintRoundsUp(env e, uint256 shares) {
    assert previewMint(e, shares) >= convertToAssets(e, shares), "previewMint charges less than exact conversion";
}

rule previewWithdrawRoundsUp(env e, uint256 assets) {
    assert previewWithdraw(e, assets) >= convertToShares(e, assets), "previewWithdraw burns less than exact conversion";
}

// ---------------------------------------------------------------------------
// max_functions_consistent
// ---------------------------------------------------------------------------

rule maxFunctionsConsistent(env e, address owner, address anyone) {
    assert maxRedeem(owner) == balanceOf(owner), "maxRedeem != balance";
    assert maxWithdraw(e, owner) == convertToAssets(e, balanceOf(owner)), "maxWithdraw != convertToAssets(balance)";
    assert maxDeposit(anyone) == max_uint256, "maxDeposit bounded";
    assert maxMint(anyone) == max_uint256, "maxMint bounded";
}

/// Redeeming more than maxRedeem(owner) always reverts.
rule redeemAboveMaxReverts(env e, uint256 shares, address receiver, address owner) {
    uint256 maxShares = maxRedeem(owner);
    redeem@withrevert(e, shares, receiver, owner);
    assert shares > maxShares => lastReverted, "redeemed more than maxRedeem";
}

/// Withdrawing more than maxWithdraw(owner) (same block) always reverts.
rule withdrawAboveMaxReverts(env e, uint256 assets, address receiver, address owner) {
    uint256 maxAssets = maxWithdraw(e, owner);
    withdraw@withrevert(e, assets, receiver, owner);
    assert assets > maxAssets => lastReverted, "withdrew more than maxWithdraw";
}

// ---------------------------------------------------------------------------
// no_profit_from_deposit_redeem_roundtrip
// ---------------------------------------------------------------------------

/// deposit(assets) then immediately redeem all received shares (same block, same caller,
/// caller is receiver and owner) returns at most `assets` and leaves the caller with no more DAI.
rule depositRedeemRoundtripNoProfit(env e, uint256 assets) {
    requireStructuralInvariants();
    address user = e.msg.sender;
    mathint daiBefore = daiToken.balanceOf(user);

    uint256 shares   = deposit(e, assets, user);
    uint256 assetsOut = redeem(e, shares, user, user);

    assert assetsOut <= assets, "roundtrip returned more DAI than deposited";
    assert to_mathint(daiToken.balanceOf(user)) <= daiBefore, "caller gained DAI from roundtrip";
}

/// mint(shares) then immediately withdraw the paid assets (same block): the withdrawal needs at
/// least as many shares as were minted.
rule mintWithdrawRoundtripNoProfit(env e, uint256 shares) {
    requireStructuralInvariants();
    requirePotChiAtLeastRay();
    address user = e.msg.sender;

    uint256 assetsPaid = mint(e, shares, user);
    uint256 sharesBurned = withdraw(e, assetsPaid, user, user);

    assert sharesBurned >= shares, "withdrawing the paid assets burned fewer shares than minted";
}

// ---------------------------------------------------------------------------
// share_price_never_decreases
// ---------------------------------------------------------------------------

/// No SavingsDai method lowers the Pot accumulator chi, nor the value of any share amount as
/// reported by convertToAssets in the same block.
rule sharePriceNeverDecreases(method f, env e, calldataarg args, uint256 s) {
    requireStructuralInvariants();
    mathint chiBefore   = pot.chi();
    mathint valueBefore = convertToAssets(e, s);

    f(e, args);

    assert to_mathint(pot.chi()) >= chiBefore, "chi decreased";
    assert to_mathint(convertToAssets(e, s)) >= valueBefore, "share value decreased";
}

// ---------------------------------------------------------------------------
// vault_ops_do_not_affect_other_holders
// ---------------------------------------------------------------------------

rule depositOpsDoNotAffectOthers(method f, env e, uint256 amount, address receiver, uint16 referral, address other)
    filtered { f -> isDepositOp(f) }
{
    requireStructuralInvariants();
    require other != receiver; // the property quantifies over accounts other than the receiver
    mathint otherBefore = balanceOf(other);

    callDepositOp(f, e, amount, receiver, referral);

    assert to_mathint(balanceOf(other)) == otherBefore, "deposit/mint changed a third party's shares";
}

rule withdrawOpsDoNotAffectOthers(method f, env e, uint256 amount, address receiver, address owner, address other)
    filtered { f -> isWithdrawOp(f) }
{
    requireStructuralInvariants();
    require other != owner; // the property quantifies over accounts other than the owner
    mathint otherBefore = balanceOf(other);

    callWithdrawOp(f, e, amount, receiver, owner);

    assert to_mathint(balanceOf(other)) == otherBefore, "withdraw/redeem changed a third party's shares";
}

// ---------------------------------------------------------------------------
// Justification rule for requirePotChiAtLeastRay: no state-changing Pot entry point lowers chi.
// (Pot's constructor sets chi = RAY; together this gives chi >= RAY in every reachable state.)
// ---------------------------------------------------------------------------

rule potChiNeverDecreases(env e, uint8 which, uint256 x, bytes32 what, address a) {
    mathint chiBefore = pot.chi();
    if (which == 0) {
        pot.drip(e);
    } else if (which == 1) {
        pot.join(e, x);
    } else if (which == 2) {
        pot.exit(e, x);
    } else if (which == 3) {
        pot.file(e, what, x);
    } else if (which == 4) {
        pot.file(e, what, a);
    } else if (which == 5) {
        pot.cage(e);
    } else if (which == 6) {
        pot.rely(e, a);
    } else {
        pot.deny(e, a);
    }
    assert to_mathint(pot.chi()) >= chiBefore, "a Pot entry point decreased chi";
}

// ---------------------------------------------------------------------------
// DAI supply == sum of balances is preserved by every state-changing Dai entry point, called
// directly with an arbitrary env and arguments. Only Dai code writes Dai storage, so this also
// covers the Dai calls made by DaiJoin (mint/burn) and SavingsDai (transferFrom/approve).
// Dai's arithmetic is checked (add/sub helpers), so unlike the pass-1 DaiMock version no
// pairwise balance bound is needed: an overflowing credit reverts.
// ---------------------------------------------------------------------------

rule daiSupplyIsSumPreserved(env e, uint8 which, address a, address b, uint256 x, uint256 y,
                             bool allowed, uint8 v, bytes32 r, bytes32 s) {
    requireDaiSupplyIsSum(); // induction hypothesis

    if (which == 0) {
        daiToken.transfer(e, a, x);
    } else if (which == 1) {
        daiToken.transferFrom(e, a, b, x);
    } else if (which == 2) {
        daiToken.mint(e, a, x);
    } else if (which == 3) {
        daiToken.burn(e, a, x);
    } else if (which == 4) {
        daiToken.approve(e, a, x);
    } else if (which == 5) {
        daiToken.push(e, a, x);
    } else if (which == 6) {
        daiToken.pull(e, a, x);
    } else if (which == 7) {
        daiToken.move(e, a, b, x);
    } else if (which == 8) {
        daiToken.rely(e, a);
    } else if (which == 9) {
        daiToken.deny(e, a);
    } else {
        daiToken.permit(e, a, b, x, y, allowed, v, r, s);
    }

    assert to_mathint(daiToken.totalSupply()) == sumDaiBalances, "DAI totalSupply != sum of balances";
}

// ===========================================================================
// PASS 3
// ===========================================================================

/// Calls withdraw/redeem with revert recording; returns lastReverted.
function callWithdrawOpWithRevert(method f, env e, uint256 amount, address receiver, address owner) returns bool {
    if (f.selector == sig:withdraw(uint256, address, address).selector) {
        withdraw@withrevert(e, amount, receiver, owner);
    } else {
        redeem@withrevert(e, amount, receiver, owner);
    }
    return lastReverted;
}

// ---------------------------------------------------------------------------
// referral_overloads_equivalent
// From one storage snapshot, the referral overload and the plain overload (same env, same
// arguments) revert in exactly the same cases, return the same value and leave the ENTIRE
// scene in the same state (`storage` equality covers every contract's storage, balances and
// all ghosts; see docs cvl/expr.html "Comparing storage"). The explicit balance/supply/pie/DAI
// reads are redundant with the storage equality and only make a counterexample readable.
// ---------------------------------------------------------------------------

rule depositReferralEquivalent(env e, uint256 assets, address receiver, uint16 referral) {
    storage init = lastStorage;

    uint256 sharesRef = deposit@withrevert(e, assets, receiver, referral);
    bool revertedRef = lastReverted;
    storage afterRef = lastStorage;
    mathint balRef    = balanceOf(receiver);
    mathint supplyRef = totalSupply();
    mathint pieRef    = pot.pie(currentContract);
    mathint daiRef    = daiToken.balanceOf(e.msg.sender);

    uint256 sharesPlain = deposit@withrevert(e, assets, receiver) at init;
    bool revertedPlain = lastReverted;
    storage afterPlain = lastStorage;

    assert revertedRef <=> revertedPlain, "referral deposit reverts differently from plain deposit";
    assert !revertedRef => sharesRef == sharesPlain, "referral deposit returns different shares";
    assert !revertedRef => (balRef == to_mathint(balanceOf(receiver))
                            && supplyRef == to_mathint(totalSupply())
                            && pieRef == to_mathint(pot.pie(currentContract))
                            && daiRef == to_mathint(daiToken.balanceOf(e.msg.sender))),
        "referral deposit leaves different balances";
    // Top-level `assert s1 == s2` form (the supported one). Unconditional: if both calls revert,
    // both snapshots are the rolled-back `init`; if exactly one reverts, the <=> assert fails.
    assert afterRef == afterPlain, "referral deposit leaves a different scene state";
}

rule mintReferralEquivalent(env e, uint256 shares, address receiver, uint16 referral) {
    storage init = lastStorage;

    uint256 assetsRef = mint@withrevert(e, shares, receiver, referral);
    bool revertedRef = lastReverted;
    storage afterRef = lastStorage;
    mathint balRef    = balanceOf(receiver);
    mathint supplyRef = totalSupply();
    mathint pieRef    = pot.pie(currentContract);
    mathint daiRef    = daiToken.balanceOf(e.msg.sender);

    uint256 assetsPlain = mint@withrevert(e, shares, receiver) at init;
    bool revertedPlain = lastReverted;
    storage afterPlain = lastStorage;

    assert revertedRef <=> revertedPlain, "referral mint reverts differently from plain mint";
    assert !revertedRef => assetsRef == assetsPlain, "referral mint returns different assets";
    assert !revertedRef => (balRef == to_mathint(balanceOf(receiver))
                            && supplyRef == to_mathint(totalSupply())
                            && pieRef == to_mathint(pot.pie(currentContract))
                            && daiRef == to_mathint(daiToken.balanceOf(e.msg.sender))),
        "referral mint leaves different balances";
    // Top-level `assert s1 == s2` form (the supported one). Unconditional: if both calls revert,
    // both snapshots are the rolled-back `init`; if exactly one reverts, the <=> assert fails.
    assert afterRef == afterPlain, "referral mint leaves a different scene state";
}

// ---------------------------------------------------------------------------
// conversions_and_previews_monotonic
// View functions: same state, same env (block), inputs x <= y. One rule per function so each
// nonlinear query is solved separately.
// ---------------------------------------------------------------------------

rule convertToSharesMonotonic(env e, uint256 x, uint256 y) {
    uint256 fx = convertToShares(e, x);
    uint256 fy = convertToShares(e, y);
    assert x <= y => fx <= fy, "convertToShares decreasing";
}

rule convertToAssetsMonotonic(env e, uint256 x, uint256 y) {
    uint256 fx = convertToAssets(e, x);
    uint256 fy = convertToAssets(e, y);
    assert x <= y => fx <= fy, "convertToAssets decreasing";
}

rule previewDepositMonotonic(env e, uint256 x, uint256 y) {
    uint256 fx = previewDeposit(e, x);
    uint256 fy = previewDeposit(e, y);
    assert x <= y => fx <= fy, "previewDeposit decreasing";
}

rule previewMintMonotonic(env e, uint256 x, uint256 y) {
    uint256 fx = previewMint(e, x);
    uint256 fy = previewMint(e, y);
    assert x <= y => fx <= fy, "previewMint decreasing";
}

rule previewWithdrawMonotonic(env e, uint256 x, uint256 y) {
    uint256 fx = previewWithdraw(e, x);
    uint256 fy = previewWithdraw(e, y);
    assert x <= y => fx <= fy, "previewWithdraw decreasing";
}

rule previewRedeemMonotonic(env e, uint256 x, uint256 y) {
    uint256 fx = previewRedeem(e, x);
    uint256 fy = previewRedeem(e, y);
    assert x <= y => fx <= fy, "previewRedeem decreasing";
}

// Actual operations: from one snapshot, op(x) and op(y) (same env, same receiver/owner).

rule depositMonotonic(env e, uint256 x, uint256 y, address receiver) {
    storage init = lastStorage;
    uint256 sx = deposit(e, x, receiver);
    uint256 sy = deposit(e, y, receiver) at init;
    assert x <= y => sx <= sy, "depositing more assets minted fewer shares";
}

rule mintMonotonic(env e, uint256 x, uint256 y, address receiver) {
    storage init = lastStorage;
    uint256 ax = mint(e, x, receiver);
    uint256 ay = mint(e, y, receiver) at init;
    assert x <= y => ax <= ay, "minting more shares cost fewer assets";
}

rule withdrawMonotonic(env e, uint256 x, uint256 y, address receiver, address owner) {
    storage init = lastStorage;
    uint256 sx = withdraw(e, x, receiver, owner);
    uint256 sy = withdraw(e, y, receiver, owner) at init;
    assert x <= y => sx <= sy, "withdrawing more assets burned fewer shares";
}

rule redeemMonotonic(env e, uint256 x, uint256 y, address receiver, address owner) {
    storage init = lastStorage;
    uint256 ax = redeem(e, x, receiver, owner);
    uint256 ay = redeem(e, y, receiver, owner) at init;
    assert x <= y => ax <= ay, "redeeming more shares paid fewer assets";
}

// ---------------------------------------------------------------------------
// no_gain_from_splitting_operations
// Same env (same block, caller, receiver, owner). Path 1: op(a) then op(b). Path 2, from the same
// snapshot: op(a + b). The second op of path 1 runs after the first dripped (rho == now), so it
// uses the same chi as path 2's single drip.
//
// `require ab == a + b` only names the combined amount as a uint256 call argument. It drops no
// case in which both split operations succeed: deposit/withdraw evaluate the checked product
// `amount * RAY`, so each of a, b is < 2^256 / 10^27 and a + b fits; mint's two Pot.join calls
// add a then b to Pot.Pie with checked addition, so a + b fits; redeem burns a then b from the
// owner's balance, so a + b <= the owner's prior balance.
// ---------------------------------------------------------------------------

rule depositSplitNoGain(env e, uint256 a, uint256 b, uint256 ab, address receiver) {
    requireStructuralInvariants();
    require to_mathint(ab) == a + b; // names the combined amount; see block comment above
    storage init = lastStorage;

    uint256 sa = deposit(e, a, receiver);
    uint256 sb = deposit(e, b, receiver);
    mathint balSplit = balanceOf(receiver);

    uint256 sab = deposit(e, ab, receiver) at init;
    mathint balJoint = balanceOf(receiver);

    assert sa + sb <= to_mathint(sab), "two deposits minted more shares than one combined deposit";
    assert balSplit <= balJoint, "receiver holds more shares after split deposits";
}

rule mintSplitNoGain(env e, uint256 a, uint256 b, uint256 ab, address receiver) {
    requireStructuralInvariants();
    require to_mathint(ab) == a + b; // names the combined amount; see block comment above
    storage init = lastStorage;

    uint256 assetsA = mint(e, a, receiver);
    uint256 assetsB = mint(e, b, receiver);
    mathint daiSplit = daiToken.balanceOf(e.msg.sender);

    uint256 assetsAB = mint(e, ab, receiver) at init;
    mathint daiJoint = daiToken.balanceOf(e.msg.sender);

    assert assetsA + assetsB >= to_mathint(assetsAB), "two mints cost fewer assets than one combined mint";
    assert daiSplit <= daiJoint, "caller kept more DAI after split mints";
}

rule withdrawSplitNoGain(env e, uint256 a, uint256 b, uint256 ab, address receiver, address owner) {
    requireStructuralInvariants();
    require to_mathint(ab) == a + b; // names the combined amount; see block comment above
    storage init = lastStorage;

    uint256 sharesA = withdraw(e, a, receiver, owner);
    uint256 sharesB = withdraw(e, b, receiver, owner);
    mathint ownerSplit = balanceOf(owner);

    uint256 sharesAB = withdraw(e, ab, receiver, owner) at init;
    mathint ownerJoint = balanceOf(owner);

    assert sharesA + sharesB >= to_mathint(sharesAB), "two withdraws burned fewer shares than one combined withdraw";
    assert ownerSplit <= ownerJoint, "owner kept more shares after split withdraws";
}

rule redeemSplitNoGain(env e, uint256 a, uint256 b, uint256 ab, address receiver, address owner) {
    requireStructuralInvariants();
    require to_mathint(ab) == a + b; // names the combined amount; see block comment above
    storage init = lastStorage;

    uint256 assetsA = redeem(e, a, receiver, owner);
    uint256 assetsB = redeem(e, b, receiver, owner);
    mathint daiSplit = daiToken.balanceOf(receiver);

    uint256 assetsAB = redeem(e, ab, receiver, owner) at init;
    mathint daiJoint = daiToken.balanceOf(receiver);

    assert assetsA + assetsB <= to_mathint(assetsAB), "two redeems paid more assets than one combined redeem";
    assert daiSplit <= daiJoint, "receiver got more DAI from split redeems";
}

// ---------------------------------------------------------------------------
// exit_rejects_invalid_receiver
// VERIFIED = withdraw/redeem to address(0) always revert. Expected to FAIL (finding): _burn does
// not check the receiver and Dai.mint (via DaiJoin.exit) accepts address(0).
// ---------------------------------------------------------------------------

rule exitRejectsZeroReceiver(method f, env e, uint256 amount, address owner)
    filtered { f -> isWithdrawOp(f) }
{
    requireStructuralInvariants();
    bool reverted = callWithdrawOpWithRevert(f, e, amount, 0, owner);
    assert reverted, "withdraw/redeem to address(0) succeeded";
}

/// Witness for the exitRejectsZeroReceiver finding (satisfy: VERIFIED = scenario reachable):
/// a withdraw of a positive amount of DAI to address(0) succeeds from a state satisfying the
/// structural invariants and chi >= RAY, burning the owner's shares while the DAI is minted to
/// address(0), where nobody can spend it.
rule exitToZeroReceiverWitness(env e, uint256 assets, address owner) {
    requireStructuralInvariants();
    requirePotChiAtLeastRay();
    mathint ownerBefore = balanceOf(owner);
    mathint zeroDaiBefore = daiToken.balanceOf(0);

    uint256 shares = withdraw(e, assets, 0, owner);

    satisfy assets > 0
        && to_mathint(daiToken.balanceOf(0)) == zeroDaiBefore + assets
        && to_mathint(balanceOf(owner)) == ownerBefore - shares
        && shares > 0;
}
