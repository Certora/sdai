# Formal verification report: Savings Dai (sDAI)

- **Target:** `src/SavingsDai.sol:SavingsDai`, from makerdao/sdai at commit `2b7acb9`.
- **Tools:** Certora Prover with certora-cli 8.20.3; the setup was built by AutoProver at commit `3fbe960`.
- **Date:** 2026-10-30.

## Summary

| | Count |
|---|---|
| Properties formulated | 33 (6 invariants, 8 ERC-20, 14 ERC-4626, 5 permit) |
| Properties fully verified | 32 |
| Properties with a finding | 1 (`max_functions_accurate`) |
| Rules marked expected-to-fail (genuine issue) | 2 |
| Rules marked expected-to-fail (prover limitation) | 0 |
| Properties skipped | 0 |
| Timeouts / errors | 0 |

Rule-mapping outcomes are 61 GOOD and 2 BAD. A rule that backs several properties is counted once for each property.

Every spec was reviewed by an adversarial judge separate from the agent that wrote it, and every spec was finally accepted:
- Invariants: accepted in round 2.
- ERC-20, ERC-4626 and permit: each rejected in round 1, then accepted in round 2.

Every final run is full and unfiltered, with `rule_sanity: basic`.

## Findings

### F-1 (low): `maxDeposit` and `maxMint` overstate what `deposit` and `mint` accept (ERC-4626 non-compliance)

- **What happens:**
  - `maxDeposit(address)` and `maxMint(address)` both return `type(uint256).max`.
  - `deposit` computes `assets * RAY` with checked arithmetic, so it reverts for any `assets` above `max_uint256 / 1e27`.
  - `mint` computes `shares * chi` with chi ≥ RAY, so it reverts for any `shares` above about `max_uint256 / chi`.
- **Proof that it happens in every state:**
  - `maxDepositAlwaysReverts` has no preconditions and is VERIFIED: `deposit(maxDeposit(r), r)` reverts in every state.
  - `maxMintAlwaysReverts` assumes only the proven invariant `chiAtLeastRay` and is VERIFIED: `mint(maxMint(r), r)` reverts in every state.
- **Counterexample (rules `maxDepositAccepted` / `maxMintAccepted`, VIOLATED):** the caller holds and has approved unlimited DAI, and the Pot was dripped in this block. The call reverts at the multiplication right after chi is read.
- **Impact:** ERC-4626 says maxDeposit/maxMint "MUST NOT be higher than the actual maximum that would be accepted". An integrator or aggregator that uses these values as caps, for example to deposit "the maximum", gets a revert. No funds are at risk and no accounting is affected.

## Results by audit claim

All rules below are VERIFIED unless marked. The run links are listed under "Runs".

1. **Share accounting is exact and fully backed.** totalSupply equals the sum of balances, and the Pot's `pie[sDAI]` equals totalSupply exactly. Each of these holds across every method of sDAI, Pot, Vat, DaiJoin and Dai:
   - `total_supply_equals_sum_of_balances`
   - `shares_equal_pot_pie`
   - `pot_total_pie_covers_sdai_pie`
2. **The Maker-side solvency that sDAI relies on holds.** The Pot's Vat dai covers chi·Pie, DaiJoin's Vat dai covers RAY·DAI supply, and sDAI's constructor-time Vat permissions and DAI approval persist forever:
   - `pot_vat_dai_covers_savings`
   - `daijoin_vat_dai_covers_dai_supply`
   - `sdai_setup_permissions_persist`
3. **ERC-20 transfers move exactly what they say.** Each transfer has exact effects. Each revert rule states exactly when the call reverts (an iff), so a holder can always transfer up to their balance. ERC-20 operations never touch vault backing:
   - `transfer_moves_exact_amount`
   - `transfer_from_moves_exact_amount_and_spends_allowance`
   - `transfer_revert_conditions`
   - `transfer_from_revert_conditions`
   - `erc20_ops_preserve_vault_backing`
4. **Only owners and approved spenders move or approve shares.**
   - Over all 40 sDAI methods, a balance falls only when the owner acts, or when a spender acts and its allowance falls by exactly that amount (this covers withdraw/redeem burns).
   - An allowance changes only through the owner's approve, increaseAllowance or decreaseAllowance; through a permit for exactly that pair; or through spending inside transferFrom, withdraw or redeem.
   - Properties:
     - `balance_decrease_requires_owner_or_allowance`
     - `allowance_increase_requires_owner_authorization`
     - `allowance_management_functions_correct`
5. **Deposit, mint, withdraw and redeem have exact effects.** Each action's amounts match floor/ceil formulas computed independently at the post-drip chi. No account other than the caller loses DAI:
   - `deposit_effects_exact`
   - `mint_effects_exact`
   - `withdraw_effects_exact`
   - `redeem_effects_exact`
   - `deposit_pulls_only_from_caller`
6. **Rounding never leaks value from the vault.** sDAI's internal Vat dai never decreases under any method. Deposit→redeem and mint→withdraw in the same block are never profitable:
   - `rounding_favors_vault`
   - `round_trip_no_profit`
7. **Pricing is current, consistent and resistant to manipulation.**
   - Previews equal the actions exactly, for any time elapsed since the last drip.
   - Actions drip to the current block, and the new chi equals rpow(dsr, Δt)·chi/RAY.
   - Third parties' DAI value is unchanged by other users' actions in the same block.
   - Donations of DAI or Vat dai do not move the price.
   - Chi never decreases when dsr ≥ RAY.
   - Properties:
     - `preview_matches_action`
     - `actions_price_at_accrued_rate`
     - `third_party_value_unaffected`
     - `share_price_independent_of_donations`
     - `share_price_never_decreases`
8. **Holders can always exit; the max functions are mostly accurate.**
   - `redeem_always_possible`: a holder can always redeem up to their balance, including after Pot cage.
   - `max_functions_accurate`: redeeming maxRedeem and withdrawing maxWithdraw always succeed. **Except** maxDeposit and maxMint, which is finding F-1 (`maxDepositAccepted` and `maxMintAccepted` are BAD, expected).
9. **Permit is signature-gated, replay-safe and bound to the chain.**
   - A successful permit sets exactly one allowance and advances exactly that owner's nonce, by 1 mod 2^256.
   - It requires either ecrecover of the independently computed EIP-712 digest to equal the owner, or the owner's EIP-1271 wallet to return the magic value on that exact digest and those exact signature bytes.
   - Expired permits and the zero owner are rejected.
   - Only permit changes nonces.
   - DOMAIN_SEPARATOR equals the EIP-712 separator for the current chain and differs from the cached value on any other chain.
   - Properties:
     - `permit_effects_exact`
     - `permit_rejects_expired_and_zero_owner`
     - `permit_requires_owner_signature`
     - `nonces_change_only_by_permit`
     - `domain_separator_bound_to_chain`

The per-property mapping to rules, statuses and links is in `report.json`.

## Coverage and confidence notes

**Modelling choices** (all are recorded with their soundness arguments in the commentary files):
- **Scene.**
  - sDAI is verified against the repo's copies of the dss Vat, DaiJoin and Dai, which match the dss contracts.
  - The repo's `PotMock` lacks `drip()`, so `certora/harnesses/PotHarness.sol` adds mainnet Pot's `drip()` to it. The mock-only `setYield` is excluded from one invariant, `potVatDaiCoversSavings`.
- **Links.** autosetup left the Vat/Dai immutables of DaiJoin and Pot unlinked, and dispatched `sDAI.dai` to three candidates. Those calls would have been havocs, so the links were completed by hand. The original block is kept in `certora/logs/`.
- **`_rpow` summary.** Both exponentiation loops, sDAI's and the Pot's, are replaced by one uninterpreted function.
  - It is constrained only by true facts: n=0 gives RAY, n=1 gives x, and x≥RAY gives a result ≥ RAY.
  - Without it, `loop_iter=3` would only have covered fewer than 16 seconds since the last drip.
  - **Cost:** the real rpow's overflow reverts are dropped. So "must not revert" rules state "rate accumulation does not overflow" as an explicit assumption.
- **Static-only summaries.** autosetup ran with `--skip-llm`, so it generated static summaries only. In practice none were needed: the base summaries file is empty.

**Trust assumptions:**
- **Bare `require`s:**
  - Maker governance (wards of Vat, Pot and Dai) is trusted. The solvency invariants assume the top-level caller is not a ward.
  - sDAI, Pot and DaiJoin never originate transactions themselves.
  - At sDAI's deployment, the existing Maker state satisfies the Maker invariants, chi ≥ RAY, and `pie[sDAI] = 0`.
  - The constructor arguments are the scene's DaiJoin and Pot, the same assumption the links make.
- **Liveness rules** (redeem/withdraw) additionally assume:
  - `msg.value == 0`, and a valid receiver.
  - The Pot is a Vat ward and DaiJoin is a Dai ward.
  - dsr ≥ RAY. This is a governance assumption; cage sets dsr = RAY, so caged Pots are covered.
  - Rate accumulation and the Vat sums do not overflow.
- **Signatures:**
  - ECDSA is unforgeable for contract addresses. This is used in the Dai-permit preserved blocks.
  - CVL hashing of signatures covers up to 1024 bytes (`hashing_length_bound`). sDAI's logic depends on the signature length only through `== 65`.

**Property classes:** all classes in `property-classes.md` were asked for every component. The full record is in `certora/properties/property-classes.record.md`. These classes produced no property for any component:
- **Fees and splits:** sDAI has no fees. The referral code only emits an event.
- **Re-entrancy:** sDAI hands control only to trusted Maker core contracts, which are in the scene, and to an EIP-1271 wallet via `staticcall`, which cannot write state.

**Prover limitations, timeouts, skips:** none.

**Timeout Resolver:** not used.

## Edits outside `certora/`

- **sDAI sources:** none. No ERC-7201 annotations were needed (`source_edits.json` is empty).
- **`.gitignore`:** autosetup appended `**/.certora_internal` and `**/.CertoraProverLiteReports`.
- **`.gitattributes`:** autosetup created it with three linguist lines for `*.spec` and `*.conf`.

## Runs

| Spec | Final run | Result |
|---|---|---|
| invariants (11 invariants, all scene methods) | [1080ee77](https://app.certora.com/orgs/certora/jobs/1080ee77-78e7-4afb-bb57-8a5da4e46a62/report) | all VERIFIED |
| erc20-token | [31e29977](https://app.certora.com/orgs/certora/jobs/31e29977-c51f-44e2-a565-e7348b6bff78/report) | all VERIFIED |
| erc4626-vault | [59ab9ca6](https://app.certora.com/orgs/certora/jobs/59ab9ca6-d468-4b07-8b67-604dcf1ed984/report) | all VERIFIED except 2 expected (F-1) |
| permit | [2affbb9b](https://app.certora.com/orgs/certora/jobs/2affbb9b-31e4-4932-ad68-c8f612984a40/report) | all VERIFIED |
| setup sanity (40 methods, links completed) | [2f6f6595](https://app.certora.com/orgs/certora/jobs/2f6f6595-e837-45a6-8f93-096a5993bbfa/report) | all reachable |
