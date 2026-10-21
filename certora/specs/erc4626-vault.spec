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

using DaiMock as daiToken;

methods {
    function allowance(address, address) external returns (uint256) envfree;
    function maxRedeem(address) external returns (uint256) envfree;
    function maxDeposit(address) external returns (uint256) envfree;
    function maxMint(address) external returns (uint256) envfree;
    function Pot.chi() external returns (uint256) envfree;
    function Pot.rho() external returns (uint256) envfree;
    function Pot.dsr() external returns (uint256) envfree;
    function DaiMock.balanceOf(address) external returns (uint256) envfree;
    function DaiMock.totalSupply() external returns (uint256) envfree;
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
// DAI token sum of balances (ghost + hooks on DaiMock.balanceOf, via the daiToken alias).
// Separate ghost from invariants.spec's sumOfBalances (which tracks SavingsDai.balanceOf).
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

/// DAI totalSupply equals the sum of all DAI balances. Justified by:
///  - base case: DaiMock's constructor writes no balance and leaves totalSupply = 0 (and the
///    ghost's init_state is 0);
///  - step: the justification rule `daiSupplyIsSumPreserved` (below) proves every state-changing
///    DaiMock entry point preserves it. Only DaiMock writes DaiMock storage, so this also covers
///    DaiMock calls made by DaiJoinMock and SavingsDai.
/// Combined with the Sload hook it yields balanceOf(a) <= totalSupply for every account a read,
/// which is what DaiMock.mint's unchecked `balanceOf[to] + value` relies on.
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
    requireDaiSupplyIsSum();

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
    requireDaiSupplyIsSum();

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
// Justification rule for requireDaiSupplyIsSum: every state-changing DaiMock entry point,
// called directly with an arbitrary env and arguments, preserves totalSupply == sum of balances.
// ---------------------------------------------------------------------------

rule daiSupplyIsSumPreserved(env e, uint8 which, address a, address b, uint256 x, uint256 deadline,
                             bytes signature, uint8 v, bytes32 r, bytes32 s) {
    requireDaiSupplyIsSum(); // induction hypothesis
    // The ghost is the sum of all (non-negative) balances, so two DISTINCT accounts' balances
    // together never exceed it. (The Sload hook only bounds single balances.) Needed for the
    // unchecked `balanceOf[to] += value` in transfer/transferFrom; the pairs are exactly the
    // (from, to) pairs those functions touch.
    require e.msg.sender != a => daiToken.balanceOf(e.msg.sender) + daiToken.balanceOf(a) <= sumDaiBalances;
    require a != b => daiToken.balanceOf(a) + daiToken.balanceOf(b) <= sumDaiBalances;

    if (which == 0) {
        daiToken.transfer(e, a, x);
    } else if (which == 1) {
        daiToken.transferFrom(e, a, b, x);
    } else if (which == 2) {
        daiToken.approve(e, a, x);
    } else if (which == 3) {
        daiToken.increaseAllowance(e, a, x);
    } else if (which == 4) {
        daiToken.decreaseAllowance(e, a, x);
    } else if (which == 5) {
        daiToken.mint(e, a, x);
    } else if (which == 6) {
        daiToken.burn(e, a, x);
    } else if (which == 7) {
        daiToken.rely(e, a);
    } else if (which == 8) {
        daiToken.deny(e, a);
    } else if (which == 9) {
        daiToken.permit(e, a, b, x, deadline, signature);
    } else {
        daiToken.permit(e, a, b, x, deadline, v, r, s);
    }

    assert to_mathint(daiToken.totalSupply()) == sumDaiBalances, "DAI totalSupply != sum of balances";
}
