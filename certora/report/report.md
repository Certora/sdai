# Savings DAI (sDAI): formal verification report (pass 2)

**Target:** `src/SavingsDai.sol:SavingsDai` from [makerdao/sdai](https://github.com/makerdao/sdai), compiled with solc 0.8.17.

**Prover:** Certora certora-cli 8.20.0, run with `rule_sanity: basic` on every run.

**Scene:** faithful 0.8 ports of the mainnet MakerDAO dss contracts (Pot, Vat, DaiJoin, Dai) under `certora/harnesses/`.

## Result at a glance

| | |
|---|---|
| Properties | 33 (3 invariants, 25 safety properties, 5 attack vectors) |
| Proven | **32** |
| Rules VERIFIED | 46 property rules + 2 justification rules |
| Rules VIOLATED | 1, a **finding** (governance-triggered, low/informational) |
| Prover-limitation gaps / timeouts / errors / skipped | 0 / 0 / 0 / 0 |

Every component was reviewed by an independent judge, which accepted it, and each closed with a full run that had no rule filter.

| Component | Final full run |
|---|---|
| Structural invariants | https://prover.certora.com/orgs/certora/jobs/7a094bd0-a0b9-4458-aaaa-d308a0c25dbd/report |
| ERC20 token | https://prover.certora.com/orgs/certora/jobs/d6a18bed-61d6-4e83-9b3b-5812e8dbb8fa/report |
| ERC4626 vault | https://prover.certora.com/orgs/certora/jobs/653c426b-33ce-490f-a6db-fff70055c773/report |
| Permit | https://prover.certora.com/orgs/certora/jobs/ef8a20e2-fa1f-45a5-be68-69418ccd96fb/report |
| Maker integration & liveness | https://prover.certora.com/orgs/certora/jobs/d239cba6-7903-4e49-b2ed-66a9b0b66288/report |
| Precondition minimality check | https://prover.certora.com/orgs/certora/jobs/355dfa44-7771-4e21-a854-810363897918/report |
| Setup sanity | https://prover.certora.com/orgs/certora/jobs/886f6b15-7488-4d8c-8ee6-4c928718d8b1/report |

## Finding

### F-1: sDAI exits depend on `Pot.drip()` succeeding (low / informational, governance-triggered)

Rule `redeemDoesNotDependOnDrip` is VIOLATED. It is formulated in the "VERIFIED = good" direction: it assumes every live-system precondition except `dsr >= RAY` and asserts that the owner's redeem does not revert.

**Mechanism**
- Every sDAI deposit, mint, withdraw and redeem calls `pot.drip()` whenever `block.timestamp > pot.rho()`.
- dss `Pot.file("dsr", …)` puts no lower bound on the rate.
- If governance ever sets `dsr < RAY`, the next `drip()` computes a new chi below the old one, and the checked `tmp - chi` underflows.
- **From then on, every sDAI operation reverts.**

**Why it can't be fixed by setting the rate back**
- Governance can't correct `dsr`, because `file` requires `rho == now`, and only a successful `drip` can set that.
- The only recovery is `Pot.cage()`, which resets `dsr` to RAY but permanently shuts the Pot down.

**Asymmetry with direct Pot users**
- Direct Pot depositors are unaffected: `Pot.exit` has no `rho == now` check, so they can leave at the last stored chi.
- sDAI holders are frozen until cage.

**Example counterexample** (run d239cba6): dsr = 0.5·RAY, rho = 4, now = 7, owner holding 1 share. The conclusion holds for the real `_rpow` at every dsr < RAY.

**Severity:** it requires a governance action that Maker would not normally take (a negative savings rate), so it's informational. It is worth documenting for integrators that wrap sDAI.

## Verified claims (audit view)

1. **Share accounting integrity.**
   - `totalSupply` equals the sum of balances.
   - The zero address and sDAI itself hold no shares.
   - `pot.pie(sDAI) >= totalSupply`, so every share is backed by DSR pie.
2. **ERC20 transfer correctness.**
   - Exact amounts move and supply is conserved.
   - transfer and transferFrom return true on success.
   - They revert exactly when the recipient is the zero address or sDAI, or the balance or allowance is insufficient.
3. **Allowance and authorization.**
   - Allowance updates are exact, and only authorised actions change allowances.
   - Balances fall only through the owner or a spender with sufficient allowance; this includes withdraw and redeem.
4. **Isolation between holders.**
   - No method touches an uninvolved account.
   - Supply changes only through the vault operations.
5. **Vault accounting.**
   - Pricing is exact: deposit gives ⌊a·RAY/chi⌋, mint charges ⌈s·chi/RAY⌉, withdraw burns ⌈a·RAY/chi⌉, redeem pays ⌊s·chi/RAY⌋.
   - chi is the value after drip.
   - Shares, pie and DAI move by exactly those amounts.
   - deposit and mint reject an invalid receiver.
6. **ERC4626 view consistency.**
   - Each preview equals its operation, including before drip.
   - Previews round in the vault's favour.
   - The `max*` functions are consistent with the operations.
7. **Economic attack resistance.**
   - A same-block deposit→redeem or mint→withdraw round trip makes no profit.
   - No action lowers the share price.
   - **New in pass 2:** rounding dust never drains sDAI's own Vat balance, across all 40 methods.
8. **Permit.**
   - Expired permits and a zero owner are rejected.
   - Exactly one allowance and one nonce (+1) change.
   - Nonces never decrease except at the unchecked wrap, which is now proven with no assumption.
   - **New in pass 2:** `permit(v,r,s)` and `permit(bytes)` with a Solidity-built signature are proven equivalent, closing the pass-1 coverage gap.
9. **Maker integration and liveness (new in pass 2).**
   - sDAI never revokes its Vat `hope`s or its DAI allowance to DaiJoin.
   - In a live, correctly configured Maker system, an owner can always redeem their full balance and withdraw up to `maxWithdraw`.
   - In the same conditions, a depositor with enough DAI and allowance can always deposit.
   - The live-system preconditions are listed in `properties/maker-integration.commentary.md`. Each was checked to be necessary: dropping any one makes the rule fail (minimality run 355dfa44).

## What changed in pass 2

- **Autosetup diagnosis.** Re-running autosetup can't succeed with certora-cli 8.20.0:
  - Its job-link regex (`utils/job_utils.py`) only recognises the old `/output/` links.
  - `cloud_runner.py:715` maps exit code 0 to −1 (`process.returncode or -1`).

  Its local stages had already worked. The links and the setup sanity check were done by hand and re-proven.
- **Scene audit against dss master.**
  - Pot and Vat already matched.
  - `DaiJoinMock` lacked `live`/`cage`; the real `exit` requires `live == 1`.
  - `DaiMock` is a newer Dai variant that rejects mints and transfers to `address(0)` and uses unchecked math. Mainnet DAI does neither.

  Both are now faithful ports of the dss originals (`harnesses/DaiJoin.sol`, `harnesses/Dai.sol`), and every component was re-proven on the new scene.
- **Assumptions removed.**
  - The DAI supply/balance assumptions in withdraw and redeem accounting are gone, since the real Dai uses checked math.
  - The bare nonce `require` is gone.
  - The permit-equivalence prover-limitation gap is gone. `harnesses/SigPacker.sol` builds the signature in Solidity.
- **Attempt reverted.** A deterministic ghost summary for `isValidSignature` made the prover report impossible storage changes inside `permit(bytes)`, so the NONDET summary was restored (see `specs/scene.spec`).

## Assumptions that limit confidence

**Scene models.**
- The external MakerDAO contracts are 0.8 ports of dss Pot, Vat (only the DAI ledger, since `frob` cannot be instrumented), DaiJoin and Dai.
- `parametric_contracts` is SavingsDai only.

**Summaries.**
- `_rpow` (in both SavingsDai and Pot) is one deterministic uninterpreted function that never reverts.
  - The real `_rpow` reverts on overflow, so the liveness rules do not cover rpow-overflow reverts. These are unrealistic on mainnet parameters.
  - Cross-block share-price monotonicity is not claimed.
- `isValidSignature` is NONDET. The ERC-1271 path of permit equivalence is therefore only covered as "same effects when both succeed". In the real EVM a gas-dependent signer could also answer the two calls differently.
- Unresolved constructor calls (`hope`/`approve`/`vat`/`dai`) are NONDET. As a result, the constructor establishing sDAI's approvals is argued, not proven; that no method ever undoes them is proven.

**Bare `require`s.**
- Two balances bounded by totalSupply (ERC20 success rules): arithmetic from the proven sum invariant.
- `Pot.chi >= RAY` (two vault rules): backed by the verified justification rule `potChiNeverDecreases`; Pot's constructor setting chi = RAY is argued, not proven.
- `forall d. ecrecover(d,v,r,s) == owner` (permit-equivalence rules): constrains only the ecrecover ghost.

**Liveness preconditions.** These are part of the property statements, not trust assumptions. They state that the Maker system is live, solvent, correctly authorised, and free of overflow on mainnet magnitudes.

## Resolver hooks

None. No rule timed out.

## Artifacts

- Properties: `certora/properties/*.properties.json`
- Specs: `certora/specs/{invariants,erc20-token,erc4626-vault,permit,maker-integration,scene}.spec`
- Confs: `certora/confs/`
- Judge verdicts: `certora/properties/*.judge-*.md`
- Commentary: `certora/properties/*.commentary.md`
- Machine-readable report: `certora/report/report.json`
- Status of the pass-2 plan: `certora/NEXT_STEPS.md`
