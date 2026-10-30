// ERC4626 vault component of Savings Dai (sDAI).
// Scene / links / aliases (savingsDai, potHarness, vatMock, daiJoinMock, daiMock): defined in invariants.spec (inlined
// call-resolution block). rpow is summarized by ONE uninterpreted function rpowG
// (summaries/rpow_summary.spec), shared by sDAI's views and Pot.drip.
import "invariants.spec";

methods {
    // Pot getters (pie, Pie, chi are already declared in invariants.spec)
    function PotHarness.rho() external returns (uint256) envfree;
    function PotHarness.dsr() external returns (uint256) envfree;
    // Dai balances
    function DaiMock.balanceOf(address) external returns (uint256) envfree;
    // sDAI views that read no environment
    function maxRedeem(address) external returns (uint256) envfree;
}


// =========================================================================================================
// Helpers
// =========================================================================================================

definition isDeposit(method f) returns bool =
    f.selector == sig:deposit(uint256,address).selector
    || f.selector == sig:deposit(uint256,address,uint16).selector;
definition isMint(method f) returns bool =
    f.selector == sig:mint(uint256,address).selector
    || f.selector == sig:mint(uint256,address,uint16).selector;
definition isAction(method f) returns bool =
    isDeposit(f) || isMint(f)
    || f.selector == sig:withdraw(uint256,address,address).selector
    || f.selector == sig:redeem(uint256,address,address).selector;

// The accumulator the Pot will hold after drip() in block `now`, computed from the CURRENT Pot state with the
// same uninterpreted rpowG that both Pot.drip and sDAI's views use (mainnet Pot.drip:
// chi' = rpow(dsr, now - rho) * chi / RAY when now > rho; drip is not called otherwise).
function accruedChi(uint256 now) returns mathint {
    uint256 rho = potHarness.rho();
    uint256 chi = potHarness.chi();
    if (now > rho) {
        return rpowG(potHarness.dsr(), assert_uint256(now - rho)) * chi / RAY();
    }
    return chi;
}

// ceil(x / y) for x >= 0, y > 0
function ceilDiv(mathint x, mathint y) returns mathint {
    return (x + y - 1) / y;
}

// Both deposit overloads (the referral one only adds an event).
function callDeposit(env e, bool withReferral, uint16 referral, uint256 assets, address receiver) returns uint256 {
    if (withReferral) {
        return deposit(e, assets, receiver, referral);
    }
    return deposit(e, assets, receiver);
}

function callMint(env e, bool withReferral, uint16 referral, uint256 shares, address receiver) returns uint256 {
    if (withReferral) {
        return mint(e, shares, receiver, referral);
    }
    return mint(e, shares, receiver);
}

// Calls f with explicit parties: every sDAI method that names a share receiver or a share owner gets them
// from the rule; every other method (approve, permit, allowance changes, views) runs with arbitrary calldata.
function callWithParties(method f, env e, address receiver, address owner) {
    uint256 amount;
    uint16 referral;
    if (f.selector == sig:deposit(uint256,address).selector) {
        deposit(e, amount, receiver);
    } else if (f.selector == sig:deposit(uint256,address,uint16).selector) {
        deposit(e, amount, receiver, referral);
    } else if (f.selector == sig:mint(uint256,address).selector) {
        mint(e, amount, receiver);
    } else if (f.selector == sig:mint(uint256,address,uint16).selector) {
        mint(e, amount, receiver, referral);
    } else if (f.selector == sig:withdraw(uint256,address,address).selector) {
        withdraw(e, amount, receiver, owner);
    } else if (f.selector == sig:redeem(uint256,address,address).selector) {
        redeem(e, amount, receiver, owner);
    } else if (f.selector == sig:transfer(address,uint256).selector) {
        transfer(e, receiver, amount);
    } else if (f.selector == sig:transferFrom(address,address,uint256).selector) {
        transferFrom(e, owner, receiver, amount);
    } else {
        calldataarg args;
        f(e, args);
    }
}

// sDAI share accounting is sound: balances sum to totalSupply (bounds the unchecked += / -= in _mint/_burn)
// and totalSupply equals the Pot pie of sDAI.
function requireShareAccounting() {
    requireInvariant totalSupplyEqualsSumOfBalances();
    requireInvariant sharesEqualPotPie();
    requireInvariant potTotalPieEqualsSumOfPie();
    requireInvariant potTotalPieCoversSdaiPie();
}

// =========================================================================================================
// deposit_effects_exact / mint_effects_exact / withdraw_effects_exact / redeem_effects_exact
// (also the "amount uses the post-drip chi" half of actions_price_at_accrued_rate)
// =========================================================================================================

rule depositEffectsExact(env e, uint256 assets, address receiver, address other, address daiOther,
                         bool withReferral, uint16 referral) {
    requireShareAccounting();
    // DAI sum (bounds the unchecked `balanceOf[to] += value` in Dai.transferFrom).
    requireInvariant daiTotalSupplyEqualsSumOfDaiBalances();
    address caller = e.msg.sender;
    require other != receiver, "other is a share holder distinct from the receiver";
    require daiOther != caller, "daiOther is a DAI holder distinct from the caller";

    mathint callerDaiBefore = daiMock.balanceOf(caller);
    mathint daiOtherBefore  = daiMock.balanceOf(daiOther);
    mathint receiverBefore  = balanceOf(receiver);
    mathint otherBefore     = balanceOf(other);
    mathint supplyBefore    = totalSupply();
    mathint pieBefore       = potHarness.pie(savingsDai);

    uint256 shares = callDeposit(e, withReferral, referral, assets, receiver);

    mathint chi = potHarness.chi();     // post-drip accumulator
    assert shares == assets * RAY() / chi, "shares = floor(assets * RAY / chi)";
    assert daiMock.balanceOf(caller) == callerDaiBefore - assets, "exactly assets DAI taken from caller";
    assert daiMock.balanceOf(daiOther) == daiOtherBefore, "no other DAI balance changes (incl. sDAI's own)";
    assert balanceOf(receiver) == receiverBefore + shares, "receiver gets shares";
    assert balanceOf(other) == otherBefore, "no other share balance changes";
    assert totalSupply() == supplyBefore + shares, "totalSupply grows by shares";
    assert potHarness.pie(savingsDai) == pieBefore + shares, "sDAI's Pot pie grows by shares";
}

rule mintEffectsExact(env e, uint256 shares, address receiver, address other, address daiOther,
                      bool withReferral, uint16 referral) {
    requireShareAccounting();
    requireInvariant daiTotalSupplyEqualsSumOfDaiBalances();
    address caller = e.msg.sender;
    require other != receiver, "other is a share holder distinct from the receiver";
    require daiOther != caller, "daiOther is a DAI holder distinct from the caller";

    mathint callerDaiBefore = daiMock.balanceOf(caller);
    mathint daiOtherBefore  = daiMock.balanceOf(daiOther);
    mathint receiverBefore  = balanceOf(receiver);
    mathint otherBefore     = balanceOf(other);
    mathint supplyBefore    = totalSupply();
    mathint pieBefore       = potHarness.pie(savingsDai);

    uint256 assets = callMint(e, withReferral, referral, shares, receiver);

    mathint chi = potHarness.chi();
    assert assets == ceilDiv(shares * chi, RAY()), "assets = ceil(shares * chi / RAY)";
    assert daiMock.balanceOf(caller) == callerDaiBefore - assets, "exactly assets DAI taken from caller";
    assert daiMock.balanceOf(daiOther) == daiOtherBefore, "no other DAI balance changes (incl. sDAI's own)";
    assert balanceOf(receiver) == receiverBefore + shares, "receiver gets exactly shares";
    assert balanceOf(other) == otherBefore, "no other share balance changes";
    assert totalSupply() == supplyBefore + shares, "totalSupply grows by shares";
    assert potHarness.pie(savingsDai) == pieBefore + shares, "sDAI's Pot pie grows by shares";
}

rule withdrawEffectsExact(env e, uint256 assets, address receiver, address owner, address other,
                          address daiOther) {
    requireShareAccounting();
    requireInvariant chiAtLeastRay();
    requireInvariant daiTotalSupplyEqualsSumOfDaiBalances();
    require other != owner, "other is a share holder distinct from the owner";
    require daiOther != receiver, "daiOther is a DAI holder distinct from the receiver";

    mathint receiverDaiBefore = daiMock.balanceOf(receiver);
    mathint daiOtherBefore    = daiMock.balanceOf(daiOther);
    mathint ownerBefore       = balanceOf(owner);
    mathint otherBefore       = balanceOf(other);
    mathint supplyBefore      = totalSupply();
    mathint pieBefore         = potHarness.pie(savingsDai);

    uint256 shares = withdraw(e, assets, receiver, owner);

    mathint chi = potHarness.chi();
    assert shares == ceilDiv(assets * RAY(), chi), "shares = ceil(assets * RAY / chi)";
    assert daiMock.balanceOf(receiver) == receiverDaiBefore + assets, "receiver gets exactly assets DAI";
    assert daiMock.balanceOf(daiOther) == daiOtherBefore, "no other DAI balance changes";
    assert balanceOf(owner) == ownerBefore - shares, "owner loses shares";
    assert balanceOf(other) == otherBefore, "no other share balance changes";
    assert totalSupply() == supplyBefore - shares, "totalSupply shrinks by shares";
    assert potHarness.pie(savingsDai) == pieBefore - shares, "sDAI's Pot pie shrinks by shares";
}

rule redeemEffectsExact(env e, uint256 shares, address receiver, address owner, address other,
                        address daiOther) {
    requireShareAccounting();
    requireInvariant daiTotalSupplyEqualsSumOfDaiBalances();
    require other != owner, "other is a share holder distinct from the owner";
    require daiOther != receiver, "daiOther is a DAI holder distinct from the receiver";

    mathint receiverDaiBefore = daiMock.balanceOf(receiver);
    mathint daiOtherBefore    = daiMock.balanceOf(daiOther);
    mathint ownerBefore       = balanceOf(owner);
    mathint otherBefore       = balanceOf(other);
    mathint supplyBefore      = totalSupply();
    mathint pieBefore         = potHarness.pie(savingsDai);

    uint256 assets = redeem(e, shares, receiver, owner);

    mathint chi = potHarness.chi();
    assert assets == shares * chi / RAY(), "assets = floor(shares * chi / RAY)";
    assert daiMock.balanceOf(receiver) == receiverDaiBefore + assets, "receiver gets exactly assets DAI";
    assert daiMock.balanceOf(daiOther) == daiOtherBefore, "no other DAI balance changes";
    assert balanceOf(owner) == ownerBefore - shares, "owner loses exactly shares";
    assert balanceOf(other) == otherBefore, "no other share balance changes";
    assert totalSupply() == supplyBefore - shares, "totalSupply shrinks by shares";
    assert potHarness.pie(savingsDai) == pieBefore - shares, "sDAI's Pot pie shrinks by shares";
}

// =========================================================================================================
// rounding_favors_vault: no sDAI method decreases the internal Vat dai held by sDAI.
// =========================================================================================================
rule vaultVatDaiNeverDecreases(method f, env e, calldataarg args) {
    mathint before = vatMock.dai(savingsDai);
    f(e, args);
    assert vatMock.dai(savingsDai) >= before, "sDAI's internal Vat dai never decreases";
}

// =========================================================================================================
// round_trip_no_profit (same block: e1 and e2 have the same timestamp)
// =========================================================================================================
rule depositThenRedeemNoProfit(env e1, env e2, uint256 assets, address shareReceiver, address daiReceiver) {
    require e2.block.timestamp == e1.block.timestamp, "same block";
    uint256 shares = deposit(e1, assets, shareReceiver);
    uint256 assetsOut = redeem(e2, shares, daiReceiver, shareReceiver);
    assert assetsOut <= assets, "redeeming freshly minted shares returns at most the deposit";
}

rule mintThenWithdrawNoProfit(env e1, env e2, uint256 shares, address shareReceiver, address daiReceiver) {
    require e2.block.timestamp == e1.block.timestamp, "same block";
    requireInvariant chiAtLeastRay();
    uint256 assetsPaid = mint(e1, shares, shareReceiver);
    uint256 sharesBurned = withdraw(e2, assetsPaid, daiReceiver, shareReceiver);
    assert sharesBurned >= shares, "withdrawing what mint charged burns at least the minted shares";
}

// =========================================================================================================
// preview_matches_action: same env, same state
// =========================================================================================================
rule previewDepositMatchesDeposit(env e, uint256 assets, address receiver, bool withReferral, uint16 referral) {
    uint256 preview = previewDeposit(e, assets);
    uint256 shares = callDeposit(e, withReferral, referral, assets, receiver);
    assert preview == shares;
}

rule previewMintMatchesMint(env e, uint256 shares, address receiver, bool withReferral, uint16 referral) {
    uint256 preview = previewMint(e, shares);
    uint256 assets = callMint(e, withReferral, referral, shares, receiver);
    assert preview == assets;
}

rule previewWithdrawMatchesWithdraw(env e, uint256 assets, address receiver, address owner) {
    uint256 preview = previewWithdraw(e, assets);
    uint256 shares = withdraw(e, assets, receiver, owner);
    assert preview == shares;
}

rule previewRedeemMatchesRedeem(env e, uint256 shares, address receiver, address owner) {
    uint256 preview = previewRedeem(e, shares);
    uint256 assets = redeem(e, shares, receiver, owner);
    assert preview == assets;
}

// =========================================================================================================
// actions_price_at_accrued_rate: every action drips the Pot to the current block first.
// (The amount is checked against the post-call chi in the four *EffectsExact rules.)
// =========================================================================================================
rule actionsDripToCurrentBlock(method f, env e, calldataarg args) filtered { f -> isAction(f) } {
    uint256 now = e.block.timestamp;
    mathint rhoBefore = potHarness.rho();
    mathint expectedChi = accruedChi(now);

    f(e, args);

    // rho is only ever set to a block timestamp, so rho <= now in every reachable state; the implication
    // states the property without assuming that.
    assert rhoBefore <= now => potHarness.rho() == now, "Pot dripped to the current block";
    assert potHarness.chi() == expectedChi, "chi after the call is the accrued chi of the pre-state";
}

// =========================================================================================================
// third_party_value_unaffected: same block, any sDAI method.
// =========================================================================================================
rule thirdPartyValueUnaffected(method f, env e, address receiver, address owner, address u) {
    require u != e.msg.sender && u != receiver && u != owner, "u is a third party of the call";
    uint256 balBefore = balanceOf(u);
    mathint valueBefore = convertToAssets(e, balBefore);

    callWithParties(f, e, receiver, owner);

    uint256 balAfter = balanceOf(u);
    assert balAfter == balBefore, "third party's shares unchanged";
    assert convertToAssets(e, balAfter) == valueBefore, "third party's DAI value unchanged";
}

// =========================================================================================================
// share_price_independent_of_donations
// =========================================================================================================
rule daiDonationDoesNotMovePrice(env e, env eDonor, uint256 x, uint256 assets, uint256 shares) {
    mathint toSharesBefore = convertToShares(e, assets);
    mathint toAssetsBefore = convertToAssets(e, shares);
    mathint totalAssetsBefore = totalAssets(e);

    daiMock.transfer(eDonor, savingsDai, x);

    assert convertToShares(e, assets) == toSharesBefore;
    assert convertToAssets(e, shares) == toAssetsBefore;
    assert totalAssets(e) == totalAssetsBefore;
}

rule vatDaiDonationDoesNotMovePrice(env e, env eDonor, address src, uint256 rad, uint256 assets, uint256 shares) {
    mathint toSharesBefore = convertToShares(e, assets);
    mathint toAssetsBefore = convertToAssets(e, shares);
    mathint totalAssetsBefore = totalAssets(e);

    vatMock.move(eDonor, src, savingsDai, rad);

    assert convertToShares(e, assets) == toSharesBefore;
    assert convertToAssets(e, shares) == toAssetsBefore;
    assert totalAssets(e) == totalAssetsBefore;
}

rule daiJoinDonationDoesNotMovePrice(env e, env eDonor, uint256 wad, uint256 assets, uint256 shares) {
    mathint toSharesBefore = convertToShares(e, assets);
    mathint toAssetsBefore = convertToAssets(e, shares);
    mathint totalAssetsBefore = totalAssets(e);

    daiJoinMock.join(eDonor, savingsDai, wad);

    assert convertToShares(e, assets) == toSharesBefore;
    assert convertToAssets(e, shares) == toAssetsBefore;
    assert totalAssets(e) == totalAssetsBefore;
}

// =========================================================================================================
// share_price_never_decreases (precondition dsr >= RAY is part of the property)
// =========================================================================================================
rule chiNeverDecreases(method f, env e, calldataarg args) {
    require potHarness.dsr() >= RAY(), "property precondition: savings rate dsr >= RAY";
    mathint chiBefore = potHarness.chi();
    f(e, args);
    assert potHarness.chi() >= chiBefore, "the Pot accumulator never decreases";
}

// =========================================================================================================
// deposit_pulls_only_from_caller: no sDAI method decreases the DAI balance of anyone but the caller.
// u == savingsDai is deliberately NOT excluded: deposit routes DAI through sDAI's own balance
// (transferFrom into sDAI, then DaiJoin burns it from sDAI), and the net change must still be >= 0.
// =========================================================================================================
rule onlyCallerDaiDecreases(method f, env e, calldataarg args, address u) {
    // Bounds the unchecked `balanceOf[to] += value` in Dai.transferFrom / Dai.mint.
    requireInvariant daiTotalSupplyEqualsSumOfDaiBalances();
    require u != e.msg.sender, "u is not the caller";
    mathint before = daiMock.balanceOf(u);
    f(e, args);
    assert daiMock.balanceOf(u) >= before, "DAI of a non-caller never decreases";
}

// =========================================================================================================
// Liveness (redeem_always_possible, max_functions_accurate)
// =========================================================================================================

// The sound-Maker-system assumptions under which an exit through sDAI must succeed. Each bare require is
// justified in place; requireInvariant's are proven in invariants.spec (the two Maker-side solvency invariants
// under trusted governance and with PotHarness.setYield never called, a mock-only function).
function requireSoundMakerSystem() {
    requireShareAccounting();
    requireInvariant daiTotalSupplyEqualsSumOfDaiBalances();
    requireInvariant sdaiSetupPermissionsPersist();
    requireInvariant potVatDaiCoversSavings();
    requireInvariant daiJoinVatDaiCoversDaiSupply();
    require vatMock.wards[potHarness] == 1,
        "Maker deployment: the Pot is a Vat ward (drip calls vat.suck); trusted governance never denies it";
    require daiMock.wards[daiJoinMock] == 1,
        "Maker deployment: DaiJoin is a Dai ward (exit calls dai.mint); trusted governance never denies it";
    require potHarness.dsr() >= RAY(),
        "trusted governance: dsr >= RAY (a lower dsr makes even mainnet Pot.drip revert at tmp - chi; cage sets dsr = RAY)";
}

// drip() in block `now` does not overflow. Only needed when now > rho (otherwise sDAI does not call drip).
function requireDripNoOverflow(uint256 now) {
    uint256 rho = potHarness.rho();
    uint256 chi = potHarness.chi();
    if (now > rho) {
        mathint z = rpowG(potHarness.dsr(), assert_uint256(now - rho));
        require z * chi <= max_uint256,
            "rate accumulation does not overflow: the rpow summary drops the real rpow's overflow reverts, and drip's rpow(dsr, dt) * chi is a checked multiplication";
        mathint rad = potHarness.Pie() * (z * chi / RAY() - chi);
        require rad <= max_uint256, "rate accumulation does not overflow: drip's Pie * (chi' - chi)";
        require vatMock.dai[potHarness] + rad <= max_uint256, "Vat accounting does not overflow (vat.suck dai[pot])";
        require vatMock.sin[potHarness.vow] + rad <= max_uint256, "Vat accounting does not overflow (vat.suck sin[vow])";
        require vatMock.vice + rad <= max_uint256, "Vat accounting does not overflow (vat.suck vice)";
        require vatMock.debt + rad <= max_uint256, "Vat accounting does not overflow (vat.suck debt)";
    }
}

// The two Vat credits of an exit of `shares` (pot.exit -> dai[sDAI], daiJoin.exit -> dai[daiJoin]) do not overflow.
function requireExitNoOverflow(uint256 now, uint256 shares) {
    mathint chi = accruedChi(now);
    require vatMock.dai[savingsDai] + chi * shares <= max_uint256,
        "Vat accounting does not overflow (pot.exit credits sDAI)";
    require vatMock.dai[daiJoinMock] + RAY() * (shares * chi / RAY()) <= max_uint256,
        "Vat accounting does not overflow (daiJoin.exit credits DaiJoin)";
}

function requireValidExit(env e, address receiver) {
    require e.msg.value == 0, "redeem/withdraw are non-payable";
    require receiver != 0 && receiver != daiMock, "valid DAI receiver (Dai.mint rejects 0 and the token itself)";
}

rule redeemAlwaysPossible(env e, uint256 shares, address receiver) {
    address owner = e.msg.sender;
    require shares <= balanceOf(owner), "redeem at most the holder's balance";
    requireValidExit(e, receiver);
    requireSoundMakerSystem();
    requireDripNoOverflow(e.block.timestamp);
    requireExitNoOverflow(e.block.timestamp, shares);

    redeem@withrevert(e, shares, receiver, owner);
    assert !lastReverted, "a holder can always redeem up to its balance";
}

rule maxRedeemIsBalance(address owner) {
    assert maxRedeem(owner) == balanceOf(owner);
}

rule maxRedeemSucceeds(env e, address receiver) {
    address owner = e.msg.sender;
    uint256 shares = maxRedeem(owner);
    requireValidExit(e, receiver);
    requireSoundMakerSystem();
    requireDripNoOverflow(e.block.timestamp);
    requireExitNoOverflow(e.block.timestamp, shares);

    redeem@withrevert(e, shares, receiver, owner);
    assert !lastReverted, "redeem(maxRedeem(owner)) succeeds";
}

rule maxWithdrawSucceeds(env e, address receiver) {
    address owner = e.msg.sender;
    uint256 balance = balanceOf(owner);
    requireValidExit(e, receiver);
    requireSoundMakerSystem();
    requireDripNoOverflow(e.block.timestamp);
    // withdraw burns at most `balance` shares and pays out at most convertToAssets(balance)
    requireExitNoOverflow(e.block.timestamp, balance);
    uint256 assets = maxWithdraw(e, owner);

    uint256 burned = withdraw@withrevert(e, assets, receiver, owner);
    bool reverted = lastReverted;
    assert !reverted, "withdraw(maxWithdraw(owner)) succeeds";
    assert !reverted => burned <= balance, "and burns no more than the owner's balance";
}

// ERC-4626: maxDeposit/maxMint "MUST NOT be higher than the actual maximum that would be accepted" and assume
// the user has unlimited assets. The unlimited-DAI caller is modeled by requiring a caller balance/allowance of
// at least the amount; the DAI-supply invariants are deliberately NOT required (with them a balance of
// maxDeposit = 2^256-1 is infeasible and the rule would be vacuous).
function requireCanEnter(env e, address receiver, uint256 daiNeeded) {
    require e.msg.value == 0, "deposit/mint are non-payable";
    require receiver != 0 && receiver != savingsDai, "valid share receiver (sDAI._mint rejects 0 and itself)";
    require e.msg.sender != savingsDai, "sDAI never originates a top-level call";
    require daiMock.balanceOf(e.msg.sender) >= daiNeeded, "ERC-4626 maxDeposit/maxMint: caller has unlimited DAI";
    require daiMock.allowance(e.msg.sender, savingsDai) == max_uint256, "caller approved sDAI";
    require potHarness.rho() <= e.block.timestamp,
        "rho is only ever written with block.timestamp (Pot constructor / drip) and time is monotone";
    requireInvariant chiAtLeastRay();
    requireInvariant sdaiSetupPermissionsPersist();
    require vatMock.wards[potHarness] == 1,
        "Maker deployment: the Pot is a Vat ward (drip calls vat.suck); trusted governance never denies it";
    require potHarness.dsr() >= RAY(),
        "trusted governance: dsr >= RAY (a lower dsr makes even mainnet Pot.drip revert)";
}

rule maxDepositAccepted(env e, address receiver) {
    uint256 assets = maxDeposit(e, receiver);
    requireCanEnter(e, receiver, assets);
    requireDripNoOverflow(e.block.timestamp);

    deposit@withrevert(e, assets, receiver);
    assert !lastReverted, "deposit(maxDeposit(receiver)) is accepted";
}

// Precondition-free witnesses for the two genuine issues above: deposit/mint of the advertised maximum revert in
// EVERY state (mint: every state with chi >= RAY, proven in invariants.spec), independent of any entry precondition.
rule maxDepositAlwaysReverts(env e, address receiver) {
    uint256 a = maxDeposit(e, receiver);
    deposit@withrevert(e, a, receiver);
    assert lastReverted, "deposit(maxDeposit(receiver)) always reverts (assets * RAY overflows)";
}

rule maxMintAlwaysReverts(env e, address receiver) {
    requireInvariant chiAtLeastRay();
    uint256 s = maxMint(e, receiver);
    mint@withrevert(e, s, receiver);
    assert lastReverted, "mint(maxMint(receiver)) always reverts (shares * chi overflows)";
}

rule maxMintAccepted(env e, address receiver) {
    uint256 shares = maxMint(e, receiver);
    requireCanEnter(e, receiver, max_uint256);
    requireDripNoOverflow(e.block.timestamp);

    mint@withrevert(e, shares, receiver);
    assert !lastReverted, "mint(maxMint(receiver)) is accepted";
}

// Reachability witness: the drip branch (now > rho) of the actions is reachable and leaves rho == now.
rule actionDripBranchReachable(env e, uint256 shares, address receiver, address owner) {
    uint256 rhoBefore = potHarness.rho();
    redeem(e, shares, receiver, owner);
    satisfy e.block.timestamp > rhoBefore && potHarness.rho() == e.block.timestamp
        && potHarness.chi() != 0 && shares > 0;
}
