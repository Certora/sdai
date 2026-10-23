/*
 * maker-models / Dai: supply invariant of the scene's DAI token (certora/harnesses/Dai.sol, a port
 * of mainnet dss dai.sol), proven with Dai as the verified contract, so the invariant base case runs
 * Dai's constructor. Property: dai_supply_is_sum.
 *
 * No summaries are imported: Dai makes no external calls (permit's ecrecover is a precompile the
 * prover models as an uninterpreted function), so no summary could apply.
 */

methods {
    function totalSupply() external returns (uint256) envfree;
    function balanceOf(address) external returns (uint256) envfree;
}

// sumDaiBalances mirrors the sum of Dai.balanceOf over all addresses: 0 initially (the
// constructor writes no balance), and every write to balanceOf[a] adds new - old.
ghost mathint sumDaiBalances {
    init_state axiom sumDaiBalances == 0;
}

hook Sstore currentContract.balanceOf[KEY address a] uint256 newBal (uint256 oldBal) {
    sumDaiBalances = sumDaiBalances + newBal - oldBal;
}

// Each balance is one non-negative term of the sum, so it is at most the sum. Used only by the
// corollary daiBalanceAtMostSupply.
hook Sload uint256 bal currentContract.balanceOf[KEY address a] {
    require sumDaiBalances >= to_mathint(bal);
}

/// dai_supply_is_sum
invariant daiSupplyIsSum()
    to_mathint(totalSupply()) == sumDaiBalances;

/// Corollary: no single balance exceeds totalSupply.
invariant daiBalanceAtMostSupply(address a)
    balanceOf(a) <= totalSupply()
    {
        preserved {
            requireInvariant daiSupplyIsSum();
        }
    }
