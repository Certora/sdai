/*
 * maker-models / Dai: supply invariant of the scene's DAI token (certora/harnesses/Dai.sol, a port
 * of mainnet dss dai.sol), proven with Dai as the verified contract, so the invariant base case runs
 * Dai's constructor. Properties: dai_supply_is_sum, dai_pairwise_balance_bound (pass 4).
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

// daiBalMirror (pass 4) mirrors balanceOf entry-wise (0 initially; every store copies the new
// value). It exists only so that the CVL `usum` construct can be applied to it (sums are
// supported over ghost mappings only, expr.html "Ghost Mapping Sums"); see
// dai_pairwise_balance_bound below.
ghost mapping(address => uint256) daiBalMirror {
    init_state axiom forall address a. daiBalMirror[a] == 0;
    // The prover tracks the usum of a ghost mapping as its own term, linked to the entries only
    // through writes (run 61dbf89d: base case with all entries 0 but usum 1), so the initial
    // value of the sum is stated too; it is the sum of the all-zero mapping above.
    init_state axiom (usum address a. daiBalMirror[a]) == 0;
}

hook Sstore currentContract.balanceOf[KEY address a] uint256 newBal (uint256 oldBal) {
    sumDaiBalances = sumDaiBalances + newBal - oldBal;
    daiBalMirror[a] = newBal;
}

// Each balance is one non-negative term of the sum, so it is at most the sum. It applies to every
// Dai balance read, so it is also in force in daiMirrorMatchesBalance and daiPairwiseBalanceBound
// (sound: it states a fact that holds whenever the sum ghost is correct).
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

// ---------------------------------------------------------------------------
// dai_pairwise_balance_bound (pass 4)
//
// balanceOf(a) + balanceOf(b) <= totalSupply for a != b is not inductive on its own (a transfer
// from a third account c needs a bound on three balances), so it is derived from the proven
// daiSupplyIsSum through two auxiliary invariants that tie the scalar ghost sumDaiBalances to the
// entry-wise mirror daiBalMirror, whose `usum` the prover knows to be >= the sum of any finite
// subset of its (non-negative) entries (expr.html: "the usum is larger than any value in the
// ghost mapping and ... even larger than the sum of any finite subset of values").
// ---------------------------------------------------------------------------

/// The mirror agrees with storage entry-wise (base: both 0; step: the Sstore hook copies every write).
invariant daiMirrorMatchesBalance(address a)
    daiBalMirror[a] == balanceOf(a);

/// The scalar sum ghost of daiSupplyIsSum equals the unsigned sum of the mirror (base: both 0;
/// step: the Sstore hook changes both by newBal - oldBal).
/// The Sstore hook sets daiBalMirror[a] = newBal, so the usum moves by newBal - mirror[a]; this equals
/// the scalar's move newBal - oldBal only if mirror[a] == balanceOf[a] before the write (run
/// 61dbf89d showed the step fails otherwise). The preserved blocks therefore assume the proven
/// daiMirrorMatchesBalance for every account whose balance the method writes; methods that write
/// no balance (approve, permit, rely, deny) need nothing.
invariant daiSumGhostIsMirrorUsum()
    sumDaiBalances == (usum address u. daiBalMirror[u])
    {
        preserved transfer(address dst, uint256 wad) with (env e) {
            requireInvariant daiMirrorMatchesBalance(e.msg.sender);
            requireInvariant daiMirrorMatchesBalance(dst);
        }
        preserved transferFrom(address src, address dst, uint256 wad) with (env e) {
            requireInvariant daiMirrorMatchesBalance(src);
            requireInvariant daiMirrorMatchesBalance(dst);
        }
        preserved push(address usr, uint256 wad) with (env e) {
            requireInvariant daiMirrorMatchesBalance(e.msg.sender);
            requireInvariant daiMirrorMatchesBalance(usr);
        }
        preserved pull(address usr, uint256 wad) with (env e) {
            requireInvariant daiMirrorMatchesBalance(usr);
            requireInvariant daiMirrorMatchesBalance(e.msg.sender);
        }
        preserved move(address src, address dst, uint256 wad) with (env e) {
            requireInvariant daiMirrorMatchesBalance(src);
            requireInvariant daiMirrorMatchesBalance(dst);
        }
        preserved mint(address usr, uint256 wad) with (env e) {
            requireInvariant daiMirrorMatchesBalance(usr);
        }
        preserved burn(address usr, uint256 wad) with (env e) {
            requireInvariant daiMirrorMatchesBalance(usr);
        }
    }

/// dai_pairwise_balance_bound: in every reachable Dai state (the three invariants assumed below are
/// proven over Dai's constructor and every Dai method), two distinct accounts hold at most the
/// total supply together. The only bare require is the property's hypothesis a != b.
rule daiPairwiseBalanceBound(address a, address b) {
    requireInvariant daiSupplyIsSum();
    requireInvariant daiSumGhostIsMirrorUsum();
    requireInvariant daiMirrorMatchesBalance(a);
    requireInvariant daiMirrorMatchesBalance(b);
    require a != b; // property hypothesis (for a == b the claim is 2 * balance <= supply, false in general)

    assert balanceOf(a) + balanceOf(b) <= totalSupply(),
        "two distinct accounts hold more DAI than totalSupply";
}
