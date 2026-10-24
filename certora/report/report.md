# Savings DAI (sDAI): formal verification report (pass 4)

**Target:** `src/SavingsDai.sol:SavingsDai` from [makerdao/sdai](https://github.com/makerdao/sdai), compiled with solc 0.8.17.

**Prover:** Certora certora-cli 8.20.0, run with `rule_sanity: basic` on every run.

**Scene:** faithful 0.8 ports of the mainnet MakerDAO dss contracts (Pot, Vat, DaiJoin, Dai) under `certora/harnesses/`.

## Result at a glance

| | |
|---|---|
| Properties | 45 (6 invariants, 32 safety properties, 7 attack vectors) |
| Proven | **43** |
| Property rules VERIFIED | 87, plus justification and witness rules |
| Property rules VIOLATED | 2, both **findings** (low / informational) |
| Prover-limitation gaps / timeouts / errors / skipped | 0 / 0 / 0 / 0 |

Every component was reviewed by an independent judge, which accepted it, and each closed with a full run that had no rule filter. In pass 4, `scene.spec` changed (deterministic ERC-1271 model), so every conf that imports it was re-run; the links below are those runs.

| Component | Final full run |
|---|---|
| Structural invariants | https://prover.certora.com/orgs/certora/jobs/32094aa6-2ac4-4400-a415-4d31cf9aa9b3/report |
| ERC20 token | https://prover.certora.com/orgs/certora/jobs/958bf48b-3538-4035-8b0c-84aa86254e9f/report |
| ERC4626 vault | https://prover.certora.com/orgs/certora/jobs/ec591a60-33da-4080-a457-b98759d0e908/report |
| Permit | https://prover.certora.com/orgs/certora/jobs/ea39b316-5410-46c1-97ad-52c869560d91/report |
| Maker integration & liveness | https://prover.certora.com/orgs/certora/jobs/f453c3ce-64dc-4550-af5a-30149a0728fe/report (precondition minimality check: 355dfa44) |
| Maker models: Pot | https://prover.certora.com/orgs/certora/jobs/468e84d5-0925-4f4f-a638-c0001ca6e5e8/report |
| Maker models: Dai | https://prover.certora.com/orgs/certora/jobs/b722fc7e-703d-4dda-98f5-50c1500e23ef/report |
| Maker models: SavingsDai constructor | https://prover.certora.com/orgs/certora/jobs/b472def2-b105-4d09-b8f3-56f4e044bb89/report (non-triviality probe: 0cbfecac) |
| ERC4626 rpow probe (real `_rpow`) | https://prover.certora.com/orgs/certora/jobs/900b3830-8881-4fca-8499-cab51af8aadf/report |
| Maker models: third-party setup | https://prover.certora.com/orgs/certora/jobs/aee23f05-e783-4935-a7da-8b1fbbc1dac5/report |
| Setup sanity | https://prover.certora.com/orgs/certora/jobs/9c8e7f1b-2bd9-4a4a-8df7-2d3840e2cee8/report |

## Findings

### F-1: sDAI exits depend on `Pot.drip()` succeeding (low / informational, governance-triggered)

Rule `redeemDoesNotDependOnDrip` is VIOLATED.

**Mechanism**
- Every sDAI deposit, mint, withdraw and redeem calls `pot.drip()` when `now > rho`.
- dss `Pot.file` puts no lower bound on `dsr`.
- If `dsr < RAY`, `drip()` computes a lower chi, and the checked `tmp - chi` underflows. **Every sDAI operation then reverts.**

**Why it can't be fixed by setting the rate back**
- `file` needs `rho == now`, which only a successful `drip` can set.
- The only exit is `Pot.cage()`, which permanently shuts the Pot down.

**Asymmetry with direct Pot users**
- `Pot.exit` has no `rho` check, so direct Pot depositors can still leave.
- sDAI holders are frozen.

**Severity:** requires a negative savings rate set by governance, so informational.

### F-2: `withdraw`/`redeem` accept `receiver = address(0)` and burn the DAI (low, user-error footgun)

Rule `exitRejectsZeroReceiver` is VIOLATED.

**Mechanism**
- `deposit` and `mint` reject a zero or self receiver, but `_burn` does not check the receiver.
- `DaiJoin.exit(address(0), assets)` then calls mainnet `Dai.mint(address(0), assets)`, which accepts it.
- The owner's shares are burned, and the withdrawn DAI is minted to `address(0)`, so it is lost.

**Evidence:** the witness `exitToZeroReceiverWitness` shows `withdraw(12, address(0), owner)` succeeding. Its numbers are illustrative; the path is reachable for any chi.

**Severity:**
- Only the owner or an approved spender can trigger it, and the loss falls on that owner, so it is not a theft vector.
- ERC-4626 doesn't require the check.
- A second sink exists outside this property's scope: setting the receiver to the SavingsDai contract itself also strands the DAI.

## Verified claims (audit view)

1. **Share accounting integrity.**
   - `totalSupply` equals the sum of balances.
   - The zero address and sDAI hold no shares.
   - `pot.pie(sDAI) >= totalSupply`.
2. **ERC20 transfer correctness.**
   - Exact transfers and conserved supply.
   - Revert conditions are exact.
3. **Allowance and authorization.**
   - Allowance updates are exact, and only authorised actions change allowances.
   - Balances fall only through the owner or a spender with sufficient allowance.
4. **Isolation between holders.**
   - No method touches an uninvolved account.
   - Supply changes only through the vault operations.
5. **Vault accounting.**
   - Pricing is exact, with vault-favouring rounding at the post-drip chi.
   - Shares, pie and DAI move by exactly the right amounts.
   - deposit and mint validate the receiver; withdraw and redeem do not (F-2).
   - **New:** rounding costs the user less than one share's worth (deposit, withdraw) or less than 1 wei of DAI (mint, redeem), at the operation's chi.
   - The referral overloads `deposit(…, uint16)` and `mint(…, uint16)` are proven identical to the plain ones (same reverts, return values and whole end state).
6. **ERC4626 view consistency.**
   - Each preview equals its operation, including before drip.
   - Rounding favours the vault, and the `max*` functions are consistent.
   - `convertTo*`, every `preview*` and every operation are monotonic in their amount.
7. **Economic attack resistance.**
   - No round-trip profit.
   - Splitting a deposit, mint, withdraw or redeem into two never gains anything.
   - No action lowers the share price.
   - **New:** the share price never falls over time (dsr >= RAY), checked through the real `_rpow`. Machine-checked end to end only for t - rho < 16 s; for longer gaps it rests on machine-checked rounding lemmas plus a judge-checked written induction. rpow cannot overflow before an accrued factor of about 1.2e23 (about 380 years at 15% APY).
   - Rounding never drains sDAI's own Vat balance.
8. **Permit.**
   - Expired permits and a zero owner are rejected.
   - Exactly one allowance and one nonce (+1) change; the nonce wrap is proven with no assumption.
   - **Upgraded:** `permit(v,r,s)` and `permit(bytes)` are equivalent with no assumption, on both the ECDSA and the ERC-1271 (contract-wallet) path.
9. **Maker integration and liveness.**
   - **New:** sDAI's constructor provably wires it to the Maker system: the immutables plus the Vat `hope`s and the max DAI allowance to DaiJoin. This holds under two deployment assumptions:
     - A1: the `_daiJoin` argument is the real DaiJoin.
     - A2: DaiJoin's `vat` and `dai` are the real Vat and Dai.
   - No SavingsDai method undoes that setup.
   - **New:** no third party can undo it either, through any Vat, Dai, Pot or DaiJoin entry point. This assumes K: no one can produce an ECDSA signature for the sDAI contract's address (otherwise `Dai.permit` could zero the allowance; a witness rule shows this).
   - In a live, correctly configured Maker system:
     - owners can always redeem their full balance and withdraw up to `maxWithdraw`;
     - depositors can always deposit.
   - Each liveness precondition was checked to be necessary: dropping any one makes the rule fail.
10. **Maker model invariants (new).** Proven from the Maker contracts' own constructors over all their methods:
    - Pot `chi >= RAY`
    - Pot `Pie == Σ pie`
    - Dai `totalSupply == Σ balanceOf`
    - **New:** Dai `balanceOf(a) + balanceOf(b) <= totalSupply` for distinct a, b

## Pass history

- **Pass 1** (makerdao test mocks for DaiJoin/Dai):
  - 27 of 28 properties proven, no findings.
  - One prover-limitation gap on permit equivalence.
- **Pass 2:**
  - **Scene audit against dss master:** DaiJoin and Dai mocks diverged from mainnet, so they were replaced with faithful ports and everything was re-proven.
  - **Assumptions:** the DAI-balance assumptions became unnecessary and were removed.
  - **Permit:** the gap was closed with `SigPacker`.
  - **New:** the maker-integration liveness batch, which produced finding F-1.
- **Pass 3:**
  - **New ERC4626 properties:** referral equivalence, monotonicity, split-operation resistance, and the exit receiver check, which produced finding F-2.
  - **New maker-models component:** it turned the previously argued base cases into proofs. These now back `requirePotChiAtLeastRay`, `pre_chiAtLeastRay`, `pre_PieCoversSdaiPie`, the `daiSupplyIsSumPreserved` base case, and the hope/allowance setup preconditions.
- **Pass 4:**
  - **ERC4626:** rounding-loss bounds, and a probe of the real `_rpow` for share-price monotonicity over time.
  - **Maker models:** the two remaining argued claims (third parties can't revoke the setup; pairwise DAI bound) are now proven, so the liveness preconditions `pre_daiSupplyCoversHolders`, `pre_hope*` and `pre_daiJoinAllowance` are discharged (modulo A1, A2, K).
  - **Permit / scene:** `isValidSignature` is now a deterministic function of (signer, digest) instead of NONDET. This closes the ERC-1271 equivalence gap; every scene-dependent conf was re-run, with no change in outcome.
  - No new findings.
- **Autosetup** was not re-run in passes 2, 3 and 4. With certora-cli 8.20.0 its cloud stages cannot succeed, for two reasons:
  - its job-URL regex (`utils/job_utils.py`) expects `/output/` links;
  - `cloud_runner.py:715` maps exit code 0 to −1.

  Links and sanity were set up by hand and re-proven each pass.

## Assumptions that limit confidence

**Scene.**
- Ports of dss Pot, Vat (only the DAI ledger: `frob` cannot be instrumented), DaiJoin and Dai.
- Parametric rules range over SavingsDai methods. The Maker-model invariants range over Pot or Dai methods.

**Summaries.**
- `_rpow` is one deterministic uninterpreted function that never reverts.
  - The liveness rules therefore don't cover rpow-overflow reverts, which are unrealistic on mainnet parameters.
  - Cross-block share-price monotonicity isn't claimed.
- `isValidSignature` (pass 4) is a deterministic uninterpreted function of (signer, digest), returning a bytes4.
  - It ignores the signature bytes and the signer's state within one rule. No rule calls permit twice on the same (owner, digest) with different bytes or changed signer state, so nothing is over-constrained.
  - Callee reverts and malformed returns are not produced, but each has the same effect as a non-magic answer, which is produced. Gas-dependent signers are not modelled.
  - Unlike the pass-2 attempt, no `bytes` value enters CVL, and the invariants re-verify.
- In SavingsDai-verified runs, the constructor's unresolved calls are NONDET. The constructor itself is checked separately, under A1/A2.

**Bare `require`s.**
- `Pot.chi >= RAY`: now backed by the proven `potChiAtLeastRay`.
- Two balances bounded by `totalSupply` (ERC20 success rules): arithmetic from the proven sum invariant.
- `ab == a + b` (split rules): names the combined amount and drops no case where both operations succeed.
- `forall d. ecrecover(d,v,r,s) == owner` (ECDSA-path equivalence rule) and its negation (ERC-1271-path rules): constrain only the ecrecover ghost. The headline equivalence rule `permitSignatureFormsEquivalentAnyPath` has no assumption.
- K: `forall h,v,r,s. ecrecover(h,v,r,s) != sDAI` (third-party setup rule): a computational assumption, of the same kind as keccak collision resistance.
- `msg.sender != sDAI` (third-party setup rule): sDAI's own calls are covered by `setupApprovalsPreserved`.
- `t - rho < 16` (rpow probe): the coverage bound of the machine-checked part.

**Liveness preconditions.** These are part of the property statements. Each is either proven by maker-models or a stated fact about a live mainnet deployment.

**Still argued, not machine-checked.**
- Share-price monotonicity for t - rho >= 16 s: a written induction over the machine-checked `rmulStep*` lemmas, including a lemma that intermediate exponents don't overflow. Checked by the judge, not by the prover.
- The reduced Vat model omits dss functions (frob, fork, grab, ...). By inspection, none of them writes `Vat.can`.
- Combining the constructor proof, `setupApprovalsPreserved` and the third-party rule into one induction over all transactions is a short meta-argument.

## Resolver hooks

None. No rule timed out.

## Artifacts

- Properties: `certora/properties/*.properties.json`
- Specs: `certora/specs/` and `certora/specs/maker-models/`
- Confs: `certora/confs/`
- Judge verdicts: `certora/properties/*.judge-*.md`
- Commentary: `certora/properties/*.commentary.md`
- Machine-readable report: `certora/report/report.json`
