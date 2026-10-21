VERDICT: ACCEPT

Judge: maker-integration, pass 2, round 1. Reviewed `certora/specs/maker-integration.spec`, the conf, `scene.spec`, `invariants.spec`, `SavingsDai.sol`, the Pot/Vat/DaiJoin/Dai harnesses, the properties/commentary files, and both prover outputs. I downloaded and inspected:
- the final run d239cba6: every non-probe rule has a `rule_not_vacuous` witness, and the probe has a CEX trace;
- the minimality run 355dfa44: 59 `ctpp_min{D,R,W}_*` violation traces, one for each dropped precondition. This confirms the claim that all 59 drop-one variants were VIOLATED.

## 1. Code smells
None blocking.
- Every bare `require` is a named `pre_*` liveness precondition, and each one is on the call path of a `@withrevert` call. No require only prevents reverts of a non-`@withrevert` call: the two parametric rules call `f(e, args)` with no requires at all.
- Every methods-block entry is used (`Vat.sin/vice/debt/wards`, `Pot.vow/Pie`, `Dai.wards/allowance/totalSupply`, `DaiJoin.live`, ...).
- No assertion is tautological.
- `pre_noEther` is needed in a liveness rule, because a non-payable function reverts when sent ETH.

## 2. Guideline compliance
Compliant.
- Types: `uint256` is used for call arguments and results, `mathint` for derived quantities, `assert_uint256` for the elapsed time inside the guarded branch, and `RAY()` is a definition.
- Every CVL function ends with `return`.
- `ownerCanWithdrawMax` uses the return value of `maxWithdraw@withrevert` (guideline 16). This is acceptable because the rule also asserts `!maxReverted`, so any trace where that value is undefined already fails the rule.

## 3. Precondition validity
- The redeem/withdraw rules use `requireInvariant` on the three proven structural invariants. These give `balance(owner) <= totalSupply <= pie[sDAI]`, which `Pot.exit` needs.
- The deposit rule needs none of them, which is correct.
- Rule sanity passed, but the `ownerCanRedeemAll` witness has `shares = 0`. I checked non-triviality by hand. One state that meets every precondition is: dsr = chi = rpowG = RAY, pie[sDAI] = Pie = totalSupply = balance = 1, vat.dai(pot) = RAY, and the overflow bounds slack. Separately, the probe's CEX is a state with shares = 1 that meets every precondition except dsr. So none of the verified liveness rules is vacuously restricted to zero balances.

## 4. Overconstrained inputs
I checked each precondition against the dss code and the mainnet deployment.
- **P_rpowMonotone** (`dsr >= RAY => rpowG(dsr, n, RAY) >= RAY`) is true of the real `_rpow`:
  - z starts at RAY (n even) or at x (n odd), both >= RAY.
  - Each squaring gives `floor((x*x + RAY/2)/RAY) >= floor(x*x/RAY) >= x >= RAY`, and each multiply gives `floor((z*x + RAY/2)/RAY) >= z >= RAY`.
  - When n = 0 the result is RAY.
  - The precondition is vacuous when dsr < RAY, so keeping it in the probe is correct.
- **P_potSolvent** (`vat.dai(pot) >= chi * pie[sDAI]`, with the pre-drip chi) is weaker than the real Pot invariant `vat.dai(pot) >= chi * Pie`, and drip's suck closes the gap: `Pie*dchi >= pie[sDAI]*dchi` given P_PieCoversSdaiPie and dchi >= 0. Realistic.
- **P_daiBacked / P_daiSupplyCoversHolders** hold on mainnet and are checkable on-chain:
  - DaiJoin is the only DAI ward, and exit/join lock and release exactly RAY*wad, which gives the backing.
  - totalSupply is the sum of balances.
- **P_hopeDaiJoin / P_hopePot / P_daiJoinAllowance** are set by the visible constructor. `setupApprovalsPreserved` proves they are preserved. Only the base case rests on reading the constructor, because the scene NONDETs it. This is documented.
- **The overflow bounds** match one checked operation each and are many orders of magnitude below 2^256 on mainnet.
- **The rules are not over-restricted.** The exit rules leave out now >= rho and chi >= RAY, which is more general than needed, and the minimality run shows each remaining precondition is necessary. The deposit rule leaves out `DaiJoin.live`, which is correct because `DaiJoin.join` does not check it.
- Nothing excludes realistic states or makes a rule trivial.

## 5. Trivializing summaries
None introduced by this spec.
- The inherited scene trust assumption is that `rpowG` never reverts, while the real `_rpow` reverts on intermediate overflow. For liveness rules this assumption can hide reverts.
- In realistic states (chi >= RAY) this is harmless. `pre_dripNoOverflow` bounds rpow*chi <= max, which gives RAY*rpow <= max, and every intermediate of the real `_rpow` is about RAY times a value no larger than the final result.
- The exit rules do not require chi >= RAY, so the gap remains only in unrealistic states where chi < RAY.
- The commentary documents this. It is not blocking (see the optional suggestion below).

## 6. Manifest errors
None. I verified that the finding is genuine:
- **The scenario holds for every dsr < RAY, not just the CEX value.** For dsr < RAY and n >= 1, the real `_rpow(dsr, n)` is below RAY: squaring and multiplying by values below RAY never increases the value, and dsr = 0 gives 0. So `rmul(rpow, chi) < chi` for any chi > 0, and drip's checked `tmp - chi` underflows. Every deposit, mint, withdraw and redeem then reverts once now > rho.
- **Governance cannot repair dsr through `file`.** `file("dsr")` requires `block.timestamp == rho`. Only `drip` updates rho, and drip reverts. When now == rho, drip with n = 0 succeeds, but rho is already in the past in every later block. `Pot.cage` resets dsr to RAY but sets live = 0 permanently. sDAI's `pot` is immutable.
- **The contrast with direct Pot users is correct.** `Pot.exit` has no rho check, and `DaiJoin.exit` does not depend on drip.
- **The probe is well-formed.** It is the verified redeem rule minus one precondition, and VERIFIED means the good property holds.

## 7. Meaningful contract interaction
- Every assertion is on `lastReverted` of a real SavingsDai call, or on Vat/Dai storage read after a SavingsDai method.
- `vaultNeverPaysRoundingFromOwnVatBalance` has no preconditions, no filter, and covers 40 of 40 methods. It genuinely depends on the floor/ceil rounding in deposit/mint/withdraw/redeem.
- `setupApprovalsPreserved` reads `Vat.can` and `Dai.allowance` before and after every SavingsDai method (40 of 40). Restricting it to SavingsDai methods is complete for "no SavingsDai method revokes":
  - only sDAI can call `Vat.nope` or `Dai.approve` as sDAI;
  - `Dai.transferFrom` and `Dai.burn` never decrement a max allowance.
- Neither parametric rule has a hidden filter.

## 8. Property coverage
All 5 properties are formalized, and none is skipped:
- `setup_approvals_preserved`
- `owner_can_always_redeem` (both redeem-all and withdraw-max)
- `redeem_does_not_depend_on_drip` (probe, marked expected-to-fail as a finding)
- `deposit_liveness`
- `vault_never_pays_rounding_from_own_vat_balance`

## Non-blocking notes (no resubmission required)
1. **The CEX details in the commentary and in `_expected_fail.detail` do not match the trace in run d239cba6.**
   - The commentary says rho = 5, now = 6 and `rpow(dsr, 1) < RAY`. The downloaded trace has rho = 4, `rpowG(0.5 RAY, 3, RAY) = 1` (so now = 7), and an unrealistic chi of about 2.4e55.
   - The ghost value 1 is not what the real `_rpow` returns (0.125 RAY), although any value below RAY gives the same revert.
   - Fix: correct the numbers, and say the conclusion holds for the real `_rpow` (see section 6).
2. **Optional: close the inherited `rpowG`-never-reverts gap for the liveness rules.** Add a named precondition that the real `_rpow` does not overflow, for example `RAY() * dripFactor(e) + RAY()/2 <= max_uint256` when now > rho. Alternatively, add `pre_chiAtLeastRay` to the exit rules and say so in the commentary.
3. **Severity of the finding.** The finding should keep stating that it is triggered only by governance (Pot.file with dsr < RAY) and that the only recovery is a permanent `Pot.cage`.
