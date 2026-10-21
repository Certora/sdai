// SPDX-License-Identifier: AGPL-3.0-or-later

/// DaiJoin.sol -- verification model of the mainnet DaiJoin adapter: the DaiJoin contract of
/// MakerDAO dss `join.sol` (https://github.com/makerdao/dss/blob/master/src/join.sol), ported
/// from 0.5.12 to 0.8.17 with the original checked `mul`. Unlike src/test/mocks/DaiJoinMock.sol
/// it keeps `live` / `cage()`: `exit` requires live == 1, so withdrawals through it stop after
/// emergency shutdown.

pragma solidity ^0.8.13;

interface VatLike {
    function move(address,address,uint256) external;
}

interface DSTokenLike {
    function mint(address,uint) external;
    function burn(address,uint) external;
}

contract DaiJoin {
    // --- Auth ---
    mapping (address => uint) public wards;
    function rely(address usr) external auth { wards[usr] = 1; }
    function deny(address usr) external auth { wards[usr] = 0; }
    modifier auth {
        require(wards[msg.sender] == 1, "DaiJoin/not-authorized");
        _;
    }

    VatLike public vat;      // CDP Engine
    DSTokenLike public dai;  // Stablecoin Token
    uint    public live;     // Active Flag

    constructor(address vat_, address dai_) {
        wards[msg.sender] = 1;
        live = 1;
        vat = VatLike(vat_);
        dai = DSTokenLike(dai_);
    }
    function cage() external auth {
        live = 0;
    }
    uint constant ONE = 10 ** 27;
    function mul(uint x, uint y) internal pure returns (uint z) {
        unchecked { require(y == 0 || (z = x * y) / y == x); }
    }
    function join(address usr, uint wad) external {
        vat.move(address(this), usr, mul(ONE, wad));
        dai.burn(msg.sender, wad);
    }
    function exit(address usr, uint wad) external {
        require(live == 1, "DaiJoin/not-live");
        vat.move(msg.sender, address(this), mul(ONE, wad));
        dai.mint(usr, wad);
    }
}
