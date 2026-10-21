# Savings DAI (sDAI): formal verification report

**Target:** `src/SavingsDai.sol:SavingsDai` from [makerdao/sdai](https://github.com/makerdao/sdai), cloned 2026-10-21 and compiled with solc 0.8.17. The prover is Certora certora-cli 8.20.0, run with `rule_sanity: basic` on every run.

## Result at a glance

| | |
|---|---|
| Properties formulated | 28 (3 invariants, 21 safety properties, 4 attack vectors) |
| Properties proven | **27 fully**, plus 1 proven through replacement rules with a documented gap |
| Rules VERIFIED | 40 property rules + 2 justification rules |
| Rules VIOLATED | 1, expected-to-fail because of a **prover limitation** (not a bug) |
| Timeouts / errors | 0 |
| Skipped properties | 0 |
| **Suspected bugs (findings)** | **None** |

Every component converged after 1–2 generate→judge rounds. Each one was reviewed by an independent judge, which accepted it, and each closed with a full run that had no rule filter.

| Component | Final full run |
|---|---|
| Structural invariants | https://prover.certora.com/orgs/certora/jobs/b91ff71e-7cb3-4cc9-85b5-b30457145a95/report |
| ERC20 token | https://prover.certora.com/orgs/certora/jobs/6aa78c3d-b8e4-468c-8fbc-7efdf0ec5bbd/report |
| ERC4626 vault | https://prover.certora.com/orgs/certora/jobs/b4c84dec-6030-4573-b299-c9a1eadae623/report |
| Permit | https://prover.certora.com/orgs/certora/jobs/53186bb4-9791-40ae-a464-965924ea4e01/report |
| Setup sanity (linked scene) | https://prover.certora.com/orgs/certora/jobs/d5cc3f4a-60d8-4f1f-bae2-f2cab5e629a9/report |

## Verified claims (audit view)

1. **Share accounting integrity.** These hold in every reachable state:
   - `totalSupply` equals the sum of all balances.
   - The zero address and sDAI itself never hold shares.
   - sDAI's normalized Pot balance is always at least `totalSupply` (`pot.pie(sDAI) >= totalSupply`), so every share is backed by DSR pie. *(Rules: totalSupplyIsSumOfBalances, zeroAndSelfHoldNoShares, sharesBackedByPie.)*
2. **ERC20 transfer correctness.** `transfer` and `transferFrom` move exactly `value`, conserve supply, return true, and spend finite allowances exactly. They revert if and only if:
   - the recipient is the zero address or sDAI,
   - the balance is insufficient, or
   - the allowance is insufficient.
3. **Allowance and authorization:**
   - approve, increaseAllowance and decreaseAllowance set exact values.
   - An allowance increases only through the owner's own call or a permit.
   - An account's share balance can only fall through the owner's own action or a spender with enough allowance. This covers withdraw and redeem.
4. **Isolation between holders:**
   - No method changes the share balance of an account that is not a named party (from, to, receiver or owner).
   - `totalSupply` changes only through deposit, mint, withdraw and redeem.
5. **Vault accounting:**
   - `deposit` returns ⌊assets·RAY/chi⌋ and `mint` charges ⌈shares·chi/RAY⌉.
   - `withdraw` burns ⌈assets·RAY/chi⌉ and `redeem` pays ⌊shares·chi/RAY⌋.
   - chi is the Pot's accumulator after the drip.
   - Each of these moves exactly that many shares and that much pie and DAI.
   - `deposit` and `mint` reject a zero or self receiver.
6. **ERC4626 view consistency:**
   - Every `preview*` equals the corresponding operation in the same block, including when the Pot has not been dripped.
   - `previewMint` and `previewWithdraw` round in the vault's favour.
   - The `max*` functions are consistent: redeeming or withdrawing above the max reverts.
7. **Economic attack resistance:**
   - Within one block, a deposit→redeem or mint→withdraw round trip never yields a profit.
   - No sDAI method can lower Pot `chi`, so it cannot lower the share price either.
8. **Permit:**
   - It reverts on an expired deadline or a zero owner.
   - On success it sets exactly `allowance[owner][spender]` and adds exactly +1 to `nonces[owner]`. No other allowance, nonce, balance or supply changes.
   - Nonces change only through permit.
   - The v/r/s form decodes back to the same (v, r, s) and has the same effects as the bytes form (see the coverage gap below).

## Suspected bugs (findings)

**None.** No rule failed because of contract behaviour.

## Coverage gaps (prover limitations, not bugs)

- **`permitSignatureFormsEquivalent`** is VIOLATED and marked expected-to-fail because of a prover limitation. The rule pins the 65 bytes of `abi.encodePacked(r, s, v)` one at a time in a CVL `bytes` value. The prover models that value as a map from offset to word, and that map is not kept consistent across overlapping offsets. As a result the contract's `mload` at offset 0x20 can read an `s` that differs from the pinned bytes (counterexample in run 53186bb4). The judge checked the counterexample and confirmed this; the byte layout and decoding in the spec are correct. Sound coverage of the property comes from two other rules:
  - `permitVrsDecodesPackedSignature` (VERIFIED) shows the pack→decode round trip returns exactly (v, r, s).
  - `permitSignatureFormsSameEffects` (VERIFIED) shows the two forms have the same revert behaviour and the same effects.

  **Still unproven:** that externally supplied `bytes` signatures and the ERC-1271 path behave identically across the two entry points.
- **`noncesNeverDecrease`** excludes the single state `nonce == max_uint256`, where the unchecked `++` wraps to 0. Reaching it takes 2²⁵⁶−1 permits. `nonceChangesOnlyViaPermit` proves with no assumptions that every change is exactly +1 mod 2²⁵⁶.

## Assumptions that limit confidence

**Scene models (external MakerDAO components):**
- **Pot:** `certora/harnesses/Pot.sol` is a port of dss `pot.sol` to 0.8. The repo's `PotMock` lacks `drip()`, which sDAI calls.
- **Vat:** `certora/harnesses/Vat.sol` is `VatMock` reduced to `hope`/`move`/`suck`/`heal`. `VatMock.frob` fails the prover's instrumentation with "stack too deep".
- **DaiJoin and Dai:** `DaiJoinMock` and `DaiMock` from `src/test/mocks`.
- The properties rely on these models behaving like mainnet Maker. The models' own methods are outside the parametric scope.

**Summaries** (`certora/specs/scene.spec`):
- `_rpow`, in both SavingsDai and Pot, is replaced by one deterministic uninterpreted function. The real `_rpow` reverts on overflow and the summary never reverts. Results hold for every elapsed time `now − rho`, but overflow-driven reverts of conversions are not modelled.
- `isValidSignature` (ERC-1271) is NONDET. This is sound because the call is a staticcall.
- Unresolved `hope`/`approve`/`vat`/`dai` calls are NONDET. Only SavingsDai's constructor makes such calls, while its dependencies are still arbitrary addresses. This drops the constructor's writes to `Vat.can` and `Dai.allowance`, which no property reads.

**Bare `require`s,** each justified:
- **Two balances bounded by `totalSupply`** (ERC20 success rules). This is arithmetic from the proven sum invariant.
- **`Pot.chi >= RAY`** (two vault rules). It is supported by the VERIFIED justification rule `potChiNeverDecreases` and by Pot's constructor setting `chi = RAY`. That constructor step is argued, not proven.
- **DAI `totalSupply == sum of balances`** (withdraw and redeem accounting). It is supported by the VERIFIED justification rule `daiSupplyIsSumPreserved` over every DaiMock entry point. Its base case is argued, not proven.
- **`nonce < max_uint256`** (see above).

**Other limits:**
- **Static-only autosetup summaries.** Autosetup ran with `--skip-llm`, so its summaries are static only. It produced no summaries for this contract and no call-resolution links. Its own warmup also failed: the cloud runner misread `wait_for_results: none` submissions. To compensate, the links were added by hand to `certora/confs/base.conf`, and setup sanity was re-proven with them.
- **Same-block share price.** `share_price_never_decreases` compares values within one block, because interest accrual legitimately changes the price across blocks.
- **Parametric scope.** `parametric_contracts` is SavingsDai only.

## Resolver hooks

None. No rule timed out.

## Artifacts

- Properties: `certora/properties/*.properties.json`
- Specs: `certora/specs/{invariants,erc20-token,erc4626-vault,permit,scene}.spec`
- Confs: `certora/confs/`
- Judge verdicts: `certora/properties/*.judge-round*.md`
- Commentary: `certora/properties/*.commentary.md`
- Machine-readable report: `certora/report/report.json`
