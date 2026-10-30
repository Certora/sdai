// Structural invariants for Savings Dai (sDAI).
// Scene / links: inlined below from certora/specs/summaries/SavingsDai_call_resolution.spec (aliases savingsDai, potHarness,
// vatMock, daiJoinMock, daiMock). Importing specs must not redeclare them nor import the call-resolution file.
import "summaries/SavingsDai_base_summaries.spec";
import "summaries/rpow_summary.spec";

// ---- Inlined copy of summaries/SavingsDai_call_resolution.spec (aliases + links). ----
// Why inlined instead of imported: CVL hooks in an IMPORTED spec cannot see `using` aliases that come from a file
// that spec imports in turn ("hook contract daiMock ... is undefined"), so component specs could not import this file.
// Keep this block identical to summaries/SavingsDai_call_resolution.spec.
using DaiJoinMock as daiJoinMock;
using DaiMock as daiMock;
using DummyERC20Impl as dummyERC20Impl;
using PotHarness as potHarness;
using SavingsDai as savingsDai;
using VatMock as vatMock;

links {
    savingsDai.pot => potHarness;
    savingsDai.daiJoin => daiJoinMock;
    savingsDai.dai => daiMock;
    savingsDai.vat => vatMock;
    daiJoinMock.vat => vatMock;
    daiJoinMock.dai => daiMock;
    potHarness.vat => vatMock;
}
// ---- end inlined call resolution ----

methods {
    // sDAI
    function totalSupply() external returns (uint256) envfree;
    function balanceOf(address) external returns (uint256) envfree;

    // Pot (getters inherited from PotMock; PotMock itself is not a scene contract, so the receiver is PotHarness)
    function PotHarness.pie(address) external returns (uint256) envfree;
    function PotHarness.Pie() external returns (uint256) envfree;
    function PotHarness.chi() external returns (uint256) envfree;

    // Vat
    function VatMock.dai(address) external returns (uint256) envfree;
    function VatMock.can(address, address) external returns (uint256) envfree;

    // Dai
    function DaiMock.totalSupply() external returns (uint256) envfree;
    function DaiMock.allowance(address, address) external returns (uint256) envfree;

    // ---- Constructor call resolution (base case of every invariant) ----
    // The links block fixes sDAI's immutables (daiJoin, pot, vat, dai) to the scene contracts, but inside the
    // constructor these values are still the free constructor arguments, so the four calls the constructor
    // makes (daiJoin.vat(), daiJoin.dai(), vat.hope(x) twice, dai.approve(...)) are unresolved and havoc all
    // state. These wildcard entries use the default UNRESOLVED policy, so they ONLY replace calls the prover
    // could not resolve -- after construction every call is linked and none of these entries applies.
    // Each one runs the real scene-contract code (or returns the linked value), see the CVL functions below.
    function _.vat() external => ctorDaiJoinVat(calledContract) expect address;
    function _.dai() external => ctorDaiJoinDai(calledContract) expect address;
    function _.hope(address usr) external => ctorHope(calledContract, executingContract, usr) expect void;
    function _.approve(address spender, uint256 value) external
        => ctorApprove(calledContract, executingContract, spender, value) expect bool;
}

definition MAX_UINT256() returns uint256 = max_uint256;

// ---------------------------------------------------------------------------------------------------------
// Constructor call resolution. The only ASSUMPTIONS here are the two constructor arguments:
// _daiJoin == daiJoinMock and _pot == potHarness -- exactly what the shared links block already assumes for
// every post-construction state (savingsDai.daiJoin => daiJoinMock, savingsDai.pot => potHarness).
// Everything else is asserted (it follows from the code), not assumed.
// ---------------------------------------------------------------------------------------------------------
ghost mathint ctorHopeCalls {
    init_state axiom ctorHopeCalls == 0;
}

function ctorDaiJoinVat(address callee) returns address {
    require callee == daiJoinMock, "deployment assumption (= links block): constructor arg _daiJoin is DaiJoinMock";
    return daiJoinMock.vat;     // linked to vatMock
}

function ctorDaiJoinDai(address callee) returns address {
    assert callee == daiJoinMock, "daiJoin.dai() is called on the same _daiJoin as daiJoin.vat()";
    return daiJoinMock.dai;     // linked to daiMock
}

function ctorHope(address callee, address caller, address usr) {
    assert callee == vatMock, "vat was obtained from daiJoinMock.vat()";
    // sDAI's constructor calls vat.hope(address(daiJoin)) then vat.hope(address(pot)).
    assert ctorHopeCalls == 0 => usr == daiJoinMock, "first hope is for _daiJoin";
    require ctorHopeCalls == 1 => usr == potHarness, "deployment assumption (= links block): constructor arg _pot is PotHarness";
    ctorHopeCalls = ctorHopeCalls + 1;
    env eHope;
    require eHope.msg.sender == caller, "the call is made by the executing contract (sDAI)";
    require eHope.msg.value == 0, "Solidity interface call sends no value";
    vatMock.hope(eHope, usr);
}

function ctorApprove(address callee, address caller, address spender, uint256 value) returns bool {
    assert callee == daiMock, "dai was obtained from daiJoinMock.dai()";
    env eApprove;
    require eApprove.msg.sender == caller, "the call is made by the executing contract (sDAI)";
    require eApprove.msg.value == 0, "Solidity interface call sends no value";
    return daiMock.approve(eApprove, spender, value);
}

// ---------------------------------------------------------------------------------------------------------
// Ghost: sum of DAI balances (supporting invariant daiTotalSupplyEqualsSumOfDaiBalances).
// No init_state axiom: DAI already exists when sDAI is deployed (see the invariant's constructor block).
// ---------------------------------------------------------------------------------------------------------
ghost mathint sumDaiBalances;

hook Sstore daiMock.balanceOf[KEY address a] uint256 newBal (uint256 oldBal) {
    sumDaiBalances = sumDaiBalances + newBal - oldBal;
}

// Same "one non-negative summand <= sum" fact as for sDAI balances below. Without
// daiTotalSupplyEqualsSumOfDaiBalances in scope the ghost is otherwise unconstrained, so this only bounds a free
// variable.
hook Sload uint256 bal daiMock.balanceOf[KEY address a] {
    require bal <= sumDaiBalances, "a single non-negative DAI balance is at most the sum of all DAI balances";
}

// ---------------------------------------------------------------------------------------------------------
// Ghost: sum of sDAI balances (not readable from storage, hence a hook-maintained ghost).
// ---------------------------------------------------------------------------------------------------------
ghost mathint sumBalances {
    // Before the constructor every balanceOf entry is zero, so the sum is zero.
    init_state axiom sumBalances == 0;
}

hook Sstore currentContract.balanceOf[KEY address a] uint256 newBal (uint256 oldBal) {
    sumBalances = sumBalances + newBal - oldBal;
}

// Every individual (non-negative) balance is one summand of sumBalances, so it can never exceed it.
// This is the standard "one summand <= sum" fact that the solver cannot derive from the mathint ghost alone.
// It is needed only to show that the unchecked `balanceOf[to] += value` cannot wrap (the load of
// balanceOf[to] happens after balanceOf[from] has already been decreased, so this gives
// balanceOf[to] + value <= sum == totalSupply <= max_uint256).
hook Sload uint256 bal currentContract.balanceOf[KEY address a] {
    require bal <= sumBalances, "a single non-negative balance is at most the sum of all balances";
}

// =========================================================================================================
// 1. total_supply_equals_sum_of_balances
// Checked against the methods of SavingsDai, PotHarness, VatMock, DaiJoinMock and DaiMock.
// =========================================================================================================
invariant totalSupplyEqualsSumOfBalances()
    totalSupply() == sumBalances
    {
        preserved {
            // _mint does `totalSupply + shares` unchecked; Pot.join(shares) performs the same addition on
            // pie[sDAI] with checked arithmetic, so the equality below rules out a wrapped totalSupply.
            requireInvariant sharesEqualPotPie();
        }
    }

// =========================================================================================================
// 2. shares_equal_pot_pie
// Checked against the methods of SavingsDai, PotHarness, VatMock, DaiJoinMock and DaiMock.
// =========================================================================================================
invariant sharesEqualPotPie()
    potHarness.pie(savingsDai) == totalSupply()
    {
        preserved constructor() {
            // Pot.pie[usr] is only ever written by Pot.join/exit for usr == msg.sender. Before sDAI's
            // constructor runs, its address has never executed code, so it cannot have called Pot.join:
            // its pie is zero.
            require potHarness.pie[savingsDai] == 0, "freshly deployed sDAI has no Pot pie";
        }
        preserved with (env e) {
            // sDAI is a contract: it never originates a transaction. Every call it makes to the Pot happens
            // inside one of its own methods, which are checked here as SavingsDai methods.
            require e.msg.sender != savingsDai, "sDAI never originates a top-level call";
        }
    }

// ---------------------------------------------------------------------------------------------------------
// Ghost: sum of Pot pie over all users (supporting invariant potTotalPieEqualsSumOfPie).
// No init_state axiom: the Pot already exists when sDAI is deployed (see the invariant's constructor block).
// ---------------------------------------------------------------------------------------------------------
ghost mathint sumPie;

hook Sstore potHarness.pie[KEY address a] uint256 newPie (uint256 oldPie) {
    sumPie = sumPie + newPie - oldPie;
}

// "Summand <= sum" facts for the non-negative pie entries: a single pie is at most the sum, and for any other
// user a, pie[a] and pie[sDAI] are two distinct summands, so together they are at most the sum. The second one
// is what Pot.exit by another user needs (Pie - wad >= pie[sDAI]). Without potTotalPieEqualsSumOfPie in scope
// sumPie is a free variable and this only bounds it.
hook Sload uint256 p potHarness.pie[KEY address a] {
    require p <= sumPie, "a single non-negative pie is at most the sum of all pies";
    require a != savingsDai => p + potHarness.pie[savingsDai] <= sumPie,
        "two distinct non-negative pies are at most the sum of all pies";
}

// ---------------------------------------------------------------------------------------------------------
// Supporting invariant (not in the property list): the Pot's Pie equals the sum of all users' pie.
// Checked against the methods of SavingsDai, PotHarness, VatMock, DaiJoinMock and DaiMock, no exclusions.
// ---------------------------------------------------------------------------------------------------------
invariant potTotalPieEqualsSumOfPie()
    potHarness.Pie() == sumPie
    {
        preserved constructor() {
            // Maker-system assumption: the already-deployed Pot's Pie is the sum of its pie entries when sDAI
            // is deployed (true from the Pot's all-zero deployment, and every Pot method keeps it, as the
            // preservation checks show). sDAI's constructor does not touch the Pot.
            require potHarness.Pie == sumPie, "Maker assumption: Pot accounting is consistent at sDAI deployment";
        }
    }

// =========================================================================================================
// 3. pot_total_pie_covers_sdai_pie
// Checked against the methods of SavingsDai, PotHarness, VatMock, DaiJoinMock and DaiMock, no exclusions.
// =========================================================================================================
invariant potTotalPieCoversSdaiPie()
    potHarness.Pie() >= potHarness.pie(savingsDai)
    {
        preserved constructor() {
            // Same justification as in sharesEqualPotPie: a freshly deployed sDAI has no pie.
            require potHarness.pie[savingsDai] == 0, "freshly deployed sDAI has no Pot pie";
        }
        preserved {
            requireInvariant potTotalPieEqualsSumOfPie();
        }
    }

// ---------------------------------------------------------------------------------------------------------
// Trusted actors for the Maker-side invariants (4, 5 and the supporting noVatPermissionsFromPotOrDaiJoin).
// - Maker governance (wards of the Vat, Pot and Dai) is trusted and is not an adversary (NOTES): the top-level
//   caller is not a ward. Ward-only functions (Vat.suck/fold/grab/slip/file/init/cage/rely/deny, Pot.file/cage/
//   rely/deny, Dai.mint/rely/deny) therefore always revert in these checks; the calls the Pot / DaiJoin make to
//   them (Vat.suck in drip, Dai.mint in exit) are nested calls and are NOT affected by this restriction.
// - sDAI, the Pot and DaiJoin are contracts with no private key: they never originate a transaction. Every call
//   they make happens inside one of their own methods, which are checked here as methods of those contracts.
// ---------------------------------------------------------------------------------------------------------
function requireUntrustedExternalCaller(env e) {
    require vatMock.wards[e.msg.sender] == 0, "trusted governance: top-level caller is not a Vat ward";
    require potHarness.wards[e.msg.sender] == 0, "trusted governance: top-level caller is not a Pot ward";
    require daiMock.wards[e.msg.sender] == 0, "trusted governance: top-level caller is not a Dai ward";
    require e.msg.sender != savingsDai, "sDAI never originates a top-level call";
    require e.msg.sender != potHarness, "the Pot never originates a top-level call";
    require e.msg.sender != daiJoinMock, "DaiJoin never originates a top-level call";
}

// ---------------------------------------------------------------------------------------------------------
// Supporting invariant (not in the property list): the Pot and DaiJoin grant no Vat permissions.
// Vat.can[src][x] is written only by hope/nope with src == msg.sender, and neither Pot nor DaiJoin ever calls
// hope/nope. Checked against the methods of all five contracts.
// ---------------------------------------------------------------------------------------------------------
invariant noVatPermissionsFromPotOrDaiJoin(address x)
    vatMock.can(potHarness, x) == 0 && vatMock.can(daiJoinMock, x) == 0
    {
        preserved constructor() {
            // Maker-system assumption: at sDAI deployment the Pot and DaiJoin have granted no Vat permissions
            // (they have no code path calling hope). sDAI's constructor only writes Vat.can[sDAI][*].
            require vatMock.can[potHarness][x] == 0 && vatMock.can[daiJoinMock][x] == 0,
                "Maker assumption: Pot and DaiJoin have no Vat permissions at sDAI deployment";
        }
        preserved with (env e) {
            require e.msg.sender != potHarness, "the Pot never originates a top-level call";
            require e.msg.sender != daiJoinMock, "DaiJoin never originates a top-level call";
        }
    }

// =========================================================================================================
// 4. pot_vat_dai_covers_savings  (Maker-side solvency)
// Checked against the methods of all five contracts except PotHarness.setYield, with the trusted-actor
// restriction above.
// =========================================================================================================
invariant potVatDaiCoversSavings()
    vatMock.dai(potHarness) >= potHarness.chi() * potHarness.Pie()
    // PotHarness.setYield is PotMock's test-only yield hook (chi = (Pie + yield) * RAY / Pie with a suck of only
    // Pie * yield); mainnet Pot has no such function -- the harness restores mainnet drip() instead.
    filtered { f -> f.selector != sig:PotHarness.setYield(uint256).selector }
    {
        preserved constructor() {
            // Maker-system assumption: the already-deployed Pot is solvent when sDAI is deployed. sDAI's
            // constructor only writes Vat.can[sDAI][*] and Dai.allowance[sDAI][*], which do not occur here.
            require vatMock.dai[potHarness] >= potHarness.chi * potHarness.Pie,
                "Maker assumption: Pot is solvent at sDAI deployment";
        }
        preserved with (env e) {
            requireUntrustedExternalCaller(e);
            // Vat.move/frob from src == Pot by the top-level caller need Vat.can[Pot][caller].
            requireInvariant noVatPermissionsFromPotOrDaiJoin(e.msg.sender);
        }
    }

// =========================================================================================================
// 5. daijoin_vat_dai_covers_dai_supply  (Maker-side solvency)
// Checked against the methods of all five contracts, with the trusted-actor restriction above.
// =========================================================================================================
invariant daiJoinVatDaiCoversDaiSupply()
    vatMock.dai(daiJoinMock) >= RAY() * daiMock.totalSupply()
    {
        preserved constructor() {
            // Maker-system assumption: outstanding DAI is fully backed by DaiJoin's Vat dai when sDAI is
            // deployed. sDAI's constructor does not move Vat dai and does not mint/burn DAI.
            require vatMock.dai[daiJoinMock] >= RAY() * daiMock.totalSupply,
                "Maker assumption: DaiJoin backs all DAI at sDAI deployment";
        }
        preserved with (env e) {
            requireUntrustedExternalCaller(e);
            // Vat.move/frob from src == DaiJoin by the top-level caller need Vat.can[DaiJoin][caller].
            requireInvariant noVatPermissionsFromPotOrDaiJoin(e.msg.sender);
            // Dai.burn subtracts from totalSupply unchecked; it is safe only because a single DAI balance never
            // exceeds DAI totalSupply.
            requireInvariant daiTotalSupplyEqualsSumOfDaiBalances();
        }
    }

// ---------------------------------------------------------------------------------------------------------
// Supporting invariant (not in the property list): DAI totalSupply equals the sum of DAI balances.
// Needed by daiJoinVatDaiCoversDaiSupply (Dai.burn / Dai.transferFrom use unchecked arithmetic).
// Checked against the methods of SavingsDai, PotHarness, VatMock, DaiJoinMock and DaiMock.
// ---------------------------------------------------------------------------------------------------------
invariant daiTotalSupplyEqualsSumOfDaiBalances()
    daiMock.totalSupply() == sumDaiBalances
    {
        preserved constructor() {
            // Maker-system assumption: the already-deployed DAI token's totalSupply is the sum of its balances
            // when sDAI is deployed (DaiMock's constructor starts from all-zero storage and every DAI method
            // keeps this, as the preservation checks below show). sDAI's constructor does not touch balances.
            require daiMock.totalSupply == sumDaiBalances, "Maker assumption: DAI accounting is consistent at sDAI deployment";
        }
    }

// =========================================================================================================
// 6. sdai_setup_permissions_persist
// Checked against the methods of SavingsDai, PotHarness, VatMock, DaiJoinMock and DaiMock.
// =========================================================================================================
invariant sdaiSetupPermissionsPersist()
    vatMock.can(savingsDai, daiJoinMock) == 1
    && vatMock.can(savingsDai, potHarness) == 1
    && daiMock.allowance(savingsDai, daiJoinMock) == MAX_UINT256()
    {
        preserved with (env e) {
            // Vat.can[sDAI][*] and Dai.allowance[sDAI][*] can only be written by calls whose msg.sender is
            // sDAI (hope/nope/approve/...). sDAI never originates a transaction, and it makes no such call
            // after its constructor (checked here as SavingsDai methods).
            require e.msg.sender != savingsDai, "sDAI never originates a top-level call";
        }
        preserved DaiMock.permit(address owner, address spender, uint256 value, uint256 deadline, bytes signature) with (env e) {
            require e.msg.sender != savingsDai, "sDAI never originates a top-level call";
            // A Dai permit for owner == sDAI needs either an ECDSA signature by sDAI's address (no private
            // key exists for a contract address) or sDAI.isValidSignature (sDAI implements no such function,
            // so the staticcall fails). The prover models ecrecover as an arbitrary function, so this
            // cryptographic fact must be assumed.
            require owner != savingsDai, "nobody can sign a Dai permit on behalf of sDAI";
        }
        preserved DaiMock.permit(address owner, address spender, uint256 value, uint256 deadline, uint8 v, bytes32 r, bytes32 s) with (env e) {
            require e.msg.sender != savingsDai, "sDAI never originates a top-level call";
            require owner != savingsDai, "nobody can sign a Dai permit on behalf of sDAI";
        }
    }

// ---------------------------------------------------------------------------------------------------------
// Supporting invariant (added at the Phase 6 round-1 barrier, requested by the erc4626-vault generator):
// the Pot's rate accumulator never drops below RAY. Pot's constructor sets chi = RAY; drip computes
// tmp - chi with checked arithmetic, so it reverts rather than lowering chi; the mock-only setYield sets
// chi = (Pie + yield) * RAY / Pie >= RAY. Proven over every method of the 5 scene contracts.
// ---------------------------------------------------------------------------------------------------------
invariant chiAtLeastRay()
    potHarness.chi() >= RAY()
    {
        preserved constructor() {
            // Maker-system assumption: the already-deployed Pot has chi >= RAY (its constructor sets RAY and,
            // as this invariant proves, no Pot method lowers it). sDAI's constructor does not touch the Pot.
            require potHarness.chi >= RAY(), "Maker assumption: Pot chi >= RAY at sDAI deployment";
        }
    }
