// SPDX-License-Identifier: AGPL-3.0-or-later

/// Pot.sol -- Dai Savings Rate
///
/// Verification model of MakerDAO dss `pot.sol` (https://github.com/makerdao/dss/blob/master/src/pot.sol),
/// ported to 0.8.17 so it compiles with the rest of the scene. The repository's own
/// src/test/mocks/PotMock.sol replaces `drip` with a test-only `setYield`, but SavingsDai calls
/// `drip()`, so the real logic is reproduced here. Arithmetic matches dss: checked add/sub/mul,
/// rmul = x * y / RAY, and the same `_rpow` used by SavingsDai.

pragma solidity ^0.8.13;

interface VatLike {
    function move(address,address,uint256) external;
    function suck(address,address,uint256) external;
}

contract Pot {
    // --- Data ---
    mapping (address => uint256) public wards;

    mapping (address => uint256) public pie;  // Normalised Savings Dai [wad]

    uint256 public Pie;   // Total Normalised Savings Dai  [wad]
    uint256 public dsr;   // The Dai Savings Rate          [ray]
    uint256 public chi;   // The Rate Accumulator          [ray]

    VatLike public vat;   // CDP Engine
    address public vow;   // Debt Engine
    uint256 public rho;   // Time of last drip     [unix epoch time]

    uint256 public live;  // Active Flag

    uint256 constant RAY = 10 ** 27;

    modifier auth {
        require(wards[msg.sender] == 1, "Pot/not-authorized");
        _;
    }

    constructor(address vat_) {
        wards[msg.sender] = 1;
        vat = VatLike(vat_);
        dsr = RAY;
        chi = RAY;
        rho = block.timestamp;
        live = 1;
    }

    // --- Math ---
    function _rpow(uint256 x, uint256 n, uint256 base) internal pure returns (uint256 z) {
        assembly {
            switch x case 0 {switch n case 0 {z := base} default {z := 0}}
            default {
                switch mod(n, 2) case 0 { z := base } default { z := x }
                let half := div(base, 2)  // for rounding.
                for { n := div(n, 2) } n { n := div(n,2) } {
                    let xx := mul(x, x)
                    if iszero(eq(div(xx, x), x)) { revert(0,0) }
                    let xxRound := add(xx, half)
                    if lt(xxRound, xx) { revert(0,0) }
                    x := div(xxRound, base)
                    if mod(n,2) {
                        let zx := mul(z, x)
                        if and(iszero(iszero(x)), iszero(eq(div(zx, x), z))) { revert(0,0) }
                        let zxRound := add(zx, half)
                        if lt(zxRound, zx) { revert(0,0) }
                        z := div(zxRound, base)
                    }
                }
            }
        }
    }

    function _rmul(uint256 x, uint256 y) internal pure returns (uint256 z) {
        z = x * y / RAY;
    }

    // --- Administration ---
    function rely(address guy) external auth { wards[guy] = 1; }
    function deny(address guy) external auth { wards[guy] = 0; }

    function file(bytes32 what, uint256 data) external auth {
        require(live == 1, "Pot/not-live");
        require(block.timestamp == rho, "Pot/rho-not-updated");
        if (what == "dsr") dsr = data;
        else revert("Pot/file-unrecognized-param");
    }

    function file(bytes32 what, address addr) external auth {
        if (what == "vow") vow = addr;
        else revert("Pot/file-unrecognized-param");
    }

    function cage() external auth {
        live = 0;
        dsr = RAY;
    }

    // --- Savings Rate Accumulation ---
    function drip() external returns (uint256 tmp) {
        require(block.timestamp >= rho, "Pot/invalid-now");
        tmp = _rmul(_rpow(dsr, block.timestamp - rho, RAY), chi);
        uint256 chi_ = tmp - chi;
        chi = tmp;
        rho = block.timestamp;
        vat.suck(address(vow), address(this), Pie * chi_);
    }

    // --- Savings Dai Management ---
    function join(uint256 wad) external {
        require(block.timestamp == rho, "Pot/rho-not-updated");
        pie[msg.sender] = pie[msg.sender] + wad;
        Pie             = Pie             + wad;
        vat.move(msg.sender, address(this), chi * wad);
    }

    function exit(uint256 wad) external {
        pie[msg.sender] = pie[msg.sender] - wad;
        Pie             = Pie             - wad;
        vat.move(address(this), msg.sender, chi * wad);
    }
}
