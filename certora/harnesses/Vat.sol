// SPDX-License-Identifier: AGPL-3.0-or-later

/// Vat.sol -- verification model of the MakerDAO Vat, reduced to the DAI-ledger surface the
/// SavingsDai scene uses (hope/nope, move, suck, heal). Function bodies are copied verbatim from
/// src/test/mocks/VatMock.sol (itself a 0.8 port of dss vat.sol). The collateral/CDP machinery
/// (frob, fork, grab, fold, ...) is omitted: SavingsDai, Pot and DaiJoin never call it, and
/// VatMock.frob does not compile under the prover's instrumentation ("stack too deep").

pragma solidity ^0.8.13;

contract Vat {
    // --- Data ---
    mapping (address => uint256) public wards;

    mapping(address => mapping (address => uint256)) public can;

    mapping (address => uint256) public dai;  // [rad]
    mapping (address => uint256) public sin;  // [rad]

    uint256 public debt;  // Total Dai Issued    [rad]
    uint256 public vice;  // Total Unbacked Dai  [rad]
    uint256 public live;  // Active Flag

    modifier auth {
        require(wards[msg.sender] == 1, "Vat/not-authorized");
        _;
    }

    function wish(address bit, address usr) internal view returns (bool) {
        return either(bit == usr, can[bit][usr] == 1);
    }

    constructor() {
        wards[msg.sender] = 1;
        live = 1;
    }

    // --- Administration ---
    function rely(address usr) external auth {
        require(live == 1, "Vat/not-live");
        wards[usr] = 1;
    }

    function deny(address usr) external auth {
        require(live == 1, "Vat/not-live");
        wards[usr] = 0;
    }

    // --- Allowance ---
    function hope(address usr) external {
        can[msg.sender][usr] = 1;
    }

    function nope(address usr) external {
        can[msg.sender][usr] = 0;
    }

    // --- Fungibility ---
    function move(address src, address dst, uint256 rad) external {
        require(wish(src, msg.sender), "Vat/not-allowed");
        dai[src] = dai[src] - rad;
        dai[dst] = dai[dst] + rad;
    }

    function either(bool x, bool y) internal pure returns (bool z) {
        assembly{ z := or(x, y)}
    }

    // --- Settlement ---
    function heal(uint256 rad) external {
        address u = msg.sender;
        sin[u] = sin[u] - rad;
        dai[u] = dai[u] - rad;
        vice   = vice   - rad;
        debt   = debt   - rad;
    }

    function suck(address u, address v, uint256 rad) external auth {
        sin[u] = sin[u] + rad;
        dai[v] = dai[v] + rad;
        vice   = vice   + rad;
        debt   = debt   + rad;
    }
}
