# Savings DAI (sDAI): formal verification report (pass 3)

**Target:** `src/SavingsDai.sol:SavingsDai` from [makerdao/sdai](https://github.com/makerdao/sdai), compiled with solc 0.8.17.

**Prover:** Certora certora-cli 8.20.0, run with `rule_sanity: basic` on every run.

**Scene:** faithful 0.8 ports of the mainnet MakerDAO dss contracts (Pot, Vat, DaiJoin, Dai) under `certora/harnesses/`.

## Result at a glance

| | |
|---|---|
| Properties | 41 (6 invariants, 29 safety properties, 6 attack vectors) |
| Proven | **39** |
| Property rules VERIFIED | 68, plus justification and witness rules |
| Property rules VIOLATED | 2, both **findings** (low / informational) |
| Prover-limitation gaps / timeouts / errors / skipped | 0 / 0 / 0 / 0 |

Every component was reviewed by an independent judge, which accepted it, and each closed with a full run that had no rule filter.

| Component | Final full run |
|---|---|
| Structural invariants | https://prover.certora.com/orgs/certora/jobs/7a094bd0-a0b9-4458-aaaa-d308a0c25dbd/report |
| ERC20 token | https://prover.certora.com/orgs/certora/jobs/d6a18bed-61d6-4e83-9b3b-5812e8dbb8fa/report |
| ERC4626 vault | https://prover.certora.com/orgs/certora/jobs/7da047cb-8def-4946-a501-01b673be33ec/report |
| Permit | https://prover.certora.com/orgs/certora/jobs/ef8a20e2-fa1f-45a5-be68-69418ccd96fb/report |
| Maker integration & liveness | https://prover.certora.com/orgs/certora/jobs/d239cba6-7903-4e49-b2ed-66a9b0b66288/report (precondition minimality check: 355dfa44) |
| Maker models: Pot | https://prover.certora.com/orgs/certora/jobs/9e14d9f8-da5c-472f-9cbf-223ef1ab6e3f/report |
| Maker models: Dai | https://prover.certora.com/orgs/certora/jobs/0e288f36-9e75-43a0-82ce-c6276d96aad8/report |
| Maker models: SavingsDai constructor | https://prover.certora.com/orgs/certora/jobs/e81898a8-1c9f-4100-9232-96be4a73c267/report (non-triviality probe: 0cbfecac) |
| Setup sanity | https://prover.certora.com/orgs/certora/jobs/886f6b15-7488-4d8c-8ee6-4c928718d8b1/report |

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
   - **New:** the referral overloads `deposit(…, uint16)` and `mint(…, uint16)` are proven identical to the plain ones (same reverts, return values and whole end state).
6. **ERC4626 view consistency.**
   - Each preview equals its operation, including before drip.
   - Rounding favours the vault, and the `max*` functions are consistent.
   - **New:** `convertTo*`, every `preview*` and every operation are monotonic in their amount.
7. **Economic attack resistance.**
   - No round-trip profit.
   - **New:** splitting a deposit, mint, withdraw or redeem into two never gains anything.
   - No action lowers the share price.
   - Rounding never drains sDAI's own Vat balance.
8. **Permit.**
   - Expired permits and a zero owner are rejected.
   - Exactly one allowance and one nonce (+1) change; the nonce wrap is proven with no assumption.
   - `permit(v,r,s)` and `permit(bytes)` are equivalent on the ECDSA path.
9. **Maker integration and liveness.**
   - **New:** sDAI's constructor provably wires it to the Maker system: the immutables plus the Vat `hope`s and the max DAI allowance to DaiJoin. This holds under two deployment assumptions:
     - A1: the `_daiJoin` argument is the real DaiJoin.
     - A2: DaiJoin's `vat` and `dai` are the real Vat and Dai.
   - No SavingsDai method undoes that setup.
   - In a live, correctly configured Maker system:
     - owners can always redeem their full balance and withdraw up to `maxWithdraw`;
     - depositors can always deposit.
   - Each liveness precondition was checked to be necessary: dropping any one makes the rule fail.
10. **Maker model invariants (new).** Proven from the Maker contracts' own constructors over all their methods:
    - Pot `chi >= RAY`
    - Pot `Pie == Σ pie`
    - Dai `totalSupply == Σ balanceOf`

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
- **Autosetup** was not re-run in passes 2 and 3. With certora-cli 8.20.0 its cloud stages cannot succeed, for two reasons:
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
- `isValidSignature` is NONDET. Permit equivalence on the ERC-1271 path therefore holds only as "same effects when both succeed". A deterministic summary was tried and rejected, because it made the prover report impossible storage changes.
- In SavingsDai-verified runs, the constructor's unresolved calls are NONDET. The constructor itself is checked separately, under A1/A2.

**Bare `require`s.**
- `Pot.chi >= RAY`: now backed by the proven `potChiAtLeastRay`.
- Two balances bounded by `totalSupply` (ERC20 success rules): arithmetic from the proven sum invariant.
- `ab == a + b` (split rules): names the combined amount and drops no case where both operations succeed.
- `forall d. ecrecover(d,v,r,s) == owner` (permit equivalence): constrains only the ecrecover ghost.

**Liveness preconditions.** These are part of the property statements. Each is either proven by maker-models or a stated fact about a live mainnet deployment.

**Still argued, not machine-checked.**
- Third parties can't revoke sDAI's Vat `hope`s or its DAI allowance by calling Vat or Dai directly. The only conceivable route, `Dai.permit` with holder = sDAI, would need a signature for a contract address.
- The pairwise DAI balance bound for a non-sDAI caller follows arithmetically from `daiSupplyIsSum`, but no rule checks it.

## Resolver hooks

None. No rule timed out.

## Artifacts

- Properties: `certora/properties/*.properties.json`
- Specs: `certora/specs/` and `certora/specs/maker-models/`
- Confs: `certora/confs/`
- Judge verdicts: `certora/properties/*.judge-*.md`
- Commentary: `certora/properties/*.commentary.md`
- Machine-readable report: `certora/report/report.json`
