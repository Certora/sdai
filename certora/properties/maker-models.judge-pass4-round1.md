VERDICT: ACCEPT

# maker-models, judge pass 4 round 1

Scope: the pass-4 additions only.
- Properties `third_parties_cannot_revoke_sdai_setup` and `dai_pairwise_balance_bound`.
- `specs/maker-models/dai-invariants.spec`: `daiBalMirror`, `daiMirrorMatchesBalance`, `daiSumGhostIsMirrorUsum`, `daiPairwiseBalanceBound`.
- New `specs/maker-models/setup-third-party.spec` and `confs/maker-models-setup.conf`.
- The downstream discharge claims in `maker-models.commentary.md` "Pass 4" against `specs/maker-integration.spec`.

Also read: scene.spec (current version, with isValidSignature as a deterministic ghost), harnesses/Vat.sol, maker-integration.conf and property_rules, and the logs maker-models-setup_{run1,pass4_barrier}.log, maker-models-dai_pass4_run2.log and maker-integration_pass4_barrier.log.

Run evidence I checked myself (downloaded treeViewStatus):
- **Dai, b722fc7e-703d-4dda-98f5-50c1500e23ef.** Base case plus all 11 Dai methods are VERIFIED for `daiSupplyIsSum`, `daiBalanceAtMostSupply` and `daiMirrorMatchesBalance`. `daiSumGhostIsMirrorUsum` is VERIFIED: 7 methods under their specific preserved blocks, and approve, permit, rely and deny under the general requirements. `daiPairwiseBalanceBound` is VERIFIED. Every `invariant_not_trivial_postcondition` / `rule_not_vacuous` sanity check passes.
- **Setup, 2047f9f4-334e-46fc-80d1-c76809d44b2c.** `thirdPartiesCannotRevokeSdaiSetup` is VERIFIED on all 62 entry points: Vat 14, Dai 22 (including permit), Pot 17, DaiJoin 9. Each entry point has a passing `rule_not_vacuous`. `permitBySdaiRevertsUnderKeyAssumption` is VERIFIED, with its sanity check passing. `permitBySdaiReachableWithoutKeyAssumption` is SATISFIED. The log shows the `_.hope`, `_.approve`, `_.vat`, `_.dai` and `_.isValidSignature` wildcard summaries as unused.
- **Re-run with the new scene.spec, aee23f05-e783-4935-a7da-8b1fbbc1dac5 (logs/maker-models-setup_pass4_barrier.log).** All rules and every sub-check are VERIFIED. That is 191 tree nodes for the parametric rule, plus 3 for the permit-revert rule and 3 for the witness, with all sanity passing. `_.isValidSignature` is again reported unused.
- **maker-integration re-run with the new scene, f453c3ce-64dc-4550-af5a-30149a0728fe (logs/maker-integration_pass4_barrier.log).** `setupApprovalsPreserved` is VERIFIED on 40 of 40 SavingsDai methods, including both permit overloads.

## 1. Code smells

No blocking findings.
- **Methods blocks.** Each methods-block entry (`Vat.can` and `Dai.allowance` envfree in the setup spec; `totalSupply` and `balanceOf` in the Dai spec) is used.
- **Asserts.** None are tautological. Each assert reads contract storage before and after a real call, or, in the pairwise rule, reads both balances and the supply. Sanity confirms none of the asserts holds trivially.
- **`init_state axiom (usum address a. daiBalMirror[a]) == 0`.** This is not redundant. Run 61dbf89d showed that the prover treats the usum as a separate term. It is also sound, because it is the sum of the all-zero mapping given by the first axiom.
- **Unused imports in the setup spec (remark).** Only `Pot._rpow => rpowG` is needed from scene.spec. The other entries are unused here, as the log confirms. This is harmless.

## 2. Guideline compliance

Compliant.
- **G13 (quantifier bodies).** `requireNoEcdsaKey` quantifies over `ecrecover(h, v, r, s)`. That is the CVL built-in, not a contract call. G13 is therefore respected.
- **G14 (CVL functions end in `return`).** The CVL function ends with `return;`.
- **G12 (`method` variables).** `method f` is a rule parameter.
- **G23 (ghost plus hook).** `daiBalMirror` is justified under G23: `usum` is defined only over ghost mappings (expr.html "Ghost Mapping Sums"), so the balance mapping cannot be summed directly.
- **G18 (preserved blocks).** The preserved blocks of `daiSumGhostIsMirrorUsum` contain only `requireInvariant daiMirrorMatchesBalance(...)`. That invariant is proven independently with no preserved block, so there is no circularity. The preserved blocks cover exactly the 7 Dai methods that write `balanceOf`. Methods without a block, such as approve, permit, rely and deny, still verify under the general requirements. So the blocks can only add proven facts and cannot hide a method.

## 3. Precondition validity (every bare require / assumption)

### setup-third-party.spec

- **`require e.msg.sender != sdai` (thirdPartiesCannotRevokeSdaiSetup): valid under the checklist carve-out.**
  - SavingsDai is part of the application but not of this verification task, which runs the Vat as main contract with Vat/Dai/Pot/DaiJoin as parametric contracts.
  - The carve-out's obligation is discharged by `setupApprovalsPreserved` in SavingsDai's own spec. It is parametric over every SavingsDai method, with an arbitrary caller and pre-state and no preconditions. It was re-verified under the current scene in f453c3ce.
  - Calls with `msg.sender == sDAI` can only originate from SavingsDai's code. The ways that could fail:
    - SavingsDai has no delegatecall.
    - SavingsDai has no selfdestruct or CREATE2 redeploy path.
    - An EIP-7702 delegation needs sDAI's key, which is excluded by K.
  - The only external call SavingsDai makes to arbitrary code is the ERC-1271 `isValidSignature`, which is a staticcall and cannot write `Vat.can` or `Dai.allowance`. Vat, Dai, Pot and DaiJoin never call back into SavingsDai or into arbitrary code.
  - So every transaction decomposes into atomic top-level calls to SavingsDai, which `setupApprovalsPreserved` covers, and calls to Vat/Dai/Pot/DaiJoin from accounts other than sDAI, which this rule covers.
  - The guard is on the top-level `e.msg.sender` only. Nested calls whose `msg.sender` is Pot or DaiJoin are still checked even when `sdai` aliases Pot or DaiJoin. This makes the rule stronger, not weaker.
- **K, `forall h, v, r, s. ecrecover(h, v, r, s) != sdai`: accepted as a standard cryptographic modeling assumption.**
  - It is the same kind of assumption as "keccak has no collisions" or "nobody holds the key of a CREATE-derived address".
  - It is load-bearing in the model. Without it, the witness rule shows that a third party can zero sDAI's allowance to DaiJoin through `Dai.permit`.
  - It constrains the ecrecover model, not the code paths. permit is not filtered out, and `permitBySdaiRevertsUnderKeyAssumption` shows that the code's own `holder == ecrecover(...)` check is what blocks the route.
  - K is not over-strong, for two reasons. First, the per-method `rule_not_vacuous` check on `Dai.permit` passes under K, so a non-reverting permit (for a holder other than sdai) is still reachable. Second, K is consistent, since a constant ecrecover different from sdai is a model of it.
  - The CVL `ecrecover` is the same uninterpreted function as the precompile used by contract code. If it were not, `permitBySdaiRevertsUnderKeyAssumption` could not be VERIFIED.
  - **Wording remark (non-blocking).** K is a *computational* assumption, not a mathematical fact. There are about 2^256 secp256k1 keys spread over 2^160 addresses, so keys mapping to sDAI's address almost certainly exist (about 2^96 of them). What fails is that nobody can find one. Commentary "Pass 4", line ~253, says "so no valid signature for sDAI exists". It should say that no party can produce one, so K abstracts a 160-bit preimage search as impossible. The spec comment already phrases this correctly ("exists to anyone's knowledge").
  - K is required only for the SavingsDai address, which is created with CREATE (`keccak(rlp(deployer, nonce))`). That is the only instantiation the discharge uses, so stating K for an arbitrary `sdai` is fine.
- **`permitBySdaiReachableWithoutKeyAssumption`.** It has `require e.msg.sender != sdai` and `require allowance(sdai, join) == max`. These are satisfy-rule hypotheses that set up the witness scenario, and they are appropriate.
- **Arbitrary `sdai`, `join` and `potAddr`.** These are free rule parameters with no state constraints. The rule therefore holds for every triple, in particular for (SavingsDai, DaiJoin, Pot). Tying them to the scene contracts would only weaken the statement, so this choice is correct.

### dai-invariants.spec

- **`require a != b` in `daiPairwiseBalanceBound`.** This is the property's own hypothesis and is valid. Everything else in that rule is a `requireInvariant` of an invariant proven in the same run.
- **Pre-existing `hook Sload ... require sumDaiBalances >= bal` (non-blocking remark).**
  - This was accepted in pass 3 and is still semantically valid. In every reachable state, `sumDaiBalances` equals Σ balanceOf by construction: it starts at 0 and the Sstore hook applies every write, Dai has no assembly stores, and mathint does not wrap.
  - However, the comment "Used only by the corollary daiBalanceAtMostSupply" is now stale. The hook also fires on the `balanceOf` reads inside `daiMirrorMatchesBalance`, including its post-state, and inside `daiPairwiseBalanceBound`.
  - This does not affect soundness, for two reasons. The mirror invariant holds trivially through the Sstore hook. And the pairwise rule cannot get its two-balance bound from two single-balance bounds; it needs the usum fact.
  - The comment should be updated. Optionally, the hook-level require could now be dropped and `daiBalanceAtMostSupply` re-derived from the usum invariants, which would leave zero bare requires in this spec.

## 4. Property faithfulness

- **`dai_pairwise_balance_bound`: faithful.**
  - The rule asserts `balanceOf(a) + balanceOf(b) <= totalSupply()` for `a != b`. All of its premises are invariants proven from Dai's constructor over every Dai method.
  - The pairwise rule really depends on the usum semantics ("larger than the sum of any finite subset"), combined with mirror equals storage and scalar equals usum. Contract reads determine the verdict.
  - The statement is a direct rule, not an invariant, so "every reachable Dai state" holds by the standard requireInvariant argument.
- **`third_parties_cannot_revoke_sdai_setup`: faithful, and stronger than the description.**
  - It covers Pot and DaiJoin in addition to Vat and Dai, and it uses arbitrary addresses.
  - The description asked for any assumption about permit to be explicit. K is explicit, justified, and has a witness showing it is load-bearing.
- **Coverage.**
  - In the scene, `Vat.can` is written only by `hope` and `nope`. Both key on `msg.sender`, so with `msg.sender != sdai` they cannot touch `can[sdai][*]`.
  - `Dai.allowance[sdai][*]` is written by `approve` (keyed on msg.sender), by `permit` (holder, blocked by K), and by `transferFrom`/`burn`/`move`/`pull` (no decrement at max, as verified).
  - All of these entry points are in the parametric set. Pot and DaiJoin reach Vat and Dai only through linked calls with themselves as `msg.sender`, and those are verified too.
  - **Non-blocking remark.** harnesses/Vat.sol is a *reduced* Vat, with 14 entry points. Mainnet `init`, `file`, `cage`, `slip`, `flux`, `frob`, `fork`, `grab` and `fold` are omitted. In dss vat.sol, `can` is written only by `hope` and `nope`, so the omission does not affect this property. That is argued by inspection, though, not machine-checked.
  - Commentary "Pass 4" says "every Vat and Dai entry point is covered". It should qualify this as every entry point of the scene's Vat model, and add the one-line inspection argument for the omitted mainnet functions. Mainnet Dai, Pot and DaiJoin are fully represented.

## 5. Downstream discharge claims (maker-integration)

- **`pre_daiSupplyCoversHolders(caller)`: correctly discharged, with no A1, A2 or K needed.**
  - The precondition is `totalSupply >= bal(caller) + (caller != sDAI ? bal(sDAI) : 0)`.
  - For `caller == sDAI` it is `daiBalanceAtMostSupply(sDAI)`. For `caller != sDAI` it is `daiPairwiseBalanceBound(caller, sDAI)`.
  - Both hold in every Dai state reachable from Dai's constructor. Only Dai code writes Dai storage, and both are proven over all Dai methods.
  - The commentary states this correctly.
- **`pre_hopeDaiJoin`, `pre_hopePot` and `pre_daiJoinAllowance`: correctly discharged modulo A1, A2 and K.** For `pre_hopePot`, the `SavingsDai:pot=Pot` link is also needed, as the commentary says. The induction is:
  - **Base.** `constructorWiresMakerSystem` (e81898a8).
  - **SavingsDai steps.** `setupApprovalsPreserved`, now re-verified under the current scene in f453c3ce.
  - **Steps for all other transactions.** `thirdPartiesCannotRevokeSdaiSetup` (2047f9f4, re-verified in aee23f05), instantiated at (sDAI, DaiJoin, Pot).
  - **Decomposition.** This is sound because no scene contract re-enters SavingsDai or calls arbitrary code. The only exception is a staticcall, which cannot write state (section 3).
  - **Remaining trust.** The commentary honestly states that the prover does not check how the three results combine, and it lists the remaining trust as A1, A2, K and the carve-out. I agree.
  - **Missing caveat.** The commentary should add the reduced-Vat inspection argument from section 4.
- **Status bookkeeping (non-blocking).** `maker-models.property_rules.json` `_status` and the commentary still cite 2047f9f4 for the setup conf and d239cba6 for `setupApprovalsPreserved`. Both were re-run under the changed scene.spec, as aee23f05 and f453c3ce, with identical results. Record those as the current runs.

## scene.spec change (isValidSignature is now a deterministic ghost)

This has no effect on the pass-4 setup or Dai results.
- **setup-third-party.spec.** No scene contract reachable from it calls `isValidSignature`, because Dai.permit uses only ecrecover. Both runs report the summary as unused, and the re-run aee23f05 is identical (all VERIFIED, all sanity passing).
- **dai-invariants.spec.** It does not import scene.spec.
- **`setupApprovalsPreserved`.** The new ghost is side-effect-free, as an ERC-1271 staticcall is. The rule's result is unchanged: 40 of 40 VERIFIED in f453c3ce.

## Required changes

None blocking. Recommended wording and bookkeeping fixes:
1. In the commentary, change "no valid signature for sDAI exists" to "no party can produce one". K is a computational assumption.
2. Qualify "every Vat and Dai entry point is covered" as covering the scene's reduced Vat. Add that the omitted mainnet Vat functions do not write `can`, which is argued by inspection.
3. Update the stale Sload-hook comment in dai-invariants.spec ("Used only by the corollary"). Optionally, remove the hook require in favour of the usum invariants.
4. Record runs aee23f05 (setup) and f453c3ce (`setupApprovalsPreserved`) as the current evidence under the changed scene.spec.
