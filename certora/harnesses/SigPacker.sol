// SPDX-License-Identifier: AGPL-3.0-or-later

/// SigPacker.sol -- verification helper. Builds the 65-byte signature exactly as
/// SavingsDai.permit(owner, spender, value, deadline, v, r, s) does (abi.encodePacked(r, s, v)),
/// so a spec can hand the bytes form of permit a Solidity-built signature instead of a
/// CVL-built `bytes` value. Pure; not part of the deployed system.

pragma solidity ^0.8.13;

contract SigPacker {
    function pack(uint8 v, bytes32 r, bytes32 s) external pure returns (bytes memory) {
        return abi.encodePacked(r, s, v);
    }
}
