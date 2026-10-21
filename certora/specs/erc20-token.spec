import "summaries/SavingsDai_base_summaries.spec";
import "summaries/SavingsDai_call_resolution.spec";
import "scene.spec";
import "invariants.spec";

/*
 * ERC20 share-token behaviour of SavingsDai (component slug: erc20-token).
 * Properties: certora/properties/erc20-token.properties.json
 *
 * Every SavingsDai function is non-payable, so a call with e.msg.value != 0 reverts. The revert
 * characterisation rules put `e.msg.value != 0` INTO the iff predicate instead of requiring
 * it away, so no bare require is used in them.
 */

methods {
    function allowance(address, address) external returns (uint256) envfree;
}

definition MAX_UINT() returns uint256 = max_uint256;

// ---------------------------------------------------------------------------
// Method identification
// ---------------------------------------------------------------------------

definition isDeposit(method f) returns bool =
    f.selector == sig:deposit(uint256,address).selector ||
    f.selector == sig:deposit(uint256,address,uint16).selector;

definition isMint(method f) returns bool =
    f.selector == sig:mint(uint256,address).selector ||
    f.selector == sig:mint(uint256,address,uint16).selector;

definition isWithdrawOrRedeem(method f) returns bool =
    f.selector == sig:withdraw(uint256,address,address).selector ||
    f.selector == sig:redeem(uint256,address,address).selector;

definition isPermit(method f) returns bool =
    f.selector == sig:permit(address,address,uint256,uint256,bytes).selector ||
    f.selector == sig:permit(address,address,uint256,uint256,uint8,bytes32,bytes32).selector;

definition isApprove(method f) returns bool =
    f.selector == sig:approve(address,uint256).selector;

definition isIncreaseAllowance(method f) returns bool =
    f.selector == sig:increaseAllowance(address,uint256).selector;

definition isDecreaseAllowance(method f) returns bool =
    f.selector == sig:decreaseAllowance(address,uint256).selector;

definition isTransfer(method f) returns bool =
    f.selector == sig:transfer(address,uint256).selector;

definition isTransferFrom(method f) returns bool =
    f.selector == sig:transferFrom(address,address,uint256).selector;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/*
 * Calls f with its address/amount arguments bound to the explicit CVL values a1, a2, x so that
 * rules can refer to "the address arguments of the call". All remaining arguments (referral,
 * deadline, signature) are unconstrained, so every behaviour of every method is still covered;
 * methods with no address argument (views) are called with arbitrary calldata.
 *
 *   transfer(to=a1, x)                     transferFrom(from=a1, to=a2, x)
 *   approve/increase/decreaseAllowance(spender=a1, x)
 *   deposit/mint(x, receiver=a1 [,ref])    withdraw/redeem(x, receiver=a1, owner=a2)
 *   permit(owner=a1, spender=a2, value=x, deadline, sig | v,r,s)
 */
function callWithArgs(env e, method f, address a1, address a2, uint256 x) {
    if (isTransfer(f)) {
        transfer(e, a1, x);
    } else if (isTransferFrom(f)) {
        transferFrom(e, a1, a2, x);
    } else if (isApprove(f)) {
        approve(e, a1, x);
    } else if (isIncreaseAllowance(f)) {
        increaseAllowance(e, a1, x);
    } else if (isDecreaseAllowance(f)) {
        decreaseAllowance(e, a1, x);
    } else if (f.selector == sig:deposit(uint256,address).selector) {
        deposit(e, x, a1);
    } else if (f.selector == sig:deposit(uint256,address,uint16).selector) {
        uint16 ref1;
        deposit(e, x, a1, ref1);
    } else if (f.selector == sig:mint(uint256,address).selector) {
        mint(e, x, a1);
    } else if (f.selector == sig:mint(uint256,address,uint16).selector) {
        uint16 ref2;
        mint(e, x, a1, ref2);
    } else if (f.selector == sig:withdraw(uint256,address,address).selector) {
        withdraw(e, x, a1, a2);
    } else if (f.selector == sig:redeem(uint256,address,address).selector) {
        redeem(e, x, a1, a2);
    } else if (f.selector == sig:permit(address,address,uint256,uint256,bytes).selector) {
        uint256 deadline1;
        bytes signature;
        permit(e, a1, a2, x, deadline1, signature);
    } else if (f.selector == sig:permit(address,address,uint256,uint256,uint8,bytes32,bytes32).selector) {
        uint256 deadline2;
        uint8 v;
        bytes32 r;
        bytes32 s;
        permit(e, a1, a2, x, deadline2, v, r, s);
    } else {
        calldataarg args;
        f(e, args);
    }
    return;
}

/// u is one of the balance-holder address arguments of f named by the property
/// (from/to/receiver/owner), as bound by callWithArgs. Spenders are deliberately NOT exempt.
function isAddressArg(method f, address u, address a1, address a2) returns bool {
    if (isTransfer(f) || isDeposit(f) || isMint(f)) {
        return u == a1;                 // to / receiver
    }
    if (isTransferFrom(f) || isWithdrawOrRedeem(f)) {
        return u == a1 || u == a2;      // from, to / receiver, owner
    }
    if (isPermit(f)) {
        return u == a1;                 // owner only (not the spender a2)
    }
    return false;                       // approve family: spender is not exempt; views
}

/*
 * Bare-require justification: totalSupplyIsSumOfBalances() (proven) states
 * totalSupply == sum over ALL addresses of balanceOf. Every term is a non-negative uint256, so
 * for two DISTINCT addresses a, b: balanceOf(a) + balanceOf(b) <= totalSupply. The proven
 * invariant's ghost only bounds a single balance by the sum (Sload hook), so this two-term
 * consequence is stated here explicitly. It is a pure arithmetic consequence of the proven
 * invariant, not an extra assumption about reachable states.
 */
function requireTwoBalancesBounded(address a, address b) {
    requireInvariant totalSupplyIsSumOfBalances();
    require a != b => balanceOf(a) + balanceOf(b) <= to_mathint(totalSupply());
    return;
}

// ---------------------------------------------------------------------------
// transfer
// ---------------------------------------------------------------------------

/// transfer_moves_exact_amount
rule transferMovesExactAmount(env e, address to, uint256 v, address other) {
    address sender = e.msg.sender;
    requireTwoBalancesBounded(sender, to);

    mathint senderBefore = balanceOf(sender);
    mathint toBefore = balanceOf(to);
    mathint otherBefore = balanceOf(other);
    mathint supplyBefore = totalSupply();

    bool ret = transfer(e, to, v);

    assert ret, "transfer must return true";
    assert sender != to => balanceOf(sender) == senderBefore - v, "sender balance must drop by v";
    assert sender != to => balanceOf(to) == toBefore + v, "recipient balance must grow by v";
    assert sender == to => balanceOf(sender) == senderBefore, "self-transfer must not change balance";
    assert (other != sender && other != to) => balanceOf(other) == otherBefore, "third-party balance changed";
    assert totalSupply() == supplyBefore, "totalSupply changed";
}

/// transfer_revert_conditions
rule transferRevertConditions(env e, address to, uint256 v) {
    requireInvariant totalSupplyIsSumOfBalances();
    mathint senderBal = balanceOf(e.msg.sender);

    transfer@withrevert(e, to, v);
    bool reverted = lastReverted;

    assert reverted <=> (
        e.msg.value != 0 ||               // non-payable
        to == 0 ||
        to == currentContract ||
        senderBal < to_mathint(v)
    );
}

// ---------------------------------------------------------------------------
// transferFrom
// ---------------------------------------------------------------------------

/// transferFrom_moves_exact_amount_and_spends_allowance
rule transferFromMovesExactAmountAndSpendsAllowance(env e, address from, address to, uint256 v,
                                                    address other, address otherSpender) {
    address sender = e.msg.sender;
    requireTwoBalancesBounded(from, to);

    mathint fromBefore = balanceOf(from);
    mathint toBefore = balanceOf(to);
    mathint otherBefore = balanceOf(other);
    mathint supplyBefore = totalSupply();
    mathint allowBefore = allowance(from, sender);
    mathint otherAllowBefore = allowance(from, otherSpender);

    bool ret = transferFrom(e, from, to, v);

    assert ret, "transferFrom must return true";
    assert from != to => balanceOf(from) == fromBefore - v, "from balance must drop by v";
    assert from != to => balanceOf(to) == toBefore + v, "to balance must grow by v";
    assert from == to => balanceOf(from) == fromBefore, "self-transfer must not change balance";
    assert (other != from && other != to) => balanceOf(other) == otherBefore, "third-party balance changed";
    assert totalSupply() == supplyBefore, "totalSupply changed";
    assert (sender != from && allowBefore != to_mathint(MAX_UINT())) =>
        allowance(from, sender) == allowBefore - v, "finite allowance must drop by exactly v";
    assert (sender == from || allowBefore == to_mathint(MAX_UINT())) =>
        allowance(from, sender) == allowBefore, "self-spend / infinite allowance must be unchanged";
    assert otherSpender != sender => allowance(from, otherSpender) == otherAllowBefore, "unrelated allowance changed";
}

/// transferFrom_revert_conditions
rule transferFromRevertConditions(env e, address from, address to, uint256 v) {
    requireInvariant totalSupplyIsSumOfBalances();
    address sender = e.msg.sender;
    mathint fromBal = balanceOf(from);
    mathint allowed = allowance(from, sender);

    transferFrom@withrevert(e, from, to, v);
    bool reverted = lastReverted;

    assert reverted <=> (
        e.msg.value != 0 ||               // non-payable
        to == 0 ||
        to == currentContract ||
        fromBal < to_mathint(v) ||
        (sender != from && allowed != to_mathint(MAX_UINT()) && allowed < to_mathint(v))
    );
}

// ---------------------------------------------------------------------------
// approve / increaseAllowance / decreaseAllowance
// ---------------------------------------------------------------------------

/// approve_and_allowance_adjustments_are_exact
rule approveIsExact(env e, address spender, uint256 v, address o, address s, address u) {
    address sender = e.msg.sender;
    mathint otherAllowBefore = allowance(o, s);
    mathint balBefore = balanceOf(u);

    bool ret = approve@withrevert(e, spender, v);
    bool reverted = lastReverted;

    assert reverted <=> e.msg.value != 0, "approve reverts only on ETH sent";
    assert !reverted => ret, "approve must return true";
    assert !reverted => allowance(sender, spender) == v, "allowance not set to value";
    assert (o != sender || s != spender) => allowance(o, s) == otherAllowBefore, "other allowance changed";
    assert balanceOf(u) == balBefore, "balance changed";
}

/// approve_and_allowance_adjustments_are_exact
rule increaseAllowanceIsExact(env e, address spender, uint256 v, address o, address s, address u) {
    address sender = e.msg.sender;
    mathint allowBefore = allowance(sender, spender);
    mathint otherAllowBefore = allowance(o, s);
    mathint balBefore = balanceOf(u);

    bool ret = increaseAllowance@withrevert(e, spender, v);
    bool reverted = lastReverted;

    assert reverted <=> (e.msg.value != 0 || allowBefore + v > to_mathint(MAX_UINT())),
        "increaseAllowance revert condition";
    assert !reverted => ret, "increaseAllowance must return true";
    assert !reverted => allowance(sender, spender) == allowBefore + v, "allowance not increased by value";
    assert (o != sender || s != spender) => allowance(o, s) == otherAllowBefore, "other allowance changed";
    assert balanceOf(u) == balBefore, "balance changed";
}

/// approve_and_allowance_adjustments_are_exact
rule decreaseAllowanceIsExact(env e, address spender, uint256 v, address o, address s, address u) {
    address sender = e.msg.sender;
    mathint allowBefore = allowance(sender, spender);
    mathint otherAllowBefore = allowance(o, s);
    mathint balBefore = balanceOf(u);

    bool ret = decreaseAllowance@withrevert(e, spender, v);
    bool reverted = lastReverted;

    assert reverted <=> (e.msg.value != 0 || allowBefore < to_mathint(v)),
        "decreaseAllowance revert condition";
    assert !reverted => ret, "decreaseAllowance must return true";
    assert !reverted => allowance(sender, spender) == allowBefore - v, "allowance not decreased by value";
    assert (o != sender || s != spender) => allowance(o, s) == otherAllowBefore, "other allowance changed";
    assert balanceOf(u) == balBefore, "balance changed";
}

// ---------------------------------------------------------------------------
// Parametric properties (all SavingsDai methods; parametric_contracts = [SavingsDai])
// ---------------------------------------------------------------------------

/// balance_decrease_requires_owner_or_allowance
rule balanceDecreaseRequiresOwnerOrAllowance(env e, method f, calldataarg args, address account) {
    requireInvariant totalSupplyIsSumOfBalances();
    requireInvariant sharesBackedByPie();
    requireInvariant zeroAndSelfHoldNoShares();

    mathint balBefore = balanceOf(account);
    mathint allowBefore = allowance(account, e.msg.sender);

    f(e, args);

    mathint balAfter = balanceOf(account);

    assert (balAfter < balBefore && e.msg.sender != account) => allowBefore >= balBefore - balAfter,
        "balance of account decreased by a non-owner without sufficient allowance";
}

/// allowance_changes_only_by_authorized_actions
rule allowanceChangesOnlyByAuthorizedActions(env e, method f, address a1, address a2, uint256 x,
                                             address owner, address spender) {
    requireInvariant totalSupplyIsSumOfBalances();
    requireInvariant sharesBackedByPie();
    requireInvariant zeroAndSelfHoldNoShares();
    address sender = e.msg.sender;

    mathint before = allowance(owner, spender);

    callWithArgs(e, f, a1, a2, x);

    mathint after = allowance(owner, spender);

    // The property as stated.
    assert after > before => ((sender == owner && (isApprove(f) || isIncreaseAllowance(f))) || isPermit(f)),
        "allowance increased without owner approval or permit";
    assert after < before => (sender == owner || sender == spender || isPermit(f)),
        "allowance decreased by someone other than owner/spender, not via permit";

    // Precise version: which arguments the changed entry corresponds to.
    assert after > before => (
        (sender == owner && (isApprove(f) || isIncreaseAllowance(f)) && spender == a1) ||
        (isPermit(f) && owner == a1 && spender == a2)
    ), "allowance increase not matching call arguments";
    assert after < before => (
        (sender == owner && (isApprove(f) || isDecreaseAllowance(f)) && spender == a1) ||
        (sender == spender && isTransferFrom(f) && owner == a1) ||
        (sender == spender && isWithdrawOrRedeem(f) && owner == a2) ||
        (isPermit(f) && owner == a1 && spender == a2)
    ), "allowance decrease not matching call arguments";
}

/// third_party_balances_unaffected
rule thirdPartyBalancesUnaffected(env e, method f, address a1, address a2, uint256 x, address u) {
    requireInvariant totalSupplyIsSumOfBalances();
    requireInvariant sharesBackedByPie();
    requireInvariant zeroAndSelfHoldNoShares();

    mathint before = balanceOf(u);

    callWithArgs(e, f, a1, a2, x);

    assert balanceOf(u) != before => (u == e.msg.sender || isAddressArg(f, u, a1, a2)),
        "balance of an uninvolved account changed";
}

/// total_supply_changes_only_via_vault_operations
rule totalSupplyChangesOnlyViaVaultOperations(env e, method f, calldataarg args) {
    requireInvariant totalSupplyIsSumOfBalances();
    requireInvariant sharesBackedByPie();
    requireInvariant zeroAndSelfHoldNoShares();

    mathint before = totalSupply();

    f(e, args);

    mathint after = totalSupply();

    assert after > before => (isDeposit(f) || isMint(f)), "totalSupply increased outside deposit/mint";
    assert after < before => isWithdrawOrRedeem(f), "totalSupply decreased outside withdraw/redeem";
}
