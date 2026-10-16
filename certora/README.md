# AutoProver rules for SavingsDai

These Certora Prover artifacts were generated for `src/SavingsDai.sol`.

## Source inputs

- Design: `docs/savings-dai-design.md`
- Threat model: None

## Generated files

- `certora/specs/autospec_EIP-2612_Permit.spec`
- `certora/specs/autospec_ERC-20_Share_Token.spec`
- `certora/specs/autospec_ERC-4626_Vault.spec`
- `certora/specs/autospec_Referral_System.spec`
- `certora/specs/invariants.spec`
- `certora/specs/summaries/custom_summaries.spec`
- `certora/specs/summaries/SavingsDai_base_summaries.spec`
- `certora/specs/summaries/SavingsDai_call_resolution.spec`
- `certora/specs/summaries/SavingsDai_summaries.spec`
- `certora/confs/autospec_EIP-2612_Permit.conf`
- `certora/confs/autospec_ERC-20_Share_Token.conf`
- `certora/confs/autospec_ERC-4626_Vault.conf`
- `certora/confs/autospec_Referral_System.conf`
- `certora/mocks/DummyERC20Impl.sol`

## Run the rules

How to run Certora Prover:

1. Install the Certora Prover CLI and export your API key:

```bash
pip install certora-cli
export CERTORAKEY=<your-certora-api-key>
```

2. From the repository root, run the generated configs:

```bash
certoraRun certora/confs/autospec_EIP-2612_Permit.conf
certoraRun certora/confs/autospec_ERC-20_Share_Token.conf
certoraRun certora/confs/autospec_ERC-4626_Vault.conf
certoraRun certora/confs/autospec_Referral_System.conf
```

The generated configs expect these Solidity compilers on your PATH: `solc-0.8.17` (installable with `solc-select`).

Note: `certoraRun` uploads the repository to Certora's cloud for verification.

Full setup and usage documentation: https://docs.certora.com/en/latest/
