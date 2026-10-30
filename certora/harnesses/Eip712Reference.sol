// SPDX-License-Identifier: AGPL-3.0-or-later
pragma solidity ^0.8.17;

/// Reference implementation of the EIP-712 formulas for sDAI's permit (used only by certora/specs/permit.spec).
/// Written from the EIP-712 / ERC-2612 standards, not from SavingsDai: the spec compares sDAI's behaviour
/// against these values. CVL's keccak256 builtin cannot hash abi.encodePacked data or string literals
/// (docs.certora.com cvl/expr.html "Hashing"), hence this harness.
/// The name/version strings are hashed at runtime (keccak256(bytes(CONST))), like sDAI does, because the
/// Prover models keccak256 as an arbitrary injective function and does not compute real hash values.
contract Eip712Reference {
    string private constant NAME = "Savings Dai";
    string private constant VERSION = "1";

    /// EIP-712 domainSeparator for domain {name: "Savings Dai", version: "1", chainId, verifyingContract}.
    function domainSeparator(uint256 chainId, address verifyingContract) external pure returns (bytes32) {
        return keccak256(abi.encode(
            keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
            keccak256(bytes(NAME)),
            keccak256(bytes(VERSION)),
            chainId,
            verifyingContract
        ));
    }

    /// The current chain id (CVL's env has no chainid field, docs cvl/types.html "The env type").
    function chainId() external view returns (uint256) {
        return block.chainid;
    }

    /// EIP-712 signing digest: keccak256("\x19\x01" ++ domainSeparator ++ hashStruct(message)).
    function digest(bytes32 domainSeparator_, bytes32 structHash) external pure returns (bytes32) {
        return keccak256(abi.encodePacked(hex"1901", domainSeparator_, structHash));
    }
}
