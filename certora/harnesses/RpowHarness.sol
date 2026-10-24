// SPDX-License-Identifier: AGPL-3.0-or-later

/// RpowHarness.sol -- verification harness (erc4626-rpow-probe, pass 4).
///
/// `rpow(x, n)` is a VERBATIM copy of `SavingsDai._rpow(uint256 x, uint256 n)` (src/SavingsDai.sol,
/// same RAY constant, same assembly, byte-for-byte identical body, extracted with sed from the
/// source), exposed as an external function so the rpow probe can call the real fixed-point
/// exponentiation on its own, without the rest of convertToAssets. Pot._rpow(x, n, base) is the
/// same algorithm with `base` in place of RAY (Pot always passes base = RAY).

pragma solidity ^0.8.17;

contract RpowHarness {
    uint256 private constant RAY = 10 ** 27;

    function rpow(uint256 x, uint256 n) external pure returns (uint256 z) {
        return _rpow(x, n);
    }

    /// One rounded fixed-point multiplication step of the _rpow loop, copied verbatim from its
    /// `if mod(n,2) { ... }` branch (z := round(z * x / RAY), reverting on overflow). The loop's
    /// squaring step `x := round(x * x / RAY)` is the same computation with z = x (its overflow
    /// check `iszero(eq(div(xx, x), x))` is equivalent to this one's for every x: for x = 0 the
    /// EVM's div(0, 0) = 0, so neither check fires).
    function rmulStep(uint256 z, uint256 x) external pure returns (uint256) {
        assembly {
            let half := div(RAY, 2)  // for rounding.
            let zx := mul(z, x)
            if and(iszero(iszero(x)), iszero(eq(div(zx, x), z))) { revert(0,0) }
            let zxRound := add(zx, half)
            if lt(zxRound, zx) { revert(0,0) }
            z := div(zxRound, RAY)
        }
        return z;
    }

    function _rpow(uint256 x, uint256 n) internal pure returns (uint256 z) {
        assembly {
            switch x case 0 {switch n case 0 {z := RAY} default {z := 0}}
            default {
                switch mod(n, 2) case 0 { z := RAY } default { z := x }
                let half := div(RAY, 2)  // for rounding.
                for { n := div(n, 2) } n { n := div(n,2) } {
                    let xx := mul(x, x)
                    if iszero(eq(div(xx, x), x)) { revert(0,0) }
                    let xxRound := add(xx, half)
                    if lt(xxRound, xx) { revert(0,0) }
                    x := div(xxRound, RAY)
                    if mod(n,2) {
                        let zx := mul(z, x)
                        if and(iszero(iszero(x)), iszero(eq(div(zx, x), z))) { revert(0,0) }
                        let zxRound := add(zx, half)
                        if lt(zxRound, zx) { revert(0,0) }
                        z := div(zxRound, RAY)
                    }
                }
            }
        }
    }
}
