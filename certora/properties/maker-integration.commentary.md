# maker-integration: commentary (pass 2, round 1)

Spec: `certora/specs/maker-integration.spec`. Conf: `certora/confs/maker-integration.conf` (a copy of
invariants.conf with `verify`/`msg` changed; no extra prover options).

Final full run (unfiltered): https://prover.certora.com/orgs/certora/jobs/d239cba6-7903-4e49-b2ed-66a9b0b66288/report
Precondition-minimality run (temporary drop-one-precondition variants, since removed from the spec):
https://prover.certora.com/orgs/certora/jobs/355dfa44-7771-4e21-a854-810363897918/report. All 59
variants were VIOLATED, so every precondition listed below is needed.

## Rules

| Property | Rule | Result |
|---|---|---|
| setup_approvals_preserved | `setupApprovalsPreserved` (parametric, all SavingsDai methods) | VERIFIED |
| owner_can_always_redeem | `ownerCanRedeemAll`, `ownerCanWithdrawMax` | VERIFIED |
| redeem_does_not_depend_on_drip | `redeemDoesNotDependOnDrip` (probe) | VIOLATED, expected (finding) |
| deposit_liveness | `depositLiveness` | VERIFIED |
| vault_never_pays_rounding_from_own_vat_balance | `vaultNeverPaysRoundingFromOwnVatBalance` (parametric, all SavingsDai methods) | VERIFIED |

## Design decisions

- **Liveness rules** have the form `op@withrevert(...); assert !lastReverted;`. Their preconditions
  are CVL functions named `pre_*`, each with a comment. They are part of the property statement
  ("in a live, correctly configured Maker system the op does not revert"), not trust assumptions.
  Each rule requires only what its own call path needs. For example, redeem needs no `vat.hope(pot)`,
  because Pot.exit moves dai *from* Pot as Pot itself. Deposit needs no `DaiJoin.live`, because
  `DaiJoin.join` does not check it.
- **Drip quantities** are computed in CVL from the pre-state with the scene's `rpowG` ghost:
  `dripFactor` = rpow(dsr, now − rho) (RAY when now ≤ rho), `chiAfterDrip` = dripFactor·chi/RAY, and
  `suckRad` = Pie·(chiAfterDrip − chi). Overflow bounds are written on these exact quantities, so
  each bound matches exactly one checked operation in the Maker contracts.
- **The rpowG ghost knows nothing about rpow.** It cannot know that dsr ≥ RAY ⇒ rpow ≥ RAY, so the
  rules state this property of the real `_rpow` (`pre_rpowMonotone`). The property is vacuous when
  dsr < RAY, so the probe keeps it.
- **Structural invariants.** The redeem/withdraw rules use `requireInvariant totalSupplyIsSumOfBalances`,
  `sharesBackedByPie` and `zeroAndSelfHoldNoShares`. These give owner balance ≤ totalSupply ≤ pie[sDAI],
  which Pot.exit needs, and they bound chi·shares by Pot's dai.
- **setupApprovalsPreserved** asserts, for every SavingsDai method: if `vat.can(sDAI, daiJoin)`
  was 1 before, it is still 1 after; the same holds for `vat.can(sDAI, pot)`; and if
  `Dai.allowance(sDAI, daiJoin)` was max before, it is still max after. The scene NONDETs the
  constructor's `hope`/`approve`, so these facts cannot be an invariant's base case here. The rule
  provides the preservation half instead, and the liveness rules state the values as preconditions.
- **vaultNeverPaysRoundingFromOwnVatBalance** is checked for every SavingsDai method, not only the
  6 vault entry points. It has **no preconditions and no alias exclusions**, and none are needed:
  - sDAI's Vat dai is only touched by these moves: `DaiJoin.join(sDAI)` (+RAY·assets),
    `Pot.join` (−chi·shares), `Pot.exit` (+chi·shares) and `DaiJoin.exit` (−RAY·assets).
  - All of these moves are between fixed contracts (sDAI, Pot, DaiJoin). `receiver` and `owner` only
    affect ERC-20 DAI and sDAI balances, never Vat dai.
  - Drip's `suck` credits `dai[pot]` and debits `sin[vow]`. The rule holds even when `vow == sDAI`
    (the prover tried that alias in the probe CEX), because suck never decreases `dai[vow]`.
  - The rounding directions are floor in deposit/redeem and ceil in mint/withdraw. With them,
    chi·shares ≤ RAY·assets on entry and chi·shares ≥ RAY·assets on exit.

## Liveness precondition list

Common to `ownerCanRedeemAll` and `ownerCanWithdrawMax` (owner = msg.sender; shares = full balance;
assets = shares·chi'/RAY):
1. requireInvariant of the 3 structural invariants.
2. `pre_noEther`: msg.value == 0.
3. `pre_daiJoinLive`: DaiJoin.live == 1 (not caged).
4. `pre_hopeDaiJoin`: vat.can(sDAI, daiJoin) == 1. The constructor sets it and setupApprovalsPreserved shows it is never revoked.
5. `pre_daiJoinMints`: Dai.wards(daiJoin) == 1.
6. `pre_potSucks`: Vat.wards(pot) == 1.
7. `pre_dsrNonNegative`: dsr ≥ RAY. This is the one dropped by the probe.
8. `pre_rpowMonotone`: dsr ≥ RAY ⇒ rpow(dsr, now − rho) ≥ RAY. This is a property of the real `_rpow`.
9. `pre_PieCoversSdaiPie`: Pot.Pie ≥ Pot.pie[sDAI]. In the real Pot, Pie is the sum of all pie.
10. `pre_potSolvent`: vat.dai(pot) ≥ chi·pie[sDAI]. The real system keeps vat.dai(pot) = chi·Pie.
11. `pre_dripNoOverflow`: rpow·chi ≤ max (only when a drip happens), and sin[vow] + rad, vice + rad,
    debt + rad ≤ max. On mainnet chi ≈ 1.05e27 and debt ≈ 5e54 rad, while max ≈ 1.16e77.
12. `pre_exitNoOverflow`: each of these is ≤ max: vat.dai(pot) + rad, vat.dai(sDAI) + chi'·shares,
    vat.dai(daiJoin) + RAY·assets, Dai.totalSupply + assets, and Dai.balanceOf(receiver) + assets.
    The DAI supply is about 5e27 wad.

`depositLiveness` (caller = msg.sender; shares = assets·RAY/chi'):
- Call conditions, which are part of the statement: receiver ∉ {0, sDAI}, Dai.balanceOf(caller) ≥ assets,
  and Dai.allowance(caller, sDAI) ≥ assets.
- `pre_noEther`, `pre_timeNotBeforeRho` (now ≥ rho), `pre_chiAtLeastRay` (chi ≥ RAY), `pre_hopePot`,
  `pre_daiJoinAllowance` (Dai.allowance(sDAI, daiJoin) == max), `pre_potSucks`, `pre_dsrNonNegative`,
  `pre_rpowMonotone`, `pre_PieCoversSdaiPie`.
- `pre_daiBacked`: vat.dai(daiJoin) ≥ RAY·Dai.totalSupply (DAI ERC-20 is backed by Vat dai).
- `pre_daiSupplyCoversHolders`: Dai.totalSupply ≥ bal(caller) + bal(sDAI), with sDAI counted once if
  it is the caller.
- `pre_dripNoOverflow`.
- `pre_joinNoOverflow`: each of these is ≤ max: vat.dai(sDAI) + RAY·assets, Pie + shares, and
  vat.dai(pot) + rad + chi'·shares.

Drop-one checks showed that a redeem/withdraw needs neither now ≥ rho nor chi ≥ RAY. When now < rho,
sDAI uses the stored chi and Pot.exit has no time check. Redeem/withdraw do not divide by chi when
assets = 0. So these two preconditions were left out of those rules.

## Expected failure (finding)

**redeemDoesNotDependOnDrip.** The setup is every redeem-liveness precondition except dsr ≥ RAY.
- **Prover CEX (run d239cba6, corrected per judge):** dsr = 0.5·RAY, rho = 4, now = 7, the uninterpreted rpowG(0.5·RAY, 3, RAY) = 1 (the real _rpow gives 0.125·RAY), chi ≈ 2.4e55, owner holds 1 share. Drip's `tmp - chi` underflows and the redeem reverts. The conclusion holds for the real _rpow: for every dsr < RAY it returns < RAY for n ≥ 1, so the new chi is below the old one.
  `SavingsDai.redeem` sees now > rho and calls `Pot.drip`. Drip computes tmp = rmul(rpow, chi) < chi,
  and the checked `tmp - chi` underflows. Drip reverts, so redeem reverts.
- **Impact:** `Pot.file("dsr", ...)` has no lower bound. If governance sets dsr < RAY (a negative
  rate), every sDAI deposit, mint, withdraw and redeem reverts from the next block onward.
- **No recovery path except cage:** `Pot.file` requires rho == now, which needs a successful drip, so
  the rate cannot be raised again. Only `Pot.cage()` resets dsr to RAY.
- **Direct Pot depositors are unaffected:** `Pot.exit` has no rho == now requirement, so they can
  still exit at the last stored chi.
- **Result:** sDAI holders' DAI is frozen until cage. The cause is SavingsDai calling drip
  whenever now > rho instead of falling back to the stored chi. Severity depends on governance
  ever setting a negative DSR.

## Trust assumptions

- The scene's `rpowG` never reverts, while the real `_rpow` reverts on overflow (inherited from scene.spec).
- Beyond the named liveness preconditions above, the spec adds no bare `require`s.

## Skipped

None.

## Judge round 1: ACCEPT (maker-integration.judge-round1.md)
Known limit: scene.spec's rpowG never reverts while the real _rpow reverts on overflow, so the liveness rules do not cover rpow-overflow reverts. On mainnet parameters (dsr ≈ 1.000000001·RAY) this needs an astronomically long time between drips.

## Pass 3: assumptions now backed by proofs (maker-models)
- pre_chiAtLeastRay: proven invariant potChiAtLeastRay (run 9e14d9f8).
- pre_PieCoversSdaiPie: proven invariant potPieCoversEachPie(sDAI) (run 9e14d9f8).
- pre_daiSupplyCoversHolders: caller == sDAI case is daiBalanceAtMostSupply (run 0e288f36); otherwise follows arithmetically from daiSupplyIsSum (not separately machine-checked).
- pre_hopeDaiJoin / pre_hopePot / pre_daiJoinAllowance: established by SavingsDai's constructor, constructorWiresMakerSystem (run e81898a8, under A1/A2); never undone by SavingsDai methods (setupApprovalsPreserved). Third-party Vat/Dai calls (e.g. Dai.permit with holder = sDAI) remain argued.
- The scene.spec NONDET of the constructor's hope/approve is still why these appear as preconditions in this spec; the separate constructor proof covers them.
Spec comments still describe the pass-2 reasoning; the proofs above supersede it.
