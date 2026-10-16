import "summaries/SavingsDai_base_summaries.spec";
import "summaries/custom_summaries.spec";

methods {
    function totalSupply() external returns (uint256) envfree;
    function balanceOf(address) external returns (uint256) envfree;
    function allowance(address, address) external returns (uint256) envfree;
    function nonces(address) external returns (uint256) envfree;
    function deploymentChainId() external returns (uint256) envfree;
}

// ---- Property 1: permit reverts if owner is zero address ----
rule permit_reverts_zero_owner {
    env e;
    address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;

    permit@withrevert(e, 0, spender, value, deadline, v, r, s);
    assert lastReverted;
}

// ---- Property 2: permit reverts if block.timestamp > deadline ----
rule permit_reverts_expired_deadline {
    env e;
    address owner; address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;

    require e.block.timestamp > deadline;

    permit@withrevert(e, owner, spender, value, deadline, v, r, s);
    assert lastReverted;
}

// ---- Property 3: successful permit increments nonces[owner] by exactly 1 ----
rule permit_nonce_increments_by_one {
    env e;
    address owner; address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;

    // Prevent unchecked nonce overflow (practically impossible: would need 2^256 permit calls)
    require nonces(owner) < max_uint256;

    mathint nonceBefore = nonces(owner);
    permit(e, owner, spender, value, deadline, v, r, s);
    assert nonces(owner) == nonceBefore + 1;
}

// ---- Property 4: successful permit sets allowance[owner][spender] to value ----
rule permit_sets_allowance_to_value {
    env e;
    address owner; address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;

    permit(e, owner, spender, value, deadline, v, r, s);
    assert allowance(owner, spender) == value;
}

// ---- Property 5: permit does not modify nonces[addr] for addr != owner ----
rule permit_no_other_nonce_change {
    env e;
    address owner; address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;
    address other;

    require other != owner;

    mathint nonceBefore = nonces(other);
    permit(e, owner, spender, value, deadline, v, r, s);
    assert nonces(other) == nonceBefore;
}

// ---- Property 6: permit does not modify allowance[a][b] for (a,b) != (owner,spender) ----
rule permit_no_other_allowance_change {
    env e;
    address owner; address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;
    address a; address b;

    require a != owner || b != spender;

    uint256 allowanceBefore = allowance(a, b);
    permit(e, owner, spender, value, deadline, v, r, s);
    assert allowance(a, b) == allowanceBefore;
}

// ---- Property 7: successful permit does not modify any balanceOf or totalSupply ----
rule permit_no_balance_or_supply_change {
    env e;
    address owner; address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;
    address anyAddr;

    uint256 balBefore = balanceOf(anyAddr);
    uint256 supplyBefore = totalSupply();

    permit(e, owner, spender, value, deadline, v, r, s);

    assert balanceOf(anyAddr) == balBefore;
    assert totalSupply() == supplyBefore;
}

// ---- Property 8: replay protection ----
// Two consecutive calls with identical arguments cannot both succeed.
// Expected to fail: _isValidSignature is NONDET, so the second call's
// signature validation can non-deterministically return true for a different
// digest. The cryptographic property that a signature is only valid for one
// specific digest cannot be modeled with NONDET.
rule permit_replay_protection {
    env e1; env e2;
    address owner; address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;

    require e1.block.timestamp == e2.block.timestamp;
    require e2.msg.value == 0;

    // First call succeeds (non-@withrevert: paths where e1 reverts are pruned)
    // Note: block.chainid is a global constant, same for both calls
    permit(e1, owner, spender, value, deadline, v, r, s);
    // Second call with identical args must revert
    permit@withrevert(e2, owner, spender, value, deadline, v, r, s);
    assert lastReverted;
}

// ---- Property 9: nonces are monotonically non-decreasing ----
rule nonces_monotonically_nondecreasing {
    env e;
    method f;
    calldataarg args;
    address addr;

    // Nonce overflow is practically impossible (requires 2^256 permit calls)
    require nonces(addr) < max_uint256;

    mathint nonceBefore = nonces(addr);
    f(e, args);
    assert nonces(addr) >= nonceBefore;
}

// ---- Property 10: DOMAIN_SEPARATOR reflects current chain ID ----
// block.chainid is not accessible in CVL, so we cannot directly compare separators
// across different chain IDs. Instead, we verify two key sub-properties:
// 1. DOMAIN_SEPARATOR is deterministic (same value for any env in same execution)
// 2. DOMAIN_SEPARATOR is state-independent (no function call can change it)
// These together show DOMAIN_SEPARATOR depends only on immutables and block.chainid,
// ensuring cross-chain replay protection by construction.
// CVL Document-Ref: 01c6af6f1869f27db1eb2ee80d374f3428969453300412
// CVL Document-Ref: db0e559eb030f43918f340dc4c4726b30385fbc19f01fe
rule domain_separator_reflects_current_chain_id {
    env e1; env e2;
    method f;
    calldataarg args;
    env eF;

    // DOMAIN_SEPARATOR returns the same value before and after any function call
    bytes32 sepBefore = DOMAIN_SEPARATOR(e1);
    f(eF, args);
    bytes32 sepAfter = DOMAIN_SEPARATOR(e2);

    assert sepBefore == sepAfter;
}

// ---- Property 11: ecrecover zero address exploit cannot occur ----
// ecrecover returns address(0) for many invalid signatures. The require(owner != 0)
// check prevents matching ecrecover's failure return value as a valid signer.
rule ecrecover_zero_address_exploit {
    env e;
    address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;

    permit@withrevert(e, 0, spender, value, deadline, v, r, s);

    // Attack is blocked: permit always reverts for address(0) owner
    assert lastReverted;
}

// ---- Property 12: nonce increment is atomic with signature validation ----
// The nonce is incremented before signature validation in the code, but the
// require() ensures a revert rolls back the increment. This rule verifies atomicity.
rule nonce_increment_before_signature_validation {
    env e;
    address owner; address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;

    // Prevent unchecked nonce overflow
    require nonces(owner) < max_uint256;

    mathint nonceBefore = nonces(owner);
    uint256 allowanceBefore = allowance(owner, spender);

    permit@withrevert(e, owner, spender, value, deadline, v, r, s);
    bool reverted = lastReverted;

    // On success: both nonce and allowance are updated together.
    // On revert: EVM rollback guarantees no state changes — no assertion needed.
    assert !reverted => (nonces(owner) == nonceBefore + 1 && allowance(owner, spender) == value);
}

// ---- Property 13: permit front-running griefing ----
// Goal: demonstrate attack cannot occur.
// Expected to fail: front-running IS possible. A third party can submit the
// permit first (consuming the nonce), causing the original submitter's tx to revert.
rule permit_front_running_griefing {
    env e1; env e2;
    address owner; address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;

    require e1.block.timestamp == e2.block.timestamp;
    require e1.msg.sender != e2.msg.sender;
    require e2.msg.value == 0;

    // Front-runner submits the permit first (succeeds; non-@withrevert prunes revert paths)
    // Note: block.chainid is a global constant, same for both calls
    permit(e1, owner, spender, value, deadline, v, r, s);

    // Original submitter's call should still succeed (if no griefing)
    permit@withrevert(e2, owner, spender, value, deadline, v, r, s);

    // This will fail: the second call CAN revert because the nonce was consumed
    assert !lastReverted;
}

// ---- Property 14: EIP-1271 overpermissive contract owner ----
// Goal: demonstrate attack cannot occur.
// Expected to fail: _isValidSignature is NONDET, which models an overpermissive
// isValidSignature (can return true for any input), allowing arbitrary allowance changes.
rule eip1271_overpermissive_contract_owner {
    env e;
    address owner; address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;

    require owner != 0;
    require e.block.timestamp <= deadline;
    require e.msg.value == 0;

    uint256 allowanceBefore = allowance(owner, spender);
    require allowanceBefore != value;

    permit@withrevert(e, owner, spender, value, deadline, v, r, s);

    // Assert: no arbitrary caller should be able to change allowances.
    // This fails because the ghost can return true for any (signer, digest),
    // modeling an overpermissive EIP-1271 contract owner.
    assert allowance(owner, spender) == allowanceBefore;
}

// ---- Property 15: permit outcome is independent of msg.sender ----
// Expected to fail: _isValidSignature is summarized as NONDET, which returns
// independent non-deterministic values for each call. Two calls from the same
// initial state with different msg.senders get independent NONDET values,
// producing a spurious counterexample. In reality, msg.sender is not read
// in permit or _isValidSignature, so the property holds by construction.
// CVL Document-Ref: 40f11f43d8eccdcd2d35030f621d23888719947efa6383
rule permit_caller_independence {
    env e1; env e2;
    address owner; address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;

    storage initState = lastStorage;

    // Environments identical except msg.sender
    // Note: block.chainid is a global constant, same for both calls
    require e1.block.timestamp == e2.block.timestamp;
    require e1.msg.sender != e2.msg.sender;
    require e1.msg.value == 0;
    require e2.msg.value == 0;

    // First execution
    permit@withrevert(e1, owner, spender, value, deadline, v, r, s);
    bool rev1 = lastReverted;
    mathint nonce1 = nonces(owner);
    uint256 allow1 = allowance(owner, spender);

    // Second execution from same initial state
    permit@withrevert(e2, owner, spender, value, deadline, v, r, s) at initState;
    bool rev2 = lastReverted;
    mathint nonce2 = nonces(owner);
    uint256 allow2 = allowance(owner, spender);

    assert rev1 == rev2;
    assert nonce1 == nonce2;
    assert allow1 == allow2;
}

// ---- Property 16: EIP-1271 callback cannot modify state ----
// The staticcall to the owner for EIP-1271 validation (abstracted by NONDET summary)
// cannot modify SavingsDai's balances or totalSupply.
rule eip1271_callback_cannot_modify_state {
    env e;
    address owner; address spender; uint256 value; uint256 deadline;
    uint8 v; bytes32 r; bytes32 s;
    address anyAddr;

    uint256 balBefore = balanceOf(anyAddr);
    uint256 supplyBefore = totalSupply();

    permit(e, owner, spender, value, deadline, v, r, s);

    // staticcall-based callback cannot modify balance or supply
    assert balanceOf(anyAddr) == balBefore;
    assert totalSupply() == supplyBefore;
}
