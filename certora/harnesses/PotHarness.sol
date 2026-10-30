// SPDX-License-Identifier: AGPL-3.0-or-later
pragma solidity 0.8.17;

import {PotMock} from "../../src/test/mocks/PotMock.sol";

/// PotMock is a faithful copy of mainnet Pot's join/exit/file/cage, but it replaces
/// drip() with a test-only setYield(). SavingsDai calls pot.drip(), so this harness
/// restores mainnet Pot's drip() (dss/src/pot.sol) to model the deployed system.
contract PotHarness is PotMock {
    constructor(address vat_) PotMock(vat_) {}

    function drip() external returns (uint256 tmp) {
        require(block.timestamp >= rho, "Pot/invalid-now");
        tmp = _rpow(dsr, block.timestamp - rho, RAY) * chi / RAY;
        uint256 chi_ = tmp - chi;
        chi = tmp;
        rho = block.timestamp;
        vat.suck(address(vow), address(this), Pie * chi_);
    }
}
