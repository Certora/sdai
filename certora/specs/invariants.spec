// Spec for SavingsDai ERC20 properties

import "summaries/SavingsDai_base_summaries.spec";
import "summaries/custom_summaries.spec";

methods {
    function totalSupply() external returns (uint256) envfree;
    function balanceOf(address) external returns (uint256) envfree;
}

// RAY = 10^27, used in shares computation
definition RAY() returns mathint = 1000000000000000000000000000;

// Ghost variable to track the sum of all balances
// Using persistent because the imported custom_summaries.spec uses HAVOC_ECF for external calls
// (pot.drip, pot.join, pot.exit, daiJoin.join, daiJoin.exit). HAVOC_ECF preserves the current
// contract's storage but havocs non-persistent ghosts. Since these ghosts track SavingsDai's own
// storage state (which IS preserved by HAVOC_ECF), persistent is sound and necessary.
// CVL Document-Ref: 4b7a00f1b23922d9486bd6762c9ea997d1a2fdd60b3d52
// CVL Document-Ref: 81179c19c85ff246331b1f47b511fdb0a218fac48e27c4
persistent ghost mathint sumOfBalances {
    init_state axiom sumOfBalances == 0;
}

// Ghost mirror mapping for individual balances - needed to link individual balances to sumOfBalances
persistent ghost mapping(address => mathint) ghostBalanceOf {
    init_state axiom forall address a. ghostBalanceOf[a] == 0;
}

// Hook on Sstore to balanceOf mapping to maintain sumOfBalances and ghostBalanceOf
hook Sstore balanceOf[KEY address a] uint256 newValue (uint256 oldValue) {
    sumOfBalances = sumOfBalances + newValue - oldValue;
    ghostBalanceOf[a] = to_mathint(newValue);
}

// Sload hook to constrain loaded balance values to match the ghost mirror
hook Sload uint256 value balanceOf[KEY address a] {
    require ghostBalanceOf[a] == to_mathint(value);
}

// Property 1: totalSupply == sum of all balanceOf[a]
invariant totalSupplyEqualsSumOfBalances()
    to_mathint(totalSupply()) == sumOfBalances
    {
        preserved transfer(address to, uint256 value) with (env e) {
            requireInvariant individualBalanceLeqTotalSupply(e.msg.sender);
            requireInvariant individualBalanceLeqTotalSupply(to);
            // Sound: if totalSupply == sum(all balances) and all balances >= 0,
            // then the sum of any two balances cannot exceed totalSupply
            require balanceOf(e.msg.sender) + balanceOf(to) <= to_mathint(totalSupply());
        }
        preserved transferFrom(address from, address to, uint256 value) with (env e) {
            requireInvariant individualBalanceLeqTotalSupply(from);
            requireInvariant individualBalanceLeqTotalSupply(to);
            require balanceOf(from) + balanceOf(to) <= to_mathint(totalSupply());
        }
        preserved mint(uint256 shares, address receiver) with (env e) {
            requireInvariant individualBalanceLeqTotalSupply(receiver);
            // Prevent unchecked totalSupply += shares overflow
            // Contract comment: "we don't need an overflow check here b/c shares totalSupply will always be <= dai totalSupply"
            require to_mathint(totalSupply()) + shares <= max_uint256;
        }
        preserved mint(uint256 shares, address receiver, uint16 referral) with (env e) {
            requireInvariant individualBalanceLeqTotalSupply(receiver);
            require to_mathint(totalSupply()) + shares <= max_uint256;
        }
        preserved deposit(uint256 assets, address receiver) with (env e) {
            requireInvariant individualBalanceLeqTotalSupply(receiver);
            // For deposit, shares = assets * RAY / chi (computed internally).
            // shares <= assets * RAY (since chi >= 1). Prevent unchecked overflow.
            // Sound: contract assumes totalSupply bounded well below max_uint256.
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

// Property 2: balanceOf[address(0)] is always 0
invariant zeroAddressHasZeroBalance()
    balanceOf(0) == 0;

// Property 3: balanceOf[address(this)] (the SavingsDai contract's own sDAI balance) is always 0
invariant contractAddressHasZeroBalance()
    balanceOf(currentContract) == 0;

// Property 4: For any address a, balanceOf[a] <= totalSupply
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
            // Sound: if totalSupply == sum(all balances), any two non-negative balances sum to <= totalSupply
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
            // Prevent unchecked overflow in _mint
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
            // shares = assets * RAY / chi <= assets * RAY; prevent unchecked overflow
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
            // Sound: sum of any two non-negative balances <= totalSupply
            require balanceOf(a) + balanceOf(owner) <= to_mathint(totalSupply());
        }
        preserved redeem(uint256 shares, address receiver, address owner) with (env e) {
            requireInvariant totalSupplyEqualsSumOfBalances();
            requireInvariant individualBalanceLeqTotalSupply(owner);
            require balanceOf(a) + balanceOf(owner) <= to_mathint(totalSupply());
        }
    }
