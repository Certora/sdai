# invariants batch — generator commentary (round 2)

- Spec: `certora/specs/invariants.spec`.
- Conf: `certora/confs/invariants.conf`. A typecheck-only copy is `certora/confs/invariants_tc.conf` (the same conf plus
  `compilation_steps_only`).
- The conf overlays `SavingsDai.conf` with these settings:
  - `verify` points to invariants.spec;
  - `rule_sanity: basic`;
  - `optimistic_loop: true`;
  - `parametric_contracts: ["SavingsDai","PotHarness","VatMock","DaiJoinMock","DaiMock"]`;
  - `wait_for_results: none`.
- There is no rule filter in the conf.

## Final run (full, unfiltered)
- Tag `invariants_iter3`, job `3c95349d-c8a0-4655-ad5a-4285034a5ed9`, about 10 minutes, `rule_sanity: basic`.
  https://app.certora.com/orgs/certora/jobs/3c95349d-c8a0-4655-ad5a-4285034a5ed9/report
- Every instance is VERIFIED. That is 52 methods + constructor = 53 for each invariant, except potVatDaiCoversSavings
  with 52, because setYield is excluded.
- `envfreeFuncsStaticCheck` is VERIFIED.
- There are no expected failures.

Earlier runs:
- `invariants_iter1` (job `0f41511d-cf2c-427e-97ec-5d01670c76ac`): the constructor base cases failed, and the DaiJoin
  invariant failed on deposit/mint. See below.
- `invariants_iter2` (job `9122f592-4c3a-4f21-bba9-7df523bb1c60`): everything was VERIFIED with the round-1 scope. The
  judge rejected it because three invariants were filtered to SavingsDai only.

## Property -> invariant, and scope
"All 52" means every non-view method of SavingsDai, PotHarness, VatMock, DaiJoinMock and DaiMock. The constructor is
always checked as well.

| Property | Invariant(s) | Methods / exclusions |
|---|---|---|
| total_supply_equals_sum_of_balances | totalSupplyEqualsSumOfBalances | all 52; no caller restriction |
| shares_equal_pot_pie | sharesEqualPotPie | all 52; caller != sDAI |
| pot_total_pie_covers_sdai_pie | potTotalPieCoversSdaiPie (+ potTotalPieEqualsSumOfPie) | all 52; no caller restriction (the `msg.sender != sDAI` require the judge proposed turned out unnecessary, so it was left out — strictly fewer assumptions) |
| pot_vat_dai_covers_savings | potVatDaiCoversSavings (+ noVatPermissionsFromPotOrDaiJoin) | all 52 except `PotHarness.setYield`; trusted-actor restriction (below) |
| daijoin_vat_dai_covers_dai_supply | daiJoinVatDaiCoversDaiSupply (+ daiTotalSupplyEqualsSumOfDaiBalances, noVatPermissionsFromPotOrDaiJoin) | all 52; trusted-actor restriction |
| sdai_setup_permissions_persist | sdaiSetupPermissionsPersist | all 52; caller != sDAI; for `DaiMock.permit`, owner != sDAI |

Supporting invariants are not in the property list. None of them has a method filter:
- `potTotalPieEqualsSumOfPie`: Pot `Pie == Σ pie`, over all 52 methods with no caller restriction.
- `daiTotalSupplyEqualsSumOfDaiBalances`: DAI `totalSupply == Σ balanceOf`, over all 52 methods with no caller
  restriction.
- `noVatPermissionsFromPotOrDaiJoin(x)`: `Vat.can[Pot][x] == 0 && Vat.can[DaiJoin][x] == 0`, over all 52 methods. The
  caller is neither the Pot nor DaiJoin.

### Exclusions for the two Maker-side solvency invariants
- **`PotHarness.setYield` (selector filter, potVatDaiCoversSavings only).** setYield is a test hook in PotMock. It sets
  `chi = (Pie+yield)*RAY/Pie` but sucks only `Pie*yield`, which mixes up units. Mainnet Pot has no such function: the
  harness restores mainnet `drip()`, and drip is checked and VERIFIED. daiJoinVatDaiCoversDaiSupply needed no
  exclusion, so it covers setYield too.
- **Trusted-actor restriction:** the CVL function `requireUntrustedExternalCaller(e)` is used in the generic
  preserved block of both invariants.
  - `vatMock.wards[caller] == 0`, `potHarness.wards[caller] == 0`, `daiMock.wards[caller] == 0`.
    - Why: Maker governance is trusted (NOTES).
    - Effect: the ward-only functions revert in these checks. On the Vat these are suck, fold, grab, slip, file, init,
      cage, rely and deny. On the Pot: file, cage, rely and deny. On Dai: mint, rely and deny.
    - Nested calls are not restricted: the Pot's `vat.suck` in drip and DaiJoin's `dai.mint` in exit run with the
      contract itself as msg.sender. So drip and DaiJoin.exit are fully checked.
  - `caller ∉ {savingsDai, potHarness, daiJoinMock}`.
    - Why: these are contracts without private keys, so they never originate a transaction.
    - Every call they make happens inside one of their own methods, and those methods are checked in the same
      invariant.
  - `requireInvariant noVatPermissionsFromPotOrDaiJoin(e.msg.sender)`. Without it, a free prestate could give the
    caller `can[Pot][caller]` and let it drain `dai[pot]` through Vat.move or Vat.frob.
- **Permissionless Maker methods proven not to break the invariants:**
  - Pot.join, Pot.exit and Pot.drip;
  - DaiJoin.join and DaiJoin.exit;
  - Vat.move, frob, fork, flux, heal, hope and nope;
  - every Dai method that is not ward-only (transfer, transferFrom, burn, approve, permit, ...).
- No Maker method needed an individual excuse.

## Ghosts, hooks and their requires
- **`sumBalances`** is the sum of sDAI balanceOf.
  - It has `init_state axiom sumBalances == 0`. That is sound because the base case resets sDAI storage to 0.
  - **Load-hook require:** `bal <= sumBalances`. Each balance is a non-negative summand of the sum, which is the
    standard ERC20-sum fact.
  - Why it is needed: in `transfer`, `balanceOf[to] += value` is unchecked. The load of `balanceOf[to]` comes after
    `balanceOf[from]` is decreased, so the require bounds `balanceOf[to] + value` by totalSupply.
- **`sumDaiBalances`** is the sum of DaiMock.balanceOf.
  - **Load-hook require:** `bal <= sumDaiBalances`, the same fact.
  - It has no init_state axiom, because DAI already exists at sDAI deployment.
  - Why it is needed: Dai.burn and transferFrom use unchecked arithmetic.
- **`sumPie`** is the sum of Pot pie. It is new in round 2 and has no init_state axiom.
  - **Load-hook requires:**
    - `p <= sumPie`;
    - `a != sDAI => p + pie[sDAI] <= sumPie`. Two distinct non-negative summands are at most the sum. Pot.exit by
      another user `a` needs this to keep `Pie - wad >= pie[sDAI]`: the one-summand bound is not enough.
  - Where `potTotalPieEqualsSumOfPie` is not required, sumPie is a free ghost, and these requires only bound it.
- **`ctorHopeCalls`** counts the `hope` calls the constructor makes. See the constructor resolution section below.

## Constructor (base case) call resolution (accepted by the judge in round 1)
- **Problem:** inside sDAI's constructor, `daiJoin` and `pot` are still the free constructor arguments. So
  `daiJoin.vat()`, `daiJoin.dai()`, `vat.hope(...)` x2 and `dai.approve(...)` were unresolved and havoced all ghosts.
- **Fix:** wildcard entries in the methods block, using the UNRESOLVED policy.
  - Because of that policy they apply only to these constructor calls. After construction every call is linked.
  - Each entry runs the real `vatMock.hope` / `daiMock.approve` with msg.sender = sDAI and msg.value = 0, or returns
    the linked immutable.
- **What is asserted and what is assumed:**
  - Asserted: the callee of `dai()`, `hope` and `approve`, and that the first `hope` is for daiJoin.
  - Assumed: only the two constructor arguments. `require callee == daiJoinMock` in `vat()` pins
    `_daiJoin == DaiJoinMock`. `require ctorHopeCalls == 1 => usr == potHarness` pins `_pot == PotHarness`.
  - These are the same assumptions the shared links block already makes.

## Every bare require
- **Load hooks:** the three summand facts above.
- **Constructor, sDAI's Pot pie:** `preserved constructor()` in sharesEqualPotPie and potTotalPieCoversSdaiPie
  requires `potHarness.pie[savingsDai] == 0`. sDAI's address has never run code, so it cannot have called Pot.join.
- **Constructor, Maker state:** these blocks require the invariant on the pre-existing Maker state at sDAI deployment:
  - potVatDaiCoversSavings: Pot solvent;
  - daiJoinVatDaiCoversDaiSupply: DaiJoin backs all DAI;
  - daiTotalSupplyEqualsSumOfDaiBalances: DAI sum is consistent;
  - **new** potTotalPieEqualsSumOfPie: Pot `Pie == Σ pie`;
  - **new** noVatPermissionsFromPotOrDaiJoin: Pot and DaiJoin have no Vat `can`.

  Each holds from Maker's all-zero deployment, and the preservation checks above show every non-governance method
  keeps it. sDAI's constructor writes only `Vat.can[sDAI][*]` and `Dai.allowance[sDAI][*]`.
- **Caller is not sDAI:** sharesEqualPotPie and sdaiSetupPermissionsPersist require `e.msg.sender != savingsDai`,
  because sDAI never originates a transaction.
- **Permit signer:** `preserved DaiMock.permit(...)` (both overloads) in sdaiSetupPermissionsPersist requires
  `owner != savingsDai`. This is ECDSA unforgeability: no key exists for sDAI's address, and sDAI has no
  `isValidSignature`.
- **New: `requireUntrustedExternalCaller(e)`** in potVatDaiCoversSavings and daiJoinVatDaiCoversDaiSupply: no ward,
  and not sDAI, the Pot or DaiJoin (see above).
- **New:** noVatPermissionsFromPotOrDaiJoin requires that the caller is neither potHarness nor daiJoinMock, for the
  same never-originates reason.
- **Constructor env:** in the constructor summaries, `msg.sender == executingContract` and `msg.value == 0`.
- `requireInvariant` (these are not bare requires):
  - sharesEqualPotPie in totalSupplyEqualsSumOfBalances;
  - potTotalPieEqualsSumOfPie in potTotalPieCoversSdaiPie;
  - noVatPermissionsFromPotOrDaiJoin in invariants 4 and 5;
  - daiTotalSupplyEqualsSumOfDaiBalances in invariant 5.

## Summaries
- **Shared rpow_summary.spec:** this is enough here, because Pot.drip's checked `tmp - chi` forces `chi' >= chi`, and
  `vat.suck(vow, pot, Pie*(chi'-chi))` keeps `dai[pot] >= chi*Pie`.
- **Spec-local:** only the four constructor-only UNRESOLVED wildcard entries. None of them is NONDET.

## Minor cleanups (round 2)
- Removed the redundant `to_mathint(...)` wrappers.
- Removed the unused `with (env e)` in totalSupplyEqualsSumOfBalances.

## Notes for the orchestrator / shared setup
- **Methods-block receiver for Pot getters:** use `PotHarness.`, not `PotMock.`. PotMock is not a scene contract, and
  `PotMock.pie(...)` gives "Contract `PotMock` not found".
- **Constructor havoc in other specs:** a spec with invariants that does not import invariants.spec hits the
  constructor havoc. Component specs should import invariants.spec, or they will clash with or duplicate its
  wildcard entries for `vat()`, `dai()`, `hope(address)` and `approve(address,uint256)`.
- **Scope statement for NOTES_FOR_AGENTS.md:** all six invariants are now proven over all scene methods, under the
  exclusions listed above. Component specs can `requireInvariant` them at arbitrary states only where the same trusted
  actors are assumed. In practice that holds whenever the rule's top-level caller is not a Maker ward and not
  sDAI/Pot/DaiJoin.
  - potVatDaiCoversSavings and daiJoinVatDaiCoversDaiSupply also assume that setYield is never called (a mock
    artifact).

## Phase 6 round-1 barrier changes (orchestrator)
- The `using` aliases and `links` block are now inlined from summaries/SavingsDai_call_resolution.spec instead of imported.
  Reason: hooks in an imported spec cannot see aliases from a file that spec imports, so no component spec could import
  invariants.spec ("hook contract 'daiMock' must be an imported contract"). This changes no meaning; staged copy
  verified as job b6f968e7-6bc7-457c-b8b3-b13abaf04dd4.
- Added supporting invariant `chiAtLeastRay` (requested by the erc4626-vault generator), proven over all 5 scene
  contracts. Constructor require: Pot chi >= RAY at sDAI deployment (Maker assumption).
- Gate re-run: tag invariants_barrier1, job 1080ee77-78e7-4afb-bb57-8a5da4e46a62: all 11 invariants VERIFIED
  (potVatDaiCoversSavings 52/52 with setYield filtered; all others 53/53).
