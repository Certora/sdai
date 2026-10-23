# maker-models: commentary (pass 3, round 1)

This component proves facts about the scene contracts themselves (Pot, Dai, and SavingsDai's
constructor). Earlier passes had only argued these facts as base cases. Each spec checks a
different main contract, so each one has its own conf.

| Conf | Verified contract | Spec | Final full run (unfiltered) |
|---|---|---|---|
| `certora/confs/maker-models-pot.conf` | `Pot` | `certora/specs/maker-models/pot-invariants.spec` | https://prover.certora.com/orgs/certora/jobs/9e14d9f8-da5c-472f-9cbf-223ef1ab6e3f/report |
| `certora/confs/maker-models-dai.conf` | `Dai` | `certora/specs/maker-models/dai-invariants.spec` | https://prover.certora.com/orgs/certora/jobs/0e288f36-9e75-43a0-82ce-c6276d96aad8/report |
| `certora/confs/maker-models-constructor.conf` | `SavingsDai` | `certora/specs/maker-models/constructor.spec` | https://prover.certora.com/orgs/certora/jobs/e81898a8-1c9f-4100-9232-96be4a73c267/report |

All runs use `rule_sanity: basic` and passed every sanity check. No prover options were added
beyond those in `invariants.conf`.

## Results

| Property | Rule(s) | Result |
|---|---|---|
| pot_chi_at_least_ray | `potChiAtLeastRay` | VERIFIED (base: Pot constructor; step: every Pot method) |
| pot_total_pie_is_sum | `potTotalPieIsSum`, corollary `potPieCoversEachPie(a)` | VERIFIED / VERIFIED |
| dai_supply_is_sum | `daiSupplyIsSum`, corollary `daiBalanceAtMostSupply(a)` | VERIFIED / VERIFIED |
| constructor_wires_maker_system | `constructorWiresMakerSystem` | VERIFIED (induction base = SavingsDai constructor) |

No property was skipped and no failure is expected.

## Pot (pot-invariants.spec)

- **Setup.** `verify: Pot:...` and `parametric_contracts: ["Pot"]`. The files and links are those
  of `invariants.conf`. The invariant base case is Pot's own constructor, which sets `chi = RAY`
  and writes no `pie` entry.
- **Why the Pot methods are enough.** Only Pot code writes Pot storage. Pot's external calls
  (`vat.suck`, `vat.move`) resolve through `Pot:vat=Vat` to the real Vat, and the Vat never calls
  back. So covering every Pot entry point (drip, join, exit, both `file`s, cage, rely, deny) covers
  every state reachable from Pot's constructor, whoever the callers are.
- **Imports.** `scene.spec` is imported only for its `Pot._rpow => rpowG(x, n, base)` summary. This
  is the same summary every SavingsDai spec runs under. The spec puts no constraint on `rpowG`, so
  `chi >= RAY` holds for any value that rpow could return. scene.spec's other entries do not apply
  here: they are wildcard entries with the UNRESOLVED policy, and Pot makes none of those calls (the
  prover warns that the `hope` summary is unused). `invariants.spec` and the autosetup summary files
  are not imported. They concern SavingsDai, and both summary files are empty.
- **chi.** drip is the only function that writes chi. It reverts unless `tmp - chi` does not
  underflow, so chi never decreases.
- **Sum.** The ghost `sumPie` (`init_state` 0) is maintained by an Sstore hook on `pie`.
  `Pie == sumPie` holds because join and exit change `pie[msg.sender]` and `Pie` by the same checked
  `wad`.
- **Corollary `potPieCoversEachPie(a)`.** It states `Pie >= pie[a]` and uses
  `requireInvariant potTotalPieIsSum()`. It also relies on the standard Sload hook
  `require sumPie >= pie[a]`. That hook is sound because `sumPie` is exactly the sum of all `pie`
  entries, which are uint256 and so non-negative. Pot is the main contract and makes no unresolved
  calls, so the ghost is never havoced.

## Dai (dai-invariants.spec)

- **Setup.** `verify: Dai:...` and `parametric_contracts: ["Dai"]`. The base case is Dai's
  constructor, which writes no balance and leaves `totalSupply = 0`. Dai makes no external calls
  (`ecrecover` is a precompile), so the spec imports nothing.
- **Invariants.** `daiSupplyIsSum` uses a ghost and an Sstore hook on `balanceOf`. The corollary
  `daiBalanceAtMostSupply(a)` (`balanceOf(a) <= totalSupply`) uses the same Sload-hook pattern as
  Pot.
- **Coverage.** The step covers every Dai method: transfer, transferFrom, mint, burn, approve, push,
  pull, move, rely, deny, permit. Only Dai code writes Dai storage, so the DaiJoin `mint`/`burn`
  calls and the SavingsDai `transferFrom`/`approve` calls are covered too.
- **Pairwise bound.** The property's consequence `balance(a) + balance(b) <= totalSupply` for
  distinct a and b is **not** machine-checked as a separate rule. It is not inductive on its own: a
  transfer from some third account c needs a bound on three balances. It follows from
  `daiSupplyIsSum` by arithmetic, because a and b are two distinct non-negative terms of the sum.
  The single-term case is proven (`daiBalanceAtMostSupply`).

## SavingsDai constructor (constructor.spec)

**Formulation.** CVL cannot call a constructor. The only check of a constructor is an invariant's
induction base (invariants.html, "the Prover checks ... that the invariant is established after
calling any constructor"; "`preserved constructor()` applies on the base step ... the arguments of
the constructor are not captured"). `constructorWiresMakerSystem` is therefore an invariant over
SavingsDai with `filtered { f -> false }`, which makes the run exactly the base-case check.
Preservation by every SavingsDai method was already proven elsewhere: maker-integration's
`setupApprovalsPreserved`.

The invariant states:

```
daiJoin() == DaiJoin && vat() == Vat && dai() == Dai
&& Vat.can(sDAI, daiJoin()) == 1 && Vat.can(sDAI, pot()) == 1
&& Dai.allowance(sDAI, daiJoin()) == max_uint256
```

**Why this spec does not use scene.spec or base.conf's SavingsDai links.**
1. scene.spec NONDETs `_.hope`, `_.approve`, `_.vat` and `_.dai`. Those calls are exactly the
   constructor's calls, so the NONDETs would drop the writes this property is about. The spec
   imports neither scene.spec nor invariants.spec (which imports scene.spec). It needs no
   `_rpow`/`isValidSignature` summary, because no method runs.
2. With `SavingsDai:{vat,dai,daiJoin,pot}=...` linked, the prover reads SavingsDai's immutables as
   those constants, even right after the constructor ran with other arguments. Experiment run
   5ab7d489 (https://prover.certora.com/orgs/certora/jobs/5ab7d489-f109-488f-8826-c3f3c6ca4f34/report)
   showed this. `pot() == Pot` failed sanity as a trivially true postcondition, while
   `Vat.can(sDAI, Pot) == 1` was VIOLATED in the base case with `_pot != Pot`. So
   `maker-models-constructor.conf` drops those five links (SavingsDai:{vat,dai,daiJoin,pot} and Pot:vat) (base.conf itself is unchanged) and keeps
   `DaiJoin:vat=Vat` and `DaiJoin:dai=Dai`. The getters then return what the constructor stored.

**How the constructor's calls are resolved.** The calls go to arbitrary constructor arguments, so
they are unresolved. Each one has its own entry:

| Call | Summary | Meaning |
|---|---|---|
| `daiJoin.vat()` | `DISPATCH(optimistic=true) [DaiJoin.vat()]` | Assumption A1 (below). |
| `daiJoin.dai()` | `DISPATCH [DaiJoin.dai()] default ASSERT_FALSE` | Checked, not assumed. |
| `vat.hope(x)` | `DISPATCH [Vat.hope(address)] default ASSERT_FALSE` | Checked, not assumed. |
| `dai.approve(x, v)` | `DISPATCH [Dai.approve(address,uint256)] default ASSERT_FALSE` | Checked, not assumed. |

A DISPATCH list matches on both the selector and the target address (methods.html, "DISPATCH list
summaries"). For the three pessimistic entries, any call that went elsewhere would hit `assert
false` and fail the run. The run passed, so those calls provably reach the scene Dai/Vat functions
under A1 and A2.

**The `approve` pitfall.** A plain `_.approve => DISPATCHER` would include
`SavingsDai.approve(address,uint256)` among its candidates. The explicit list rules this out: it
names only `Dai.approve`, and any other target fails the run.

**Deployment-consistency assumptions** (the property's hypothesis):
- **A1:** the `_daiJoin` argument is the scene DaiJoin. This comes from the optimistic dispatch of
  the first call, `daiJoin.vat()`.
- **A2:** `DaiJoin.vat` is the Vat and `DaiJoin.dai` is the Dai. These are the conf links.
- `_pot` is **unconstrained**. The constructor never calls it, only stores and hopes it, so the
  invariant uses `pot()` (the stored value). A reader who also assumes base.conf's
  `SavingsDai:pot=Pot` (the deployment every other spec verifies) gets `Vat.can(sDAI, Pot) == 1`.

**Non-triviality.** Probe run 0cbfecac
(https://prover.certora.com/orgs/certora/jobs/0cbfecac-3505-4662-9eba-3b2894c8865d/report) added
three temporary invariants, since removed. All three were VIOLATED in the base case:
`Vat.can(sDAI, Vat) == 1`, `pot() == DaiJoin`, and `Dai.allowance(sDAI, pot()) == max`. So the
dispatch assumptions do not over-constrain the post-constructor state.

**Bonus.** The run proves that, under A1 and A2, the constructor stores `vat = Vat` and
`dai = Dai`. Two of base.conf's links (`SavingsDai:vat=Vat` and `SavingsDai:dai=Dai`) therefore
follow from `SavingsDai:daiJoin=DaiJoin` plus the DaiJoin links. They are not independent
assumptions.

## Discharge of assumptions argued in other components

| Assumption (component) | Discharged by | How to cite |
|---|---|---|
| `requirePotChiAtLeastRay` (erc4626-vault); `pre_chiAtLeastRay` (maker-integration) | `potChiAtLeastRay` | Every Pot state reachable from Pot's constructor through any sequence of Pot calls, by any caller, has `chi >= RAY`. This holds under the same `rpowG` summary, with `rpowG` unconstrained. Cite "maker-models potChiAtLeastRay, run 9e14d9f8". `potChiNeverDecreases` (erc4626-vault) is now subsumed: it is the induction step alone. |
| `pre_PieCoversSdaiPie` (maker-integration) | `potPieCoversEachPie(sDAI)` (with `potTotalPieIsSum`) | Fully discharged, run 9e14d9f8. |
| Base case of `daiSupplyIsSumPreserved` / `requireDaiSupplyIsSum` (erc4626-vault) | `daiSupplyIsSum` | Fully discharged: base case and step, run 0e288f36. erc4626-vault's own ghost `sumDaiBalances` is defined identically (init 0, same Sstore hook). |
| `pre_daiSupplyCoversHolders(caller)` (maker-integration) | `daiSupplyIsSum` + arithmetic | For `caller == sDAI` it is exactly `daiBalanceAtMostSupply`, which is proven. For `caller != sDAI` it follows from the proven equality, because two distinct non-negative terms of a sum do not exceed the sum. That step is arithmetic, not a prover result. Cite it as "follows from maker-models daiSupplyIsSum". |
| `pre_hopeDaiJoin`, `pre_hopePot`, `pre_daiJoinAllowance` (maker-integration), and the setup that `setupApprovalsPreserved` assumes | Base: `constructorWiresMakerSystem` (run e81898a8). Step over SavingsDai methods: `setupApprovalsPreserved` (maker-integration run d239cba6). | The base case is proven under A1/A2, with `pot() = Pot` taken from the scene link. One part remains argued (see below). |

**What remains argued for the hope/allowance preconditions.** Methods of other contracts called
directly by third parties are not machine-checked here. The argument:
- `Vat.hope`/`nope` and `Dai.approve` write only `msg.sender`'s own entries, and sDAI never calls
  `nope` or `approve` after construction.
- `Dai.transferFrom` and `Dai.burn` by DaiJoin leave a max allowance unchanged.
- `Dai.permit` with `holder = sDAI` needs an ECDSA signature for sDAI's contract address.

A follow-up could close this with a parametric rule over the Vat and Dai methods (with `permit`
holder ≠ sDAI as the stated assumption).

## Files

- `certora/specs/maker-models/pot-invariants.spec`, `dai-invariants.spec`, `constructor.spec`
- `certora/confs/maker-models-pot.conf`, `maker-models-dai.conf`, `maker-models-constructor.conf`
- `certora/properties/maker-models.property_rules.json`
- Logs: `certora/logs/maker-models-{pot,dai}_run1.log`, `maker-models-constructor_run{1,2}.log`, `maker-models-constructor_probe.log`

## Judge round 1: ACCEPT (maker-models.judge-round1.md)
Open follow-up: a rule over all Vat and Dai methods (msg.sender != sDAI, permit holder != sDAI) would close the remaining third-party gap for sDAI's hope/allowance setup.
