// ERC20 token component of Savings Dai (sDAI).
// Properties: certora/properties/erc20-token.properties.json. Mapping: erc20-token.property_rules.json.
// invariants.spec (judge-accepted, proven over all scene methods in job 1080ee77-78e7-4afb-bb57-8a5da4e46a62)
// provides the aliases, links, shared summaries and the envfree entries for sDAI totalSupply/balanceOf,
// PotHarness.pie, VatMock.dai, ...; they are not repeated here.
import "invariants.spec";

methods {
    function allowance(address, address) external returns (uint256) envfree;
    function DaiMock.balanceOf(address) external returns (uint256) envfree;
}

definition MAX_ALLOWANCE() returns mathint = max_uint256;

definition isPermitBytes(method f) returns bool =
    f.selector == sig:permit(address, address, uint256, uint256, bytes).selector;
definition isPermitVRS(method f) returns bool =
    f.selector == sig:permit(address, address, uint256, uint256, uint8, bytes32, bytes32).selector;

definition isErc20Op(method f) returns bool =
    f.selector == sig:transfer(address, uint256).selector
    || f.selector == sig:transferFrom(address, address, uint256).selector
    || f.selector == sig:approve(address, uint256).selector
    || f.selector == sig:increaseAllowance(address, uint256).selector
    || f.selector == sig:decreaseAllowance(address, uint256).selector;

// =========================================================================================================
// transfer_moves_exact_amount
// =========================================================================================================
rule transferMovesExactAmount(env e, address to, uint256 value, address other) {
    // transfer's `balanceOf[to] += value` is unchecked; with sum(balances) == totalSupply (and the shared
    // "one balance <= sum" load hook) it cannot wrap.
    requireInvariant totalSupplyEqualsSumOfBalances();

    address sender = e.msg.sender;
    mathint balSender = balanceOf(sender);
    mathint balTo     = balanceOf(to);
    mathint balOther  = balanceOf(other);
    mathint supply    = totalSupply();

    bool ret = transfer(e, to, value);

    assert ret, "transfer returns true";
    assert sender != to => balanceOf(sender) == balSender - value, "sender debited by exactly value";
    assert sender != to => balanceOf(to) == balTo + value, "receiver credited by exactly value";
    assert sender == to => balanceOf(sender) == balSender, "self-transfer leaves the balance unchanged";
    assert other != sender && other != to => balanceOf(other) == balOther, "no other balance changes";
    assert totalSupply() == supply, "totalSupply unchanged";
}

// =========================================================================================================
// transfer_from_moves_exact_amount_and_spends_allowance
// =========================================================================================================
rule transferFromMovesExactAmountAndSpendsAllowance(env e, address from, address to, uint256 value, address other) {
    // Same unchecked `balanceOf[to] += value` as in transfer.
    requireInvariant totalSupplyEqualsSumOfBalances();

    address spender = e.msg.sender;
    mathint balFrom  = balanceOf(from);
    mathint balTo    = balanceOf(to);
    mathint balOther = balanceOf(other);
    mathint supply   = totalSupply();
    mathint allowed  = allowance(from, spender);

    bool ret = transferFrom(e, from, to, value);

    assert ret, "transferFrom returns true";
    assert from != to => balanceOf(from) == balFrom - value, "from debited by exactly value";
    assert from != to => balanceOf(to) == balTo + value, "to credited by exactly value";
    assert from == to => balanceOf(from) == balFrom, "self-transfer leaves the balance unchanged";
    assert other != from && other != to => balanceOf(other) == balOther, "no other balance changes";
    assert totalSupply() == supply, "totalSupply unchanged";
    assert (spender != from && allowed != MAX_ALLOWANCE()) => allowance(from, spender) == allowed - value,
        "finite allowance of a third-party spender decreases by exactly value";
    assert (spender == from || allowed == MAX_ALLOWANCE()) => allowance(from, spender) == allowed,
        "infinite allowance or owner-initiated transferFrom leaves the allowance unchanged";
}

// =========================================================================================================
// transfer_revert_conditions
// =========================================================================================================
rule transferRevertConditions(env e, address to, uint256 value) {
    mathint balSender = balanceOf(e.msg.sender);

    transfer@withrevert(e, to, value);

    assert lastReverted <=> (
        e.msg.value != 0
        || to == 0
        || to == currentContract
        || balSender < value
    ), "transfer reverts exactly on non-zero msg.value, invalid receiver or insufficient balance";
}

// =========================================================================================================
// transfer_from_revert_conditions
// =========================================================================================================
rule transferFromRevertConditions(env e, address from, address to, uint256 value) {
    mathint balFrom = balanceOf(from);
    mathint allowed = allowance(from, e.msg.sender);

    transferFrom@withrevert(e, from, to, value);

    assert lastReverted <=> (
        e.msg.value != 0
        || to == 0
        || to == currentContract
        || balFrom < value
        || (e.msg.sender != from && allowed != MAX_ALLOWANCE() && allowed < value)
    ), "transferFrom reverts exactly on non-zero msg.value, invalid receiver, insufficient balance or insufficient allowance";
}

// =========================================================================================================
// balance_decrease_requires_owner_or_allowance  (every SavingsDai method, incl. withdraw/redeem burns)
// =========================================================================================================
rule balanceDecreaseRequiresOwnerOrAllowance(env e, method f, calldataarg args, address account) {
    // _mint adds shares to balanceOf[receiver] unchecked (deposit/mint). sum(balances) == totalSupply ==
    // Pot.pie[sDAI], and Pot.join adds the same shares to pie[sDAI] with checked arithmetic, so the receiver's
    // balance cannot wrap around (which would look like a decrease).
    requireInvariant totalSupplyEqualsSumOfBalances();
    requireInvariant sharesEqualPotPie();

    address caller = e.msg.sender;
    mathint balBefore   = balanceOf(account);
    mathint allowBefore = allowance(account, caller);

    f(e, args);

    mathint balAfter   = balanceOf(account);
    mathint allowAfter = allowance(account, caller);
    mathint decrease   = balBefore - balAfter;

    assert decrease > 0 => (
        caller == account
        || (allowBefore >= decrease
            && (allowBefore == MAX_ALLOWANCE() ? allowAfter == allowBefore : allowAfter == allowBefore - decrease))
    ), "a balance decreases only by its owner, or by a spender whose allowance covers it and is spent exactly";
}

// =========================================================================================================
// allowance_increase_requires_owner_authorization  (every SavingsDai method)
// For the two permit overloads the arguments are made explicit so the assertion can name the (owner, spender)
// pair the permit was issued for; every other method is called with arbitrary calldata.
// =========================================================================================================
rule allowanceChangeRequiresAuthorization(env e, method f, address owner, address spender) {
    address caller = e.msg.sender;

    // Explicit permit arguments (only used when f is a permit overload).
    address pOwner; address pSpender; uint256 pValue; uint256 pDeadline;
    bytes pSig; uint8 pV; bytes32 pR; bytes32 pS;

    mathint allowBefore = allowance(owner, spender);

    if (isPermitBytes(f)) {
        permit(e, pOwner, pSpender, pValue, pDeadline, pSig);
    } else if (isPermitVRS(f)) {
        permit(e, pOwner, pSpender, pValue, pDeadline, pV, pR, pS);
    } else {
        calldataarg args;
        f(e, args);
    }

    mathint allowAfter = allowance(owner, spender);

    bool isPermitForPair = (isPermitBytes(f) || isPermitVRS(f)) && owner == pOwner && spender == pSpender;
    bool isOwnerApproval = caller == owner
        && (f.selector == sig:approve(address, uint256).selector
            || f.selector == sig:increaseAllowance(address, uint256).selector);
    bool isOwnerAllowanceMgmt = caller == owner
        && (f.selector == sig:approve(address, uint256).selector
            || f.selector == sig:increaseAllowance(address, uint256).selector
            || f.selector == sig:decreaseAllowance(address, uint256).selector);
    bool isSpending = caller == spender && allowAfter < allowBefore
        && (f.selector == sig:transferFrom(address, address, uint256).selector
            || f.selector == sig:withdraw(uint256, address, address).selector
            || f.selector == sig:redeem(uint256, address, address).selector);

    assert allowAfter > allowBefore => (isOwnerApproval || isPermitForPair),
        "an allowance increases only by its owner via approve/increaseAllowance, or by a permit for exactly that pair";
    assert allowAfter != allowBefore => (isOwnerAllowanceMgmt || isPermitForPair || isSpending),
        "an allowance changes only via the owner's approve/increaseAllowance/decreaseAllowance, a permit for exactly that pair, or the spender spending it in transferFrom/withdraw/redeem";
}

// =========================================================================================================
// allowance_management_functions_correct
// =========================================================================================================
rule approveCorrect(env e, address spender, uint256 value, address o, address s, address a) {
    address caller = e.msg.sender;
    mathint otherAllow = allowance(o, s);
    mathint bal = balanceOf(a);

    bool ret = approve@withrevert(e, spender, value);
    bool reverted = lastReverted;

    assert reverted <=> e.msg.value != 0, "approve reverts only on non-zero msg.value";
    assert !reverted => ret, "approve returns true";
    assert !reverted => allowance(caller, spender) == value, "approve sets the allowance to value";
    assert !(o == caller && s == spender) => allowance(o, s) == otherAllow, "no other allowance changes";
    assert balanceOf(a) == bal, "no balance changes";
}

rule increaseAllowanceCorrect(env e, address spender, uint256 addedValue, address o, address s, address a) {
    address caller = e.msg.sender;
    mathint allowBefore = allowance(caller, spender);
    mathint otherAllow = allowance(o, s);
    mathint bal = balanceOf(a);

    bool ret = increaseAllowance@withrevert(e, spender, addedValue);
    bool reverted = lastReverted;

    assert reverted <=> (e.msg.value != 0 || allowBefore + addedValue > MAX_ALLOWANCE()),
        "increaseAllowance reverts exactly on non-zero msg.value or overflow";
    assert !reverted => ret, "increaseAllowance returns true";
    assert !reverted => allowance(caller, spender) == allowBefore + addedValue, "adds exactly addedValue";
    assert !(o == caller && s == spender) => allowance(o, s) == otherAllow, "no other allowance changes";
    assert balanceOf(a) == bal, "no balance changes";
}

rule decreaseAllowanceCorrect(env e, address spender, uint256 subtractedValue, address o, address s, address a) {
    address caller = e.msg.sender;
    mathint allowBefore = allowance(caller, spender);
    mathint otherAllow = allowance(o, s);
    mathint bal = balanceOf(a);

    bool ret = decreaseAllowance@withrevert(e, spender, subtractedValue);
    bool reverted = lastReverted;

    assert reverted <=> (e.msg.value != 0 || allowBefore < subtractedValue),
        "decreaseAllowance reverts exactly on non-zero msg.value or when subtractedValue exceeds the allowance";
    assert !reverted => ret, "decreaseAllowance returns true";
    assert !reverted => allowance(caller, spender) == allowBefore - subtractedValue, "subtracts exactly subtractedValue";
    assert !(o == caller && s == spender) => allowance(o, s) == otherAllow, "no other allowance changes";
    assert balanceOf(a) == bal, "no balance changes";
}

// =========================================================================================================
// erc20_ops_preserve_vault_backing
// Scope is the five ERC20 operations named in the property (filter); the vault methods are the subject of the
// erc4626-vault component.
// =========================================================================================================
rule erc20OpsPreserveVaultBacking(env e, method f, calldataarg args, address daiHolder, address vatHolder)
    filtered { f -> isErc20Op(f) }
{
    mathint supply     = totalSupply();
    mathint sdaiPie    = potHarness.pie(savingsDai);
    mathint daiBal     = daiMock.balanceOf(daiHolder);
    mathint vatDai     = vatMock.dai(vatHolder);

    f(e, args);

    assert totalSupply() == supply, "totalSupply unchanged";
    assert potHarness.pie(savingsDai) == sdaiPie, "sDAI's Pot pie unchanged";
    assert daiMock.balanceOf(daiHolder) == daiBal, "no DAI balance changes";
    assert vatMock.dai(vatHolder) == vatDai, "no Vat dai balance changes";
}
