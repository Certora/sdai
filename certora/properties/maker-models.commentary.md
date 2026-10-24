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

## Pass 4 (round 1): dai_pairwise_balance_bound, third_parties_cannot_revoke_sdai_setup

The pass-3 rules and invariants are unchanged in substance. The Dai Sstore hook also updates a new
mirror ghost. No assumption was added to the existing invariants: the Sload hook is untouched, and
the new invariants are separate. The full Dai conf was re-run, and `daiSupplyIsSum` and
`daiBalanceAtMostSupply` are VERIFIED again.

| Conf | Verified contract / parametric | Spec | Final full run (unfiltered) |
|---|---|---|---|
| `certora/confs/maker-models-dai.conf` (re-run) | `Dai` / `[Dai]` | `certora/specs/maker-models/dai-invariants.spec` | https://prover.certora.com/orgs/certora/jobs/b722fc7e-703d-4dda-98f5-50c1500e23ef/report |
| `certora/confs/maker-models-setup.conf` (new) | `Vat` / `[Vat, Dai, Pot, DaiJoin]` | `certora/specs/maker-models/setup-third-party.spec` | https://prover.certora.com/orgs/certora/jobs/2047f9f4-334e-46fc-80d1-c76809d44b2c/report |

`maker-models-setup.conf` is `maker-models-pot.conf` with three changes: `verify`, the
`parametric_contracts` list, and `msg`. It has the same files, links and options, with
`rule_sanity: basic`. Both runs report "No errors found by Prover!" and pass every sanity check.

| Property | Rule(s) | Result |
|---|---|---|
| dai_pairwise_balance_bound | `daiPairwiseBalanceBound(a, b)`; auxiliaries `daiMirrorMatchesBalance(a)`, `daiSumGhostIsMirrorUsum()` | VERIFIED / VERIFIED / VERIFIED |
| third_parties_cannot_revoke_sdai_setup | `thirdPartiesCannotRevokeSdaiSetup` (parametric); `permitBySdaiRevertsUnderKeyAssumption`; witness `permitBySdaiReachableWithoutKeyAssumption` | VERIFIED on all 62 entry points / VERIFIED / SATISFIED |

### dai_pairwise_balance_bound (now machine-checked)

The pass-3 commentary said this bound was only arithmetic. It is now proven, as follows.

**Why it is not proven directly.** The bound `bal(a) + bal(b) <= supply` is not inductive on its
own. A transfer from a third account c raises `bal(a) + bal(b)`, and bounding that needs three
balances.

**The two auxiliary invariants.**
- `daiBalMirror` is a ghost mapping that the Sstore hook keeps equal to `balanceOf` entry by entry.
  `daiMirrorMatchesBalance(a)` proves that it does.
- `daiSumGhostIsMirrorUsum()` proves that the scalar ghost `sumDaiBalances` used by `daiSupplyIsSum`
  equals `usum address u. daiBalMirror[u]`. expr.html, "Ghost Mapping Sums", says that for a `usum`
  the solver assumes the sum is "even larger than the sum of any finite subset of values".

**The rule.** `daiPairwiseBalanceBound(a, b)` assumes, via `requireInvariant`, `daiSupplyIsSum`,
`daiSumGhostIsMirrorUsum`, and `daiMirrorMatchesBalance` for a and for b. All of these are proven
over Dai's constructor and every Dai method in the same run. Its only bare `require` is the
property's own hypothesis, `a != b`. It then asserts
`balanceOf(a) + balanceOf(b) <= totalSupply()`.

**Two findings from iteration 1** (run 61dbf89d, https://prover.certora.com/orgs/certora/jobs/61dbf89d-e065-4be5-84f0-6bc0253985a9/report):
1. The prover keeps a `usum` as its own term, connected to the mapping entries only through writes.
   In that run, the base case had every entry at 0 but the usum at 1. The fix is a second
   `init_state` axiom, `usum == 0`. This is sound: it is the sum of the all-zero initial mapping
   that the first axiom states.
2. The hook writes `mirror[a] = newBal`, so the usum moves by `newBal - mirror[a]`. That equals the
   scalar's move only when the mirror matched storage before the write. So `daiSumGhostIsMirrorUsum`
   has per-method preserved blocks (transfer, transferFrom, push, pull, move, mint, burn). Each one
   `requireInvariant daiMirrorMatchesBalance(x)` for every account x the method writes. These are
   proven invariants, so the blocks contain no bare `require`.

### third_parties_cannot_revoke_sdai_setup

**Rule.** `thirdPartiesCannotRevokeSdaiSetup(f, e, args, sdai, join, potAddr)` is parametric over
every entry point of Vat, Dai, Pot and DaiJoin. The brief asked for Vat and Dai; Pot and DaiJoin
were added because they call into the Vat and Dai as `msg.sender`, and the pass-3 commentary only
argued that part. `sdai`, `join` and `potAddr` are arbitrary addresses. The rule asserts three
things:
- `can(sdai, join) == 1` is preserved.
- `can(sdai, potAddr) == 1` is preserved.
- `allowance(sdai, join) == max` is preserved.

It is VERIFIED for every method, including `Dai.permit`, `Dai.transferFrom`/`burn`/`move`/`pull`
(no decrement at max allowance), `Vat.nope`, and `DaiJoin.join` (which burns from the caller).
scene.spec is imported only for the `Pot._rpow => rpowG` summary that every spec uses. Its wildcard
UNRESOLVED entries are reported unused.

**Assumptions** (both are bare requires and are commented in the spec):
1. `e.msg.sender != sdai`. This is the criterion-4 carve-out. Calls made by sDAI are exactly the
   calls SavingsDai's own methods make (sDAI has no other code path). maker-integration's
   `setupApprovalsPreserved` already covers those, for every SavingsDai method and any caller.
   Without this assumption the property is false, because `Vat.nope` or `Dai.approve` called by
   sdai revokes the setup.
2. **K: sdai has no ECDSA key.** It is stated as
   `forall h, v, r, s. ecrecover(h, v, r, s) != sdai` (CVL function `requireNoEcdsaKey`).
   - *Is the permit route reachable in the model?* Yes. expr.html, "ECRecover", says the prover's
     ecrecover is one uninterpreted ghost function, the same in contract code and in CVL.
     `permitBySdaiReachableWithoutKeyAssumption` is SATISFIED: without K, a third party calls
     `Dai.permit(holder = sdai, spender = join, allowed = false, ...)` and drives
     `allowance(sdai, join)` from max to 0. K is therefore load-bearing.
   - *Is it reachable on mainnet?* Not a finding. sDAI is a contract, and its address is
     `keccak256(rlp(deployer, nonce))[12:]`. A private key whose address equals it is unknown to
     anyone except with negligible (~2^-160 per attempt) probability. Keys mapping to that address
     almost certainly exist (~2^96 of them), but no party can find one, so no party can produce a
     valid signature for sDAI: K is a computational (cryptographic) assumption, like keccak
     collision resistance, not a mathematical fact. K is stated for the address `sdai` only. It is false for an EOA, which can of
     course revoke its own allowance via permit.
   - *How K is used.* K is a constraint on the ecrecover model, not a filter on `permit`. Under K,
     `permitBySdaiRevertsUnderKeyAssumption` is VERIFIED: every `permit` with `holder = sdai`
     reverts, whatever the caller and arguments, because of the code's own
     `holder == ecrecover(...)` check.

No `holder != sdai` filter is used, and no method is excluded.

### Which maker-integration preconditions are now fully discharged

| Precondition (maker-integration.spec) | Status after pass 4 | Evidence |
|---|---|---|
| `pre_daiSupplyCoversHolders(caller)` | **Fully discharged, machine-checked.** For `caller == sDAI` it is `daiBalanceAtMostSupply(sDAI)`. For `caller != sDAI` it is `daiPairwiseBalanceBound(caller, sDAI)`. Both hold in every Dai state reachable from Dai's constructor. | dai run b722fc7e |
| `pre_hopeDaiJoin` (`vat.can(sDAI, DaiJoin) == 1`) | **Fully discharged, modulo the named assumptions A1, A2, K.** | constructor run e81898a8, maker-integration run d239cba6, setup run 2047f9f4 |
| `pre_hopePot` (`vat.can(sDAI, Pot) == 1`) | **Fully discharged, modulo A1, A2, K** and base.conf's `SavingsDai:pot=Pot` (the scene deployment). | same |
| `pre_daiJoinAllowance` (`Dai.allowance(sDAI, DaiJoin) == max`) | **Fully discharged, modulo A1, A2, K.** | same |

The hope/allowance preconditions are proven by induction over any interleaving of calls:
- **Base:** `constructorWiresMakerSystem` proves the SavingsDai constructor establishes them.
- **Step, any SavingsDai method:** `setupApprovalsPreserved`.
- **Step, any Vat/Dai/Pot/DaiJoin entry point called by an account other than sDAI:**
  `thirdPartiesCannotRevokeSdaiSetup`, which is stated for arbitrary addresses and so in particular
  for sDAI, DaiJoin and Pot.

`Vat.can` and `Dai.allowance` are written only by Vat and Dai code, and every entry point of
the scene's Vat and Dai is covered. The scene's Vat is reduced (harnesses/Vat.sol); by inspection
of dss vat.sol, the omitted functions (init, file, cage, slip, flux, frob, fork, grab, fold) do
not write `can`, which only hope/nope write. That part is argued, not machine-checked. These steps therefore cover every transaction in the scene. Combining the three
results into one induction is a short meta-argument; the prover does not check that combination
itself.

The remaining trust is:
- A1 and A2 (the deployment is consistent);
- K (cryptographic);
- the `msg.sender != sDAI` carve-out, which is discharged by `setupApprovalsPreserved`.

The "what remains argued" paragraph of the pass-3 section is superseded.

### Files (pass 4)

- `certora/specs/maker-models/dai-invariants.spec`: new mirror ghost, 2 auxiliary invariants and
  `daiPairwiseBalanceBound`.
- `certora/specs/maker-models/setup-third-party.spec`: new.
- `certora/confs/maker-models-setup.conf`: new.
- `certora/confs/maker-models-dai.conf`: `msg` only.
- Logs: `certora/logs/maker-models-dai_pass4_run{1,2}.log` and `maker-models-setup_run1.log`.

### Pass 4 barrier re-runs and judge
scene.spec switched `isValidSignature` from NONDET to the deterministic `isValidSigG` ghost. Re-runs (full, unfiltered, rule_sanity basic, all VERIFIED):
- maker-models-setup: https://prover.certora.com/orgs/certora/jobs/aee23f05-e783-4935-a7da-8b1fbbc1dac5/report (current run for thirdPartiesCannotRevokeSdaiSetup and the K rules; the isValidSignature summary is unused there)
- maker-models-pot: https://prover.certora.com/orgs/certora/jobs/468e84d5-0925-4f4f-a638-c0001ca6e5e8/report
- maker-models-constructor: https://prover.certora.com/orgs/certora/jobs/b472def2-b105-4d09-b8f3-56f4e044bb89/report
- maker-integration (setupApprovalsPreserved 40/40): https://prover.certora.com/orgs/certora/jobs/f453c3ce-64dc-4550-af5a-30149a0728fe/report
- maker-models-dai does not import scene.spec; b722fc7e stands.

Judge pass 4 round 1: ACCEPT (maker-models.judge-pass4-round1.md). Its recommended wording fixes are applied: K is a computational assumption, the reduced-Vat coverage is stated as argued by inspection, and the Sload-hook comment in dai-invariants.spec is updated (comment only).
