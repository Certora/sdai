/*
 * maker-models / Pot: invariants of the scene's Pot (certora/harnesses/Pot.sol, a port of dss pot.sol),
 * proven with Pot as the verified contract, so the invariant base case runs Pot's constructor.
 * Properties: pot_chi_at_least_ray, pot_total_pie_is_sum (certora/properties/maker-models.properties.json).
 *
 * scene.spec is imported for one reason: its summary of Pot._rpow by the uninterpreted ghost
 * rpowG(x, n, base) is the summary every SavingsDai spec runs under, so these results are about the
 * same Pot model. Its other entries (SavingsDai._rpow, wildcard isValidSignature/hope/approve/vat/dai
 * with the default UNRESOLVED policy) never apply here: Pot makes no such call, and its only external
 * calls (vat.suck, vat.move) are resolved to the scene Vat by base.conf's link Pot:vat=Vat.
 * Nothing in this spec constrains rpowG, so chi >= RAY holds for EVERY value rpow could return.
 */
import "../scene.spec";

methods {
    function chi() external returns (uint256) envfree;
    function Pie() external returns (uint256) envfree;
    function pie(address) external returns (uint256) envfree;
}

// ---------------------------------------------------------------------------
// pot_chi_at_least_ray
// Base case: the constructor sets chi = RAY. Step: only drip writes chi, and it reverts unless
// the new value is >= the old one (checked `tmp - chi`).
// ---------------------------------------------------------------------------

invariant potChiAtLeastRay()
    chi() >= RAY();

// ---------------------------------------------------------------------------
// pot_total_pie_is_sum
// sumPie mirrors the sum of Pot.pie over all addresses: it starts at 0 (the constructor writes
// no pie entry) and every write to pie[a] adds new - old.
// ---------------------------------------------------------------------------

ghost mathint sumPie {
    init_state axiom sumPie == 0;
}

hook Sstore currentContract.pie[KEY address a] uint256 newPie (uint256 oldPie) {
    sumPie = sumPie + newPie - oldPie;
}

// Each pie entry is one non-negative term of the sum sumPie mirrors, so it is at most the sum.
// Used only by the corollary potPieCoversEachPie (the sum invariant does not need it).
hook Sload uint256 p currentContract.pie[KEY address a] {
    require sumPie >= to_mathint(p);
}

invariant potTotalPieIsSum()
    to_mathint(Pie()) == sumPie;

/// Corollary: Pie >= pie[a] for every account a (in particular a = sDAI; this is
/// maker-integration's pre_PieCoversSdaiPie).
invariant potPieCoversEachPie(address a)
    Pie() >= pie(a)
    {
        preserved {
            requireInvariant potTotalPieIsSum();
        }
    }
