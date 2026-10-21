import "summaries/SavingsDai_base_summaries.spec";
import "summaries/SavingsDai_call_resolution.spec";
import "scene.spec";

/*
 * Structural invariants of SavingsDai (batch slug: invariants).
 * Properties: certora/properties/invariants.properties.json
 */

using Pot as pot;

methods {
    function totalSupply() external returns (uint256) envfree;
    function balanceOf(address) external returns (uint256) envfree;
    function Pot.pie(address) external returns (uint256) envfree;
}

// ---------------------------------------------------------------------------
// Sum of balances, tracked with hooks on SavingsDai.balanceOf
// ---------------------------------------------------------------------------

ghost mathint sumOfBalances {
    init_state axiom sumOfBalances == 0;
}

hook Sstore currentContract.balanceOf[KEY address a] uint256 newBal (uint256 oldBal) {
    sumOfBalances = sumOfBalances + newBal - oldBal;
}

// Every individual balance is part of the sum, so it can never exceed it.
hook Sload uint256 bal currentContract.balanceOf[KEY address a] {
    require sumOfBalances >= to_mathint(bal);
}

/// total_supply_equals_sum_of_balances
// _mint adds shares to totalSupply and balanceOf[receiver] in an unchecked block; the
// Pot.join of the same shares (checked) rules out wrap-around only given sharesBackedByPie.
invariant totalSupplyIsSumOfBalances()
    to_mathint(totalSupply()) == sumOfBalances
    {
        preserved {
            requireInvariant sharesBackedByPie();
        }
    }

/// shares_backed_by_pot_pie
// _burn subtracts shares from totalSupply unchecked; it cannot underflow because
// shares <= balanceOf[owner] <= totalSupply, which needs totalSupplyIsSumOfBalances.
invariant sharesBackedByPie()
    pot.pie(currentContract) >= totalSupply()
    {
        preserved {
            requireInvariant totalSupplyIsSumOfBalances();
        }
    }

/// zero_and_self_hold_no_shares
invariant zeroAndSelfHoldNoShares()
    balanceOf(0) == 0 && balanceOf(currentContract) == 0;
