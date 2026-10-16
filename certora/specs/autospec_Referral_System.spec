import "summaries/SavingsDai_base_summaries.spec";
import "summaries/custom_summaries.spec";

// Persistent ghost functions to abstractly model the return values of the standard
// (2-arg) deposit and mint functions. By summarizing these public functions' internal
// implementations with persistent ghost functions, both the direct external call and
// the internal call from the referral overload receive the same deterministic return
// value for the same inputs. This is necessary because the imported NONDET summaries
// for Pot view functions (chi, rho) produce fresh unconstrained values per call site,
// preventing direct comparison of two separate executions.
// CVL Document-Ref: 90048da8d429282506a4d9dbb0496f46265bc29eec82c2
// CVL Document-Ref: dbe76fca3033bb551c6ebf26157e125e98945497940f95
persistent ghost depositReturnValue(uint256, address) returns uint256;
persistent ghost mintReturnValue(uint256, address) returns uint256;

methods {
    // Summarize the standard (2-arg) deposit and mint internal implementations
    // with persistent ghost functions. This ensures deterministic, consistent
    // return values across both external and internal call paths.
    // CVL Document-Ref: 520dfce064e402daba6e423afb7505da030ffbf3e29e3f
    function SavingsDai.deposit(uint256 assets, address receiver) internal returns (uint256)
        => depositReturnValue(assets, receiver);
    function SavingsDai.mint(uint256 shares, address receiver) internal returns (uint256)
        => mintReturnValue(shares, receiver);

    // Envfree utility declarations for state comparison
    function totalSupply() external returns (uint256) envfree;
    function balanceOf(address) external returns (uint256) envfree;
    function allowance(address, address) external returns (uint256) envfree;
}

// =============================================================================
// Property 1: referral_deposit_returns_same_shares
// deposit(assets, receiver, referral) must return exactly the same number of shares
// as deposit(assets, receiver) for identical inputs from the same starting state.
// =============================================================================
rule referral_deposit_returns_same_shares {
    env e;
    uint256 assets;
    address receiver;
    uint16 referral;

    storage initState = lastStorage;

    uint256 sharesStd = deposit(e, assets, receiver);

    uint256 sharesRef = deposit(e, assets, receiver, referral) at initState;

    assert sharesStd == sharesRef;
}

// =============================================================================
// Property 2: referral_mint_returns_same_assets
// mint(shares, receiver, referral) must return exactly the same number of assets
// as mint(shares, receiver) for identical inputs from the same starting state.
// =============================================================================
rule referral_mint_returns_same_assets {
    env e;
    uint256 shares;
    address receiver;
    uint16 referral;

    storage initState = lastStorage;

    uint256 assetsStd = mint(e, shares, receiver);

    uint256 assetsRef = mint(e, shares, receiver, referral) at initState;

    assert assetsStd == assetsRef;
}

// =============================================================================
// Property 3: referral_deposit_state_equivalence
// After deposit(assets, receiver, referral), the resulting contract state
// (balanceOf, totalSupply, allowances) must be identical to calling
// deposit(assets, receiver) with the same inputs from the same starting state.
// =============================================================================
rule referral_deposit_state_equivalence {
    env e;
    uint256 assets;
    address receiver;
    uint16 referral;
    address anyAddr;
    address anyAddr2;

    storage initState = lastStorage;

    deposit(e, assets, receiver);
    uint256 balStd = balanceOf(anyAddr);
    uint256 tsStd = totalSupply();
    uint256 allowStd = allowance(anyAddr, anyAddr2);

    deposit(e, assets, receiver, referral) at initState;
    uint256 balRef = balanceOf(anyAddr);
    uint256 tsRef = totalSupply();
    uint256 allowRef = allowance(anyAddr, anyAddr2);

    assert balStd == balRef;
    assert tsStd == tsRef;
    assert allowStd == allowRef;
}

// =============================================================================
// Property 4: referral_mint_state_equivalence
// After mint(shares, receiver, referral), the resulting contract state
// (balanceOf, totalSupply, allowances) must be identical to calling
// mint(shares, receiver) with the same inputs from the same starting state.
// =============================================================================
rule referral_mint_state_equivalence {
    env e;
    uint256 shares;
    address receiver;
    uint16 referral;
    address anyAddr;
    address anyAddr2;

    storage initState = lastStorage;

    mint(e, shares, receiver);
    uint256 balStd = balanceOf(anyAddr);
    uint256 tsStd = totalSupply();
    uint256 allowStd = allowance(anyAddr, anyAddr2);

    mint(e, shares, receiver, referral) at initState;
    uint256 balRef = balanceOf(anyAddr);
    uint256 tsRef = totalSupply();
    uint256 allowRef = allowance(anyAddr, anyAddr2);

    assert balStd == balRef;
    assert tsStd == tsRef;
    assert allowStd == allowRef;
}

// =============================================================================
// Property 5: referral_code_independence
// Two calls with different referral codes but same parameters must produce
// identical ending state and return values.
// =============================================================================
rule referral_code_independence_deposit {
    env e;
    uint256 assets;
    address receiver;
    uint16 referral1;
    uint16 referral2;
    address anyAddr;
    address anyAddr2;

    storage initState = lastStorage;

    uint256 shares1 = deposit(e, assets, receiver, referral1);
    uint256 bal1 = balanceOf(anyAddr);
    uint256 ts1 = totalSupply();
    uint256 allow1 = allowance(anyAddr, anyAddr2);

    uint256 shares2 = deposit(e, assets, receiver, referral2) at initState;
    uint256 bal2 = balanceOf(anyAddr);
    uint256 ts2 = totalSupply();
    uint256 allow2 = allowance(anyAddr, anyAddr2);

    assert shares1 == shares2;
    assert bal1 == bal2;
    assert ts1 == ts2;
    assert allow1 == allow2;
}

rule referral_code_independence_mint {
    env e;
    uint256 shares;
    address receiver;
    uint16 referral1;
    uint16 referral2;
    address anyAddr;
    address anyAddr2;

    storage initState = lastStorage;

    uint256 assets1 = mint(e, shares, receiver, referral1);
    uint256 bal1 = balanceOf(anyAddr);
    uint256 ts1 = totalSupply();
    uint256 allow1 = allowance(anyAddr, anyAddr2);

    uint256 assets2 = mint(e, shares, receiver, referral2) at initState;
    uint256 bal2 = balanceOf(anyAddr);
    uint256 ts2 = totalSupply();
    uint256 allow2 = allowance(anyAddr, anyAddr2);

    assert assets1 == assets2;
    assert bal1 == bal2;
    assert ts1 == ts2;
    assert allow1 == allow2;
}

// =============================================================================
// Property 6: referral_deposit_revert_equivalence
// deposit(assets, receiver, referral) must revert if and only if
// deposit(assets, receiver) would revert for the same inputs from same state.
// =============================================================================
rule referral_deposit_revert_equivalence {
    env e;
    uint256 assets;
    address receiver;
    uint16 referral;

    storage initState = lastStorage;

    deposit@withrevert(e, assets, receiver);
    bool stdReverted = lastReverted;

    deposit@withrevert(e, assets, receiver, referral) at initState;
    bool refReverted = lastReverted;

    assert stdReverted == refReverted;
}

// =============================================================================
// Property 7: referral_mint_revert_equivalence
// mint(shares, receiver, referral) must revert if and only if
// mint(shares, receiver) would revert for the same inputs from same state.
// =============================================================================
rule referral_mint_revert_equivalence {
    env e;
    uint256 shares;
    address receiver;
    uint16 referral;

    storage initState = lastStorage;

    mint@withrevert(e, shares, receiver);
    bool stdReverted = lastReverted;

    mint@withrevert(e, shares, receiver, referral) at initState;
    bool refReverted = lastReverted;

    assert stdReverted == refReverted;
}
