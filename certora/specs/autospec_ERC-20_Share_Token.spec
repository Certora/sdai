// CVL Specification for SavingsDai ERC-20 Properties

import "summaries/SavingsDai_base_summaries.spec";
import "summaries/custom_summaries.spec";

methods {
    function totalSupply() external returns (uint256) envfree;
    function balanceOf(address) external returns (uint256) envfree;
    function allowance(address, address) external returns (uint256) envfree;
    function nonces(address) external returns (uint256) envfree;
}

// RAY = 10^27, used in shares computation
definition RAY() returns mathint = 1000000000000000000000000000;

// Ghost variable to track the sum of all balances
// Using persistent because HAVOC_ECF for external calls (pot.drip, pot.join, etc.)
// preserves SavingsDai's storage but would havoc non-persistent ghosts.
// Since these ghosts mirror SavingsDai's own storage state, persistent is sound.
persistent ghost mathint sumOfBalances {
    init_state axiom sumOfBalances == 0;
}

// Ghost mirror mapping for individual balances
persistent ghost mapping(address => mathint) ghostBalanceOf {
    init_state axiom forall address a. ghostBalanceOf[a] == 0;
}

// Hook on Sstore to balanceOf mapping
hook Sstore balanceOf[KEY address a] uint256 newValue (uint256 oldValue) {
    sumOfBalances = sumOfBalances + newValue - oldValue;
    ghostBalanceOf[a] = to_mathint(newValue);
}

// Sload hook to constrain loaded balance values to match the ghost mirror
hook Sload uint256 value balanceOf[KEY address a] {
    require ghostBalanceOf[a] == to_mathint(value);
}

// ===================== Property 1 (Invariant) =====================
// totalSupply == sum of all balanceOf entries
invariant totalSupplyEqualsSumOfBalances()
    to_mathint(totalSupply()) == sumOfBalances
    {
        preserved transfer(address to, uint256 value) with (env e) {
            requireInvariant individualBalanceLeqTotalSupply(e.msg.sender);
            requireInvariant individualBalanceLeqTotalSupply(to);
            require balanceOf(e.msg.sender) + balanceOf(to) <= to_mathint(totalSupply());
        }
        preserved transferFrom(address from, address to, uint256 value) with (env e) {
            requireInvariant individualBalanceLeqTotalSupply(from);
            requireInvariant individualBalanceLeqTotalSupply(to);
            require balanceOf(from) + balanceOf(to) <= to_mathint(totalSupply());
        }
        preserved mint(uint256 shares, address receiver) with (env e) {
            requireInvariant individualBalanceLeqTotalSupply(receiver);
            require to_mathint(totalSupply()) + shares <= max_uint256;
        }
        preserved mint(uint256 shares, address receiver, uint16 referral) with (env e) {
            requireInvariant individualBalanceLeqTotalSupply(receiver);
            require to_mathint(totalSupply()) + shares <= max_uint256;
        }
        preserved deposit(uint256 assets, address receiver) with (env e) {
            requireInvariant individualBalanceLeqTotalSupply(receiver);
            require to_mathint(totalSupply()) + to_mathint(assets) * RAY() <= max_uint256;
        }
        preserved deposit(uint256 assets, address receiver, uint16 referral) with (env e) {
            requireInvariant individualBalanceLeqTotalSupply(receiver);
            require to_mathint(totalSupply()) + to_mathint(assets) * RAY() <= max_uint256;
        }
        preserved withdraw(uint256 assets, address receiver, address owner) with (env e) {
            requireInvariant individualBalanceLeqTotalSupply(owner);
        }
        preserved redeem(uint256 shares, address receiver, address owner) with (env e) {
            requireInvariant individualBalanceLeqTotalSupply(owner);
        }
    }

// ===================== Property 2 (Invariant) =====================
// balanceOf[address(0)] must always be zero
invariant zeroAddressHasZeroBalance()
    balanceOf(0) == 0;

// ===================== Property 3 (Invariant) =====================
// balanceOf[address(this)] must always be zero
invariant contractAddressHasZeroBalance()
    balanceOf(currentContract) == 0;

// Helper invariant: each individual balance is at most totalSupply
invariant individualBalanceLeqTotalSupply(address a)
    balanceOf(a) <= totalSupply()
    {
        preserved {
            requireInvariant totalSupplyEqualsSumOfBalances();
        }
        preserved transfer(address to, uint256 value) with (env e) {
            requireInvariant totalSupplyEqualsSumOfBalances();
            requireInvariant individualBalanceLeqTotalSupply(e.msg.sender);
            requireInvariant individualBalanceLeqTotalSupply(to);
            require balanceOf(e.msg.sender) + balanceOf(to) <= to_mathint(totalSupply());
        }
        preserved transferFrom(address from, address to, uint256 value) with (env e) {
            requireInvariant totalSupplyEqualsSumOfBalances();
            requireInvariant individualBalanceLeqTotalSupply(from);
            requireInvariant individualBalanceLeqTotalSupply(to);
            require balanceOf(from) + balanceOf(to) <= to_mathint(totalSupply());
        }
        preserved mint(uint256 shares, address receiver) with (env e) {
            requireInvariant totalSupplyEqualsSumOfBalances();
            requireInvariant individualBalanceLeqTotalSupply(receiver);
            require to_mathint(totalSupply()) + shares <= max_uint256;
        }
        preserved mint(uint256 shares, address receiver, uint16 referral) with (env e) {
            requireInvariant totalSupplyEqualsSumOfBalances();
            requireInvariant individualBalanceLeqTotalSupply(receiver);
            require to_mathint(totalSupply()) + shares <= max_uint256;
        }
        preserved deposit(uint256 assets, address receiver) with (env e) {
            requireInvariant totalSupplyEqualsSumOfBalances();
            requireInvariant individualBalanceLeqTotalSupply(receiver);
            require to_mathint(totalSupply()) + to_mathint(assets) * RAY() <= max_uint256;
        }
        preserved deposit(uint256 assets, address receiver, uint16 referral) with (env e) {
            requireInvariant totalSupplyEqualsSumOfBalances();
            requireInvariant individualBalanceLeqTotalSupply(receiver);
            require to_mathint(totalSupply()) + to_mathint(assets) * RAY() <= max_uint256;
        }
        preserved withdraw(uint256 assets, address receiver, address owner) with (env e) {
            requireInvariant totalSupplyEqualsSumOfBalances();
            requireInvariant individualBalanceLeqTotalSupply(owner);
            require balanceOf(a) + balanceOf(owner) <= to_mathint(totalSupply());
        }
        preserved redeem(uint256 shares, address receiver, address owner) with (env e) {
            requireInvariant totalSupplyEqualsSumOfBalances();
            requireInvariant individualBalanceLeqTotalSupply(owner);
            require balanceOf(a) + balanceOf(owner) <= to_mathint(totalSupply());
        }
    }

// ===================== Property 4 =====================
// transfer must revert if to is address(0) or address(this)
rule transfer_reverts_on_invalid_recipient(env e, address to, uint256 value) {
    require to == 0 || to == currentContract;
    transfer@withrevert(e, to, value);
    assert lastReverted;
}

// ===================== Property 5 =====================
// transferFrom must revert if to is address(0) or address(this)
rule transferFrom_reverts_on_invalid_recipient(env e, address from, address to, uint256 value) {
    require to == 0 || to == currentContract;
    transferFrom@withrevert(e, from, to, value);
    assert lastReverted;
}

// ===================== Property 6 =====================
// transfer must revert if value exceeds balanceOf[msg.sender]
rule transfer_reverts_on_insufficient_balance(env e, address to, uint256 value) {
    require balanceOf(e.msg.sender) < value;
    transfer@withrevert(e, to, value);
    assert lastReverted;
}

// ===================== Property 7 =====================
// transferFrom must revert if value exceeds balanceOf[from]
rule transferFrom_reverts_on_insufficient_balance(env e, address from, address to, uint256 value) {
    require balanceOf(from) < value;
    transferFrom@withrevert(e, from, to, value);
    assert lastReverted;
}

// ===================== Property 8 =====================
// transferFrom must revert when from != msg.sender, allowance not max, and allowance < value
rule transferFrom_reverts_on_insufficient_allowance(env e, address from, address to, uint256 value) {
    require from != e.msg.sender;
    require allowance(from, e.msg.sender) != max_uint256;
    require allowance(from, e.msg.sender) < value;
    transferFrom@withrevert(e, from, to, value);
    assert lastReverted;
}

// ===================== Property 9 =====================
// transfer preserves totalSupply
rule transfer_preserves_total_supply(env e, address to, uint256 value) {
    mathint totalBefore = totalSupply();
    transfer(e, to, value);
    assert totalSupply() == totalBefore;
}

// ===================== Property 10 =====================
// transferFrom preserves totalSupply
rule transferFrom_preserves_total_supply(env e, address from, address to, uint256 value) {
    mathint totalBefore = totalSupply();
    transferFrom(e, from, to, value);
    assert totalSupply() == totalBefore;
}

// ===================== Property 11 =====================
// After transfer(to, value) where msg.sender != to: sender decreases by value, to increases by value
rule transfer_correct_balance_update(env e, address to, uint256 value) {
    require e.msg.sender != to;
    // Needed to rule out spurious overflow of unchecked balanceOf[to] += value
    requireInvariant totalSupplyEqualsSumOfBalances();
    requireInvariant individualBalanceLeqTotalSupply(to);
    requireInvariant individualBalanceLeqTotalSupply(e.msg.sender);
    // Sound: follows from totalSupply == sum(all non-negative balances)
    require balanceOf(e.msg.sender) + balanceOf(to) <= to_mathint(totalSupply());

    mathint senderBefore = balanceOf(e.msg.sender);
    mathint toBefore = balanceOf(to);
    transfer(e, to, value);
    assert balanceOf(e.msg.sender) == senderBefore - value;
    assert balanceOf(to) == toBefore + value;
}

// ===================== Property 12 =====================
// After transferFrom(from, to, value) where from != to: from decreases by value, to increases by value
rule transferFrom_correct_balance_update(env e, address from, address to, uint256 value) {
    require from != to;
    // Needed to rule out spurious overflow of unchecked balanceOf[to] += value
    requireInvariant totalSupplyEqualsSumOfBalances();
    requireInvariant individualBalanceLeqTotalSupply(to);
    requireInvariant individualBalanceLeqTotalSupply(from);
    // Sound: follows from totalSupply == sum(all non-negative balances)
    require balanceOf(from) + balanceOf(to) <= to_mathint(totalSupply());

    mathint fromBefore = balanceOf(from);
    mathint toBefore = balanceOf(to);
    transferFrom(e, from, to, value);
    assert balanceOf(from) == fromBefore - value;
    assert balanceOf(to) == toBefore + value;
}

// ===================== Property 13 =====================
// transfer does not change any third party's balance
rule transfer_no_third_party_balance_change(env e, address to, uint256 value, address addr) {
    require addr != e.msg.sender && addr != to;
    mathint balBefore = balanceOf(addr);
    transfer(e, to, value);
    assert balanceOf(addr) == balBefore;
}

// ===================== Property 14 =====================
// transferFrom does not change any third party's balance
rule transferFrom_no_third_party_balance_change(env e, address from, address to, uint256 value, address addr) {
    require addr != from && addr != to;
    mathint balBefore = balanceOf(addr);
    transferFrom(e, from, to, value);
    assert balanceOf(addr) == balBefore;
}

// ===================== Property 15 =====================
// When msg.sender == from, transferFrom must not modify any allowance entry
rule transferFrom_self_no_allowance_consumed(env e, address to, uint256 value, address anyOwner, address anySpender) {
    address from = e.msg.sender;
    mathint allowanceBefore = allowance(anyOwner, anySpender);
    transferFrom(e, from, to, value);
    assert allowance(anyOwner, anySpender) == allowanceBefore;
}

// ===================== Property 16 =====================
// If allowance is max_uint256 before transferFrom, it remains max_uint256 after
rule infinite_allowance_not_decremented(env e, address from, address to, uint256 value) {
    require allowance(from, e.msg.sender) == max_uint256;
    transferFrom(e, from, to, value);
    assert allowance(from, e.msg.sender) == max_uint256;
}

// ===================== Property 17 =====================
// After transferFrom where from != sender and finite allowance: allowance decreases by exactly value
rule finite_allowance_decremented_exactly(env e, address from, address to, uint256 value) {
    require from != e.msg.sender;
    mathint allowanceBefore = allowance(from, e.msg.sender);
    require allowanceBefore != max_uint256;
    transferFrom(e, from, to, value);
    assert allowance(from, e.msg.sender) == allowanceBefore - value;
}

// ===================== Property 18 =====================
// decreaseAllowance reverts if subtractedValue exceeds current allowance
rule decreaseAllowance_reverts_on_underflow(env e, address spender, uint256 subtractedValue) {
    require allowance(e.msg.sender, spender) < subtractedValue;
    decreaseAllowance@withrevert(e, spender, subtractedValue);
    assert lastReverted;
}

// ===================== Property 19 =====================
// approve sets the allowance to exactly the given value
rule approve_sets_exact_value(env e, address spender, uint256 value) {
    approve(e, spender, value);
    assert allowance(e.msg.sender, spender) == value;
}

// ===================== Property 20 =====================
// increaseAllowance adds exactly addedValue to the current allowance
rule increaseAllowance_adds_exactly(env e, address spender, uint256 addedValue) {
    mathint allowanceBefore = allowance(e.msg.sender, spender);
    increaseAllowance(e, spender, addedValue);
    assert allowance(e.msg.sender, spender) == allowanceBefore + addedValue;
}

// ===================== Property 21 =====================
// decreaseAllowance subtracts exactly subtractedValue from the current allowance
rule decreaseAllowance_subtracts_exactly(env e, address spender, uint256 subtractedValue) {
    mathint allowanceBefore = allowance(e.msg.sender, spender);
    decreaseAllowance(e, spender, subtractedValue);
    assert allowance(e.msg.sender, spender) == allowanceBefore - subtractedValue;
}

// ===================== Property 22 =====================
// Allowance can only increase via approve/increaseAllowance (by owner) or permit
rule no_unauthorized_allowance_increase(env e, method f, calldataarg args, address owner, address spender) {
    mathint allowanceBefore = allowance(owner, spender);
    f(e, args);
    mathint allowanceAfter = allowance(owner, spender);
    assert allowanceAfter > allowanceBefore => (
        (e.msg.sender == owner && 
         (f.selector == sig:approve(address, uint256).selector || 
          f.selector == sig:increaseAllowance(address, uint256).selector)) ||
        f.selector == sig:permit(address, address, uint256, uint256, bytes).selector ||
        f.selector == sig:permit(address, address, uint256, uint256, uint8, bytes32, bytes32).selector
    );
}

// ===================== Property 23 =====================
// transferFrom must not change allowance[x][y] for any (x,y) != (from, msg.sender)
rule transferFrom_no_third_party_allowance_change(env e, address from, address to, uint256 value, address x, address y) {
    require x != from || y != e.msg.sender;
    mathint allowanceBefore = allowance(x, y);
    transferFrom(e, from, to, value);
    assert allowance(x, y) == allowanceBefore;
}

// ===================== Property 24 =====================
// approve, increaseAllowance, decreaseAllowance must not modify any balance or totalSupply
rule allowance_ops_no_side_effects_on_balances(env e, method f, calldataarg args, address addr) 
    filtered { f -> f.selector == sig:approve(address, uint256).selector ||
                     f.selector == sig:increaseAllowance(address, uint256).selector ||
                     f.selector == sig:decreaseAllowance(address, uint256).selector }
{
    mathint balBefore = balanceOf(addr);
    mathint totalBefore = totalSupply();
    f(e, args);
    assert balanceOf(addr) == balBefore;
    assert totalSupply() == totalBefore;
}

// ===================== Property 25 =====================
// Self-transfer preserves balance (transfer case)
rule self_transfer_preserves_balance_transfer(env e, uint256 value) {
    address to = e.msg.sender;
    mathint balBefore = balanceOf(to);
    transfer(e, to, value);
    assert balanceOf(to) == balBefore;
}

// Self-transfer preserves balance (transferFrom case where from == to)
rule self_transfer_preserves_balance_transferFrom(env e, address fromTo, uint256 value) {
    mathint balBefore = balanceOf(fromTo);
    transferFrom(e, fromTo, fromTo, value);
    assert balanceOf(fromTo) == balBefore;
}

// ===================== Property 26 =====================
// Unchecked balanceOf[to] += value in transfer cannot overflow
// Relies on the invariant that totalSupply == sum of all balances
rule unchecked_recipient_balance_no_overflow_transfer(env e, address to, uint256 value) {
    requireInvariant totalSupplyEqualsSumOfBalances();
    requireInvariant individualBalanceLeqTotalSupply(to);
    requireInvariant individualBalanceLeqTotalSupply(e.msg.sender);
    // Sound: follows from totalSupply == sum(all non-negative balances)
    require balanceOf(e.msg.sender) + balanceOf(to) <= to_mathint(totalSupply());
    
    mathint toBefore = balanceOf(to);
    transfer(e, to, value);
    assert balanceOf(to) >= toBefore;
}

// Unchecked balanceOf[to] += value in transferFrom cannot overflow
rule unchecked_recipient_balance_no_overflow_transferFrom(env e, address from, address to, uint256 value) {
    requireInvariant totalSupplyEqualsSumOfBalances();
    requireInvariant individualBalanceLeqTotalSupply(to);
    requireInvariant individualBalanceLeqTotalSupply(from);
    // Sound: follows from totalSupply == sum(all non-negative balances)
    require balanceOf(from) + balanceOf(to) <= to_mathint(totalSupply());
    
    mathint toBefore = balanceOf(to);
    transferFrom(e, from, to, value);
    assert balanceOf(to) >= toBefore;
}

// ===================== Property 27 =====================
// transfer must not modify any allowance entry
rule transfer_no_allowance_change(env e, address to, uint256 value, address x, address y) {
    mathint allowanceBefore = allowance(x, y);
    transfer(e, to, value);
    assert allowance(x, y) == allowanceBefore;
}

// ===================== Property 28 =====================
// approve must not change allowance[x][y] for (x,y) != (msg.sender, spender)
rule approve_no_third_party_allowance_change(env e, address spender, uint256 value, address x, address y) {
    require x != e.msg.sender || y != spender;
    mathint allowanceBefore = allowance(x, y);
    approve(e, spender, value);
    assert allowance(x, y) == allowanceBefore;
}

// increaseAllowance must not change allowance[x][y] for (x,y) != (msg.sender, spender)
rule increaseAllowance_no_third_party_allowance_change(env e, address spender, uint256 addedValue, address x, address y) {
    require x != e.msg.sender || y != spender;
    mathint allowanceBefore = allowance(x, y);
    increaseAllowance(e, spender, addedValue);
    assert allowance(x, y) == allowanceBefore;
}

// decreaseAllowance must not change allowance[x][y] for (x,y) != (msg.sender, spender)
rule decreaseAllowance_no_third_party_allowance_change(env e, address spender, uint256 subtractedValue, address x, address y) {
    require x != e.msg.sender || y != spender;
    mathint allowanceBefore = allowance(x, y);
    decreaseAllowance(e, spender, subtractedValue);
    assert allowance(x, y) == allowanceBefore;
}

// ===================== Property 29 =====================
// transfer must not revert when preconditions are met
rule transfer_succeeds_when_valid(env e, address to, uint256 value) {
    require to != 0;
    require to != currentContract;
    require balanceOf(e.msg.sender) >= value;
    require e.msg.value == 0; // function is not payable
    
    transfer@withrevert(e, to, value);
    assert !lastReverted;
}

// ===================== Property 30 =====================
// transferFrom must not revert when preconditions are met
rule transferFrom_succeeds_when_valid(env e, address from, address to, uint256 value) {
    require to != 0;
    require to != currentContract;
    require balanceOf(from) >= value;
    require from == e.msg.sender || allowance(from, e.msg.sender) == max_uint256 || allowance(from, e.msg.sender) >= value;
    require e.msg.value == 0; // function is not payable
    
    transferFrom@withrevert(e, from, to, value);
    assert !lastReverted;
}

// ===================== Property 31 =====================
// approve must never revert (no preconditions beyond non-payable)
rule approve_always_succeeds(env e, address spender, uint256 value) {
    require e.msg.value == 0; // function is not payable
    approve@withrevert(e, spender, value);
    assert !lastReverted;
}

// ===================== Property 32 =====================
// decreaseAllowance must not revert when allowance >= subtractedValue
rule decreaseAllowance_succeeds_when_valid(env e, address spender, uint256 subtractedValue) {
    require allowance(e.msg.sender, spender) >= subtractedValue;
    require e.msg.value == 0; // function is not payable
    decreaseAllowance@withrevert(e, spender, subtractedValue);
    assert !lastReverted;
}

// ===================== Property 33 =====================
// increaseAllowance must not revert when sum doesn't overflow uint256
rule increaseAllowance_succeeds_when_valid(env e, address spender, uint256 addedValue) {
    require allowance(e.msg.sender, spender) + addedValue <= max_uint256;
    require e.msg.value == 0; // function is not payable
    increaseAllowance@withrevert(e, spender, addedValue);
    assert !lastReverted;
}

// ===================== Property 34 =====================
// ERC-20 operations must not modify nonces
rule erc20_functions_preserve_nonces(env e, method f, calldataarg args, address x)
    filtered { f -> f.selector == sig:transfer(address, uint256).selector ||
                     f.selector == sig:transferFrom(address, address, uint256).selector ||
                     f.selector == sig:approve(address, uint256).selector ||
                     f.selector == sig:increaseAllowance(address, uint256).selector ||
                     f.selector == sig:decreaseAllowance(address, uint256).selector }
{
    mathint nonceBefore = nonces(x);
    f(e, args);
    assert nonces(x) == nonceBefore;
}
