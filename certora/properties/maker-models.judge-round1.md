VERDICT: ACCEPT

# maker-models, judge round 1 (pass 3)

Reviewed: specs/maker-models/{pot-invariants,dai-invariants,constructor}.spec, confs/maker-models-{pot,dai,constructor}.conf, base.conf, scene.spec, harnesses Pot/Vat/DaiJoin/Dai, src/SavingsDai.sol (constructor), maker-models.{properties.json,property_rules.json,commentary.md}, and the consumers in erc4626-vault.spec and maker-integration.spec. I also checked the run logs (certora/logs/maker-models-{pot,dai}_run1.log, maker-models-constructor_run2.log, maker-models-constructor_probe.log) against the claims, and checked docs methods.txt and invariants.txt.

Run evidence I confirmed:
- Pot (9e14d9f8): base case plus all 8 Pot entry points (drip, join, exit, file x2, cage, rely, deny) VERIFIED for all three invariants. The sanity checks `rule_not_vacuous` and `invariant_not_trivial_postcondition` are "Violated", which is the passing outcome.
- Dai (0e288f36): base case plus all 11 Dai entry points (transfer, transferFrom, mint, burn, approve, push, pull, move, rely, deny, permit) VERIFIED for both invariants. Sanity passes.
- Constructor (e81898a8): `constructorWiresMakerSystem-Induction base: After the constructor` VERIFIED. Both sanity checks pass, so the optimistic dispatch does not make the base case vacuous. The only warning is that the generic preserved block applies to no method, which is expected with `f -> false`.
- Probe (0cbfecac): it runs the same spec and conf plus three probe invariants. All three are VIOLATED in the base case, and the main invariant is still VERIFIED.

## 1. Code smells

None blocking.
- Every methods-block entry is used. In constructor.spec, the four DISPATCH entries and the envfree getters and `Vat.can`/`Dai.allowance` are all exercised by the invariant.
- No asserts are tautological. `daiJoin() == daiJoinC` follows from A1, but it still checks that the constructor stores `_daiJoin`, and sanity confirms it is not a trivially true postcondition.
- In scene.spec (imported by the Pot spec), the wildcard UNRESOLVED NONDET entries never fire, because Pot's only calls go to the linked Vat. That is harmless.
- The `filtered { f -> false }` with an empty generic preserved block warning is intended.

## 2. Guideline compliance (23 rules)

Compliant. Types are correct (`to_mathint` only where it helps readability). Ghost/hook use is justified under G23 because a sum over a mapping cannot be read directly from storage. No `persistent` ghosts. `RAY()` is a definition. Invariant parameters are used instead of `forall` (G22). Dispatch-list patterns omit data locations (G7), and the contract names are type names, not aliases (G8).

On the docs points I was asked to check:
- **`filtered { f -> false }` on an invariant.** The invariants grammar allows `filtered { id -> expression }` on invariants. The docs say filters (and `parametric_contracts`) restrict the methods checked for preservation. The induction base is a separate check, and the run log shows it ran and passed sanity. Filtering everything is unsound as a full invariant (invariants.html, "Filters"). Here that is deliberate and declared: preservation over SavingsDai methods is `setupApprovalsPreserved`.
- **DISPATCH lists on a regular wildcard entry.** The methods grammar allows `dispatch_list` as a `method_summary`, with `DISPATCH(optimistic=...)` and `default`. methods.html documents that dispatch matches both selector and target address, and that the optimistic form inlines `ASSUME FALSE` when nothing matches. The A1 encoding is therefore exactly "the target of `daiJoin.vat()` is DaiJoin".

## 3. Precondition validity

The Pot and Dai Sload hooks (`require sum >= loaded value`) restrict the prestate of the induction step. They are sound:
- The ghosts start at 0 (`init_state`, and the constructors write no pie or balance entries).
- Every store is tracked by the Sstore hook.
- Neither Pot nor Dai makes an unresolved call, so the ghosts are never havoced.

So in every reachable state the ghost is the true sum of uint256 terms, and the hook never excludes a reachable state.

The constructor base case only asserts entries that the constructor itself writes (`can[sDAI][daiJoin]`, `can[sDAI][pot]`, `allowance[sDAI][daiJoin]`), so the initial Vat/Dai state is irrelevant.

## 4. Overconstrained inputs

No bare `require` in any rule body.

The only assumptions are A1 (optimistic `daiJoin.vat()` dispatch, meaning `_daiJoin` is the scene DaiJoin) and A2 (conf links `DaiJoin:vat=Vat` and `DaiJoin:dai=Dai`). Both are necessary for a statement about the scene contracts, and both match the deployment every other component verifies (base.conf links `SavingsDai:daiJoin=DaiJoin` and the same DaiJoin links).

They are minimal:
- `_pot` is left free.
- `daiJoin.dai()`, `vat.hope` and `dai.approve` are pessimistic with `default ASSERT_FALSE`, so their routing is checked, not assumed. This also rules out the `SavingsDai.approve` dispatch pitfall.
- A1 cannot be expressed through `preserved constructor()`, because the docs say constructor arguments are not captured there.

Dropping the SavingsDai immutable links removes assumptions, which is the sound direction. The 5ab7d489 experiment correctly shows why they had to go. The probe run shows the post-constructor state is not over-constrained.

## 5. Trivializing summaries

None.
- `Pot._rpow => rpowG` is uninterpreted and unconstrained, so `chi >= RAY` is proven for every possible rpow result. The real `_rpow` (deterministic or reverting) is a special case. This is the same summary all consumers run under.
- constructor.spec does not import scene.spec, so the constructor's hope/approve writes really execute.

## 6. Manifest errors

None. Each invariant states the obviously intended fact. drip's checked `tmp - chi` gives monotonicity, and join/exit change `pie[msg.sender]` and `Pie` by the same `wad`.

## 7. Meaningful contract interaction

Every verdict depends on contract state:
- `chi`, `Pie`, `pie`, `totalSupply` and `balanceOf` are read from the contracts, and the ghosts are fed only by Sstore hooks on contract storage.
- The constructor invariant reads SavingsDai's stored immutables and `Vat.can`/`Dai.allowance` as written by the dispatched calls. Run 5ab7d489 (VIOLATED with `_pot != Pot`) and probe 0cbfecac (VIOLATED probes) show that the verdict really depends on the constructor's behavior.

## 8. Property coverage

All 4 properties are formalized and VERIFIED in full, unfiltered runs. Nothing is skipped and nothing is expected to fail.

I checked the "discharges" table in the commentary claim by claim:
- **`requirePotChiAtLeastRay` / `pre_chiAtLeastRay`.** Accurate. Fully discharged by `potChiAtLeastRay` under the same rpowG summary (base case plus all Pot methods). `potChiNeverDecreases` is indeed just the induction step.
- **`pre_PieCoversSdaiPie`.** Accurate. `potPieCoversEachPie(sDAI)` covers it.
- **Base case of `daiSupplyIsSumPreserved` / `requireDaiSupplyIsSum`.** Accurate. erc4626-vault's `sumDaiBalances` has the same definition (init 0, same Sstore hook).
- **`pre_daiSupplyCoversHolders(caller)`.** The partial claim is accurate and honestly labelled:
  - When `caller == sDAI`, the precondition is exactly `daiBalanceAtMostSupply`, which is proven.
  - When `caller != sDAI`, it is a sound arithmetic consequence of the proven `totalSupply == Σ balanceOf` (two distinct non-negative terms of the sum), but it is not a prover result.
  - The commentary is right that the existing single-term Sload hook does not make the pairwise bound inductive.
- **`pre_hopeDaiJoin` / `pre_hopePot` / `pre_daiJoinAllowance`.** Accurately described as base case (`constructorWiresMakerSystem`, for any `_pot`, so in particular `pot = Pot`), plus the step over SavingsDai methods (`setupApprovalsPreserved`), plus an argued third-party step. The argument is correct:
  - `Vat.hope`/`nope` and `Dai.approve` write only `msg.sender`'s entries, and sDAI never calls `nope`, or `approve` after construction.
  - `Dai.transferFrom`/`burn` skip the decrement when the allowance is max.
  - Pot/DaiJoin calls into the Vat do not touch `can`.
  - The only real hole is `Dai.permit` with `holder = sDAI`, which needs an ECDSA signature for a contract address.

  This gap is clearly stated as unproven, so it is not a coverage defect for this round.

## Non-blocking issues (fix when convenient; not required for acceptance)

1. **properties.json, `constructor_wires_maker_system`.** The description says the constructor "sets vat/dai/daiJoin/pot to those contracts" and states the hypothesis only as "daiJoin.vat() is the Vat, daiJoin.dai() is the Dai". The formalization does not (and cannot) claim `pot() == Pot`. It proves the setup for the stored `pot()` with `_pot` free, and it also assumes A1 (`_daiJoin` is the scene DaiJoin). Reword the description to match: A1 and A2 as the hypothesis, "pot() is the `_pot` argument, hoped for any `_pot`".
2. **commentary.md, "drops those four links ... keeps DaiJoin:vat=Vat and DaiJoin:dai=Dai".** maker-models-constructor.conf also drops base.conf's `Pot:vat=Vat`, so five links are dropped. This is harmless, because Pot code never runs and dropping a link is sound, but the text should say so.
3. **Optional follow-up to close the third-party gap.** A parametric rule over Vat and Dai methods would close it: `parametric_contracts: ["Vat","Dai"]`, asserting that `can[sDAI][DaiJoin]`, `can[sDAI][Pot]` and `allowance[sDAI][DaiJoin] == max` are preserved. It would need two stated assumptions:
   - `e.msg.sender != sDAI`, under the criterion-4 carve-out. sDAI-originated calls are already covered by `setupApprovalsPreserved`.
   - `permit` holder != sDAI, a cryptographic assumption.
4. **Consumer comments.** The comments in maker-integration.spec (for example "scene.spec NONDETs the constructor's hope, so it is stated here") and in erc4626-vault.spec (`requirePotChiAtLeastRay`, `requireDaiSupplyIsSum`) should cite the maker-models results and run ids. That edit belongs to those components.

## Required changes

None.
