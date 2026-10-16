
import "summaries/SavingsDai_base_summaries.spec";
import "summaries/custom_summaries.spec";

using SavingsDai as savingsDai;
using DummyERC20Impl as dummyERC20Impl;

// ============================================================
// Definitions
// ============================================================
definition RAY() returns mathint = 1000000000000000000000000000;

// ============================================================
// Ghost Variables
// ============================================================

// Sum of all balances - must be persistent to survive HAVOC_ECF calls
// from the imported custom_summaries (pot.join/exit, daiJoin.join/exit).
// HAVOC_ECF preserves the current contract's storage (so balanceOf is safe)
// but havocs non-persistent ghosts.
persistent ghost mathint sumOfBalances {
    init_state axiom sumOfBalances == 0;
}

// ============================================================
// Methods Block
// ============================================================
methods {
    function totalSupply() external returns (uint256) envfree;
    function balanceOf(address) external returns (uint256) envfree;
    function allowance(address, address) external returns (uint256) envfree;
    function maxDeposit(address) external returns (uint256) envfree;
    function maxMint(address) external returns (uint256) envfree;
    function maxRedeem(address) external returns (uint256) envfree;
}

// ============================================================
// Hooks
// ============================================================

hook Sstore balanceOf[KEY address a] uint256 newValue (uint256 oldValue) {
    sumOfBalances = sumOfBalances + newValue - oldValue;
}

// ============================================================
// INVARIANTS
// ============================================================

// Property 1: totalSupply equals sum of all balanceOf values
invariant share_ledger_conservation()
    to_mathint(totalSupply()) == sumOfBalances
    {
        preserved transfer(address to, uint256 value) with (env e) {
            require balanceOf(e.msg.sender) + balanceOf(to) <= to_mathint(totalSupply());
        }
        preserved transferFrom(address from, address to, uint256 value) with (env e) {
            require balanceOf(from) + balanceOf(to) <= to_mathint(totalSupply());
        }
        preserved deposit(uint256 assets, address receiver) with (env e) {
            // Prevent unchecked overflow in _mint for both totalSupply and balanceOf
            require to_mathint(totalSupply()) + to_mathint(assets) * RAY() <= max_uint256;
            require to_mathint(balanceOf(receiver)) + to_mathint(assets) * RAY() <= max_uint256;
        }
        preserved deposit(uint256 assets, address receiver, uint16 referral) with (env e) {
            require to_mathint(totalSupply()) + to_mathint(assets) * RAY() <= max_uint256;
            require to_mathint(balanceOf(receiver)) + to_mathint(assets) * RAY() <= max_uint256;
        }
        preserved mint(uint256 shares, address receiver) with (env e) {
            require to_mathint(totalSupply()) + shares <= max_uint256;
            require to_mathint(balanceOf(receiver)) + shares <= max_uint256;
        }
        preserved mint(uint256 shares, address receiver, uint16 referral) with (env e) {
            require to_mathint(totalSupply()) + shares <= max_uint256;
            require to_mathint(balanceOf(receiver)) + shares <= max_uint256;
        }
        preserved withdraw(uint256 assets, address receiver, address owner) with (env e) {
            // Prevent spurious states where balanceOf(owner) > totalSupply
            require balanceOf(owner) <= totalSupply();
        }
        preserved redeem(uint256 shares, address receiver, address owner) with (env e) {
            require balanceOf(owner) <= totalSupply();
        }
    }

// ============================================================
// RULES
// ============================================================

// --- Property 9: deposit and mint revert on invalid receiver ---
rule invalid_receiver_revert_deposit_zero(uint256 assets) {
    env e;
    deposit@withrevert(e, assets, 0);
    assert lastReverted;
}

rule invalid_receiver_revert_deposit_self(uint256 assets) {
    env e;
    deposit@withrevert(e, assets, currentContract);
    assert lastReverted;
}

rule invalid_receiver_revert_mint_zero(uint256 shares) {
    env e;
    mint@withrevert(e, shares, 0);
    assert lastReverted;
}

rule invalid_receiver_revert_mint_self(uint256 shares) {
    env e;
    mint@withrevert(e, shares, currentContract);
    assert lastReverted;
}

// --- Property 10: insufficient balance revert ---
rule insufficient_balance_revert_withdraw(uint256 assets, address receiver, address owner) {
    env e;
    // Specific case: owner has zero balance, any positive assets requires shares >= 1
    require balanceOf(owner) == 0;
    require assets > 0;

    withdraw@withrevert(e, assets, receiver, owner);
    assert lastReverted;
}

rule insufficient_balance_revert_redeem(uint256 shares, address receiver, address owner) {
    env e;
    require to_mathint(balanceOf(owner)) < to_mathint(shares);
    require shares > 0;

    redeem@withrevert(e, shares, receiver, owner);
    assert lastReverted;
}

// --- Property 11: insufficient allowance revert ---
rule insufficient_allowance_revert_withdraw(uint256 assets, address receiver, address owner) {
    env e;
    require e.msg.sender != owner;
    // Ensure sufficient balance but zero allowance
    require balanceOf(owner) == max_uint256;
    require allowance(owner, e.msg.sender) == 0;
    require assets > 0;

    withdraw@withrevert(e, assets, receiver, owner);
    assert lastReverted;
}

rule insufficient_allowance_revert_redeem(uint256 shares, address receiver, address owner) {
    env e;
    require e.msg.sender != owner;
    require to_mathint(balanceOf(owner)) >= to_mathint(shares);
    require shares > 0;
    require allowance(owner, e.msg.sender) != max_uint256;
    require to_mathint(allowance(owner, e.msg.sender)) < to_mathint(shares);

    redeem@withrevert(e, shares, receiver, owner);
    assert lastReverted;
}

// --- Property 12: infinite allowance unchanged ---
rule infinite_allowance_unchanged_withdraw(uint256 assets, address receiver, address owner) {
    env e;
    require e.msg.sender != owner;
    require allowance(owner, e.msg.sender) == max_uint256;

    withdraw(e, assets, receiver, owner);

    assert allowance(owner, e.msg.sender) == max_uint256;
}

rule infinite_allowance_unchanged_redeem(uint256 shares, address receiver, address owner) {
    env e;
    require e.msg.sender != owner;
    require allowance(owner, e.msg.sender) == max_uint256;

    redeem(e, shares, receiver, owner);

    assert allowance(owner, e.msg.sender) == max_uint256;
}

rule infinite_allowance_unchanged_transferFrom(address from, address to, uint256 value) {
    env e;
    require e.msg.sender != from;
    require allowance(from, e.msg.sender) == max_uint256;

    transferFrom(e, from, to, value);

    assert allowance(from, e.msg.sender) == max_uint256;
}

// --- Property 13: finite allowance decremented ---
rule finite_allowance_decremented_withdraw(uint256 assets, address receiver, address owner) {
    env e;
    require e.msg.sender != owner;
    uint256 allowanceBefore = allowance(owner, e.msg.sender);
    require allowanceBefore != max_uint256;

    uint256 shares = withdraw(e, assets, receiver, owner);

    assert to_mathint(allowance(owner, e.msg.sender)) == to_mathint(allowanceBefore) - to_mathint(shares);
}

rule finite_allowance_decremented_redeem(uint256 shares, address receiver, address owner) {
    env e;
    require e.msg.sender != owner;
    uint256 allowanceBefore = allowance(owner, e.msg.sender);
    require allowanceBefore != max_uint256;

    redeem(e, shares, receiver, owner);

    assert to_mathint(allowance(owner, e.msg.sender)) == to_mathint(allowanceBefore) - to_mathint(shares);
}

rule finite_allowance_decremented_transferFrom(address from, address to, uint256 value) {
    env e;
    require e.msg.sender != from;
    uint256 allowanceBefore = allowance(from, e.msg.sender);
    require allowanceBefore != max_uint256;

    transferFrom(e, from, to, value);

    assert to_mathint(allowance(from, e.msg.sender)) == to_mathint(allowanceBefore) - to_mathint(value);
}

// --- Property 14: maxDeposit and maxMint return max ---
rule max_deposit_max_mint_return_max(address addr) {
    assert maxDeposit(addr) == max_uint256;
    assert maxMint(addr) == max_uint256;
}

// --- Property 16: maxRedeem computation ---
rule max_redeem_computation(address owner) {
    assert maxRedeem(owner) == balanceOf(owner);
}

// --- Property 17: exact mint state transition (deposit/mint) ---
rule exact_mint_state_transition_deposit(uint256 assets, address receiver, address other) {
    env e;
    require other != receiver;
    // Prevent unchecked overflow in _mint
    require to_mathint(totalSupply()) + to_mathint(assets) * RAY() <= max_uint256;
    require to_mathint(balanceOf(receiver)) + to_mathint(assets) * RAY() <= max_uint256;

    uint256 supply_before = totalSupply();
    uint256 bal_recv_before = balanceOf(receiver);
    uint256 bal_other_before = balanceOf(other);

    uint256 shares = deposit(e, assets, receiver);

    assert to_mathint(totalSupply()) == to_mathint(supply_before) + to_mathint(shares);
    assert to_mathint(balanceOf(receiver)) == to_mathint(bal_recv_before) + to_mathint(shares);
    assert balanceOf(other) == bal_other_before;
}

rule exact_mint_state_transition_mint(uint256 shares, address receiver, address other) {
    env e;
    require other != receiver;
    require to_mathint(totalSupply()) + shares <= max_uint256;
    require to_mathint(balanceOf(receiver)) + shares <= max_uint256;

    uint256 supply_before = totalSupply();
    uint256 bal_recv_before = balanceOf(receiver);
    uint256 bal_other_before = balanceOf(other);

    mint(e, shares, receiver);

    assert to_mathint(totalSupply()) == to_mathint(supply_before) + to_mathint(shares);
    assert to_mathint(balanceOf(receiver)) == to_mathint(bal_recv_before) + to_mathint(shares);
    assert balanceOf(other) == bal_other_before;
}

// --- Property 18: exact burn state transition (withdraw/redeem) ---
rule exact_burn_state_transition_withdraw(uint256 assets, address receiver, address owner, address other) {
    env e;
    require other != owner;
    // Prevent spurious states where totalSupply < balanceOf(owner)
    requireInvariant share_ledger_conservation();
    require balanceOf(owner) <= totalSupply();

    uint256 supply_before = totalSupply();
    uint256 bal_owner_before = balanceOf(owner);
    uint256 bal_other_before = balanceOf(other);

    uint256 shares = withdraw(e, assets, receiver, owner);

    assert to_mathint(totalSupply()) == to_mathint(supply_before) - to_mathint(shares);
    assert to_mathint(balanceOf(owner)) == to_mathint(bal_owner_before) - to_mathint(shares);
    assert balanceOf(other) == bal_other_before;
}

rule exact_burn_state_transition_redeem(uint256 shares, address receiver, address owner, address other) {
    env e;
    require other != owner;
    // Prevent spurious states where totalSupply < balanceOf(owner)
    requireInvariant share_ledger_conservation();
    require balanceOf(owner) <= totalSupply();

    uint256 supply_before = totalSupply();
    uint256 bal_owner_before = balanceOf(owner);
    uint256 bal_other_before = balanceOf(other);

    redeem(e, shares, receiver, owner);

    assert to_mathint(totalSupply()) == to_mathint(supply_before) - to_mathint(shares);
    assert to_mathint(balanceOf(owner)) == to_mathint(bal_owner_before) - to_mathint(shares);
    assert balanceOf(other) == bal_other_before;
}

// --- Property 23: transfer preserves total supply ---
rule transfer_preserves_total_supply(address to, uint256 value) {
    env e;
    uint256 supplyBefore = totalSupply();
    transfer(e, to, value);
    assert totalSupply() == supplyBefore;
}

rule transferFrom_preserves_total_supply(address from, address to, uint256 value) {
    env e;
    uint256 supplyBefore = totalSupply();
    transferFrom(e, from, to, value);
    assert totalSupply() == supplyBefore;
}

// --- Property 24: transfer invalid address revert ---
rule transfer_invalid_address_revert_zero(uint256 value) {
    env e;
    transfer@withrevert(e, 0, value);
    assert lastReverted;
}

rule transfer_invalid_address_revert_self(uint256 value) {
    env e;
    transfer@withrevert(e, currentContract, value);
    assert lastReverted;
}

rule transferFrom_invalid_address_revert_zero(address from, uint256 value) {
    env e;
    transferFrom@withrevert(e, from, 0, value);
    assert lastReverted;
}

rule transferFrom_invalid_address_revert_self(address from, uint256 value) {
    env e;
    transferFrom@withrevert(e, from, currentContract, value);
    assert lastReverted;
}

// --- Property 30: zero share deposit loss ---
// Attack vector: small deposit can yield 0 shares (expected to FAIL)
rule zero_share_deposit_loss(uint256 assets, address receiver) {
    env e;
    require assets > 0;
    // Overflow prevention
    require to_mathint(totalSupply()) + to_mathint(assets) * RAY() <= max_uint256;
    require to_mathint(balanceOf(receiver)) + to_mathint(assets) * RAY() <= max_uint256;

    uint256 shares = deposit(e, assets, receiver);

    assert shares > 0;
}

// --- Property 31: unchecked overflow ---
// Attack vector: _mint unchecked arithmetic can overflow (expected to FAIL)
rule unchecked_balance_and_supply_overflow(uint256 assets, address receiver) {
    env e;

    mathint supply_before = totalSupply();
    mathint balance_before = balanceOf(receiver);

    uint256 shares = deposit(e, assets, receiver);

    assert to_mathint(totalSupply()) == supply_before + to_mathint(shares);
    assert to_mathint(balanceOf(receiver)) == balance_before + to_mathint(shares);
}

// --- Property 36: self-transfer balance preservation ---
rule self_transfer_balance_preservation_transfer(uint256 value) {
    env e;
    address sender = e.msg.sender;
    uint256 balanceBefore = balanceOf(sender);

    transfer(e, sender, value);

    assert balanceOf(sender) == balanceBefore;
}

rule self_transfer_balance_preservation_transferFrom(address addr, uint256 value) {
    env e;
    uint256 balanceBefore = balanceOf(addr);

    transferFrom(e, addr, addr, value);

    assert balanceOf(addr) == balanceBefore;
}

// --- Property 37: transferFrom self caller no allowance consumed ---
rule transferFrom_self_caller_no_allowance_consumed(address to, uint256 value, address spender) {
    env e;

    uint256 allowanceBefore = allowance(e.msg.sender, spender);

    transferFrom(e, e.msg.sender, to, value);

    assert allowance(e.msg.sender, spender) == allowanceBefore;
}

// --- Property 38: withdraw/redeem receiver unvalidated ---
// Attack vector: receiver=SavingsDai is not validated (expected to FAIL)
rule withdraw_redeem_receiver_unvalidated(uint256 assets, address owner) {
    env e;
    require e.msg.sender == owner;
    require balanceOf(owner) == max_uint256;
    require assets > 0;

    withdraw@withrevert(e, assets, currentContract, owner);

    assert lastReverted;
}


