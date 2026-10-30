# erc4626-vault — generator commentary (round 2)

- Spec: `certora/specs/erc4626-vault.spec`.
- Conf: `certora/confs/erc4626-vault.conf`. It is the only conf; a full run takes about 5 minutes, so no split was
  needed. `certora/confs/erc4626-vault_tc.conf` is the same conf plus `compilation_steps_only` (typecheck only).
- The overlay on `SavingsDai.conf`: `verify` = this spec, `parametric_contracts: ["SavingsDai"]`, `optimistic_loop`,
  `rule_sanity: basic`, `wait_for_results: none`, `msg`. No rule filter.
- Mapping: `certora/properties/erc4626-vault.property_rules.json`. All 14 properties are formalized; none is skipped.

## Runs
| Tag | Job | Result |
|---|---|---|
| erc4626_iter1 | 706b493b-818c-4509-b9ce-ed0e0f7aae88 | 4 violated: maxDepositAccepted, maxMintAccepted (genuine, see below); withdrawEffectsExact, mintThenWithdrawNoProfit (spurious chi == 0 prestate) |
| erc4626_iter2 | 25b859d6-9e44-44b9-95ac-7111f1caac64 | about 6.3 min. Every rule VERIFIED (all parametric instances, the then-copied invariants and a local chiAtLeastRay, envfreeFuncsStaticCheck) except maxDepositAccepted and maxMintAccepted (VIOLATED, expected: genuine issue) |
| erc4626_iter3 (final) | 59ab9ca6-d468-4b07-8b67-604dcf1ed984 | about 4.5 min, unfiltered, rule_sanity basic. Every rule VERIFIED (all parametric instances, maxDepositAlwaysReverts, maxMintAlwaysReverts, satisfy witness actionDripBranchReachable, envfreeFuncsStaticCheck) except maxDepositAccepted and maxMintAccepted (VIOLATED, expected: genuine issue). Imported invariants are not re-checked in this conf. |

Report links: `https://app.certora.com/orgs/certora/jobs/<job>/report`.

## Invariants used
The spec is `import "invariants.spec";` plus four local envfree methods entries (PotHarness.rho/dsr,
DaiMock.balanceOf, maxRedeem). All requireInvariant's refer to invariants.spec, proven over all five scene contracts:
judge-accepted job 3c95349d-c8a0-4655-ad5a-4285034a5ed9, and chiAtLeastRay (`chi >= RAY`, added at the round-1
barrier on this component's request) in job 1080ee77-78e7-4afb-bb57-8a5da4e46a62. chiAtLeastRay excludes iter1's
spurious `chi == 0` prestates (withdrawEffectsExact's ceilDiv by zero; mint at chi = 0 charging 0 DAI).

`potVatDaiCoversSavings` and `daiJoinVatDaiCoversDaiSupply` are proven under trusted governance (top-level caller
not a Maker ward, not sDAI/Pot/DaiJoin) and with `PotHarness.setYield` (mock-only) never called. The liveness rules
rely on them through `requireInvariant`; that is the trust assumption they inherit.

## Rules per property
- **deposit/mint/withdraw/redeem_effects_exact** — `depositEffectsExact`, `mintEffectsExact`,
  `withdrawEffectsExact`, `redeemEffectsExact`. The expected amount is computed in CVL from `potHarness.chi()` read
  AFTER the call (post-drip chi): floor(a*RAY/chi), ceil(s*chi/RAY), ceil(a*RAY/chi), floor(s*chi/RAY). Each rule
  asserts the return value, the DAI delta of the payer/receiver, that an arbitrary other DAI holder is unchanged
  (for deposit/mint this includes sDAI's own DAI balance), the share delta of receiver/owner, that an arbitrary
  other share holder is unchanged, and the totalSupply and `pot.pie(sDAI)` deltas. receiver/owner/caller are free,
  so receiver == caller, owner == receiver, owner != caller (allowance path) are all covered by the one rule.
  deposit and mint cover both overloads (`withReferral` flag).
- **rounding_favors_vault** — `vaultVatDaiNeverDecreases`: parametric over every SavingsDai method,
  `vat.dai(sDAI)` does not decrease. For the four actions this is exactly `shares*chi <= assets*RAY` on entry and
  `>=` on exit, because the Vat moves are `+RAY*assets, -chi*shares` (entry) and `+chi*shares, -RAY*assets` (exit).
- **round_trip_no_profit** — `depositThenRedeemNoProfit` (redeem the minted shares returns <= assets) and
  `mintThenWithdrawNoProfit` (withdraw the DAI paid burns >= shares). Two envs with the same timestamp; the second
  call's caller is free (needs allowance when it is not the share owner).
- **preview_matches_action** — four rules `previewXMatchesX`, same env and state, any elapsed time since the last
  drip (both views and Pot.drip use the one uninterpreted rpowG). deposit/mint include both overloads.
- **actions_price_at_accrued_rate** — `actionsDripToCurrentBlock` (parametric over the 6 action methods): after the
  call `rho == now` (stated as `rhoBefore <= now => rho == now`, so no assumption about time monotonicity is
  needed), and `chi_after == rpowG(dsr, now - rho) * chi_before / RAY` when `now > rho`, else unchanged. The amount
  half ("computed with the post-drip chi") is the four *EffectsExact rules.
- **third_party_value_unaffected** — `thirdPartyValueUnaffected`: parametric over every SavingsDai method through
  `callWithParties`, which passes the rule's `receiver`/`owner` to every method that names a share receiver or
  owner (deposit x2, mint x2, withdraw, redeem, transfer, transferFrom); the rest run with arbitrary calldata.
  For `u` not caller/receiver/owner: `balanceOf(u)` and `convertToAssets(balanceOf(u))` (same env) unchanged.
- **share_price_independent_of_donations** — `daiDonationDoesNotMovePrice` (`daiMock.transfer` to sDAI),
  `vatDaiDonationDoesNotMovePrice` (`vatMock.move(src, sDAI, rad)`), `daiJoinDonationDoesNotMovePrice`
  (`daiJoinMock.join(sDAI, wad)`); `convertToShares`, `convertToAssets` and `totalAssets` unchanged (same env).
  The donor env is free (any block): the share price depends only on the Pot's chi/rho/dsr.
- **share_price_never_decreases** — `chiNeverDecreases`: with `dsr >= RAY` (stated by the property), chi does not
  decrease across any SavingsDai method.
- **deposit_pulls_only_from_caller** — `onlyCallerDaiDecreases`: parametric; DAI balance of any `u != caller`
  does not decrease. `u == savingsDai` is deliberately included: deposit/mint route DAI through sDAI's balance
  (transferFrom in, DaiJoin burns it), so the rule also proves sDAI's own DAI never drops.
- **redeem_always_possible** — `redeemAlwaysPossible`: holder (caller == owner) redeems any `shares <= balance`.
- **max_functions_accurate** — `maxRedeemIsBalance`, `maxRedeemSucceeds`, `maxWithdrawSucceeds` (succeeds and the
  returned burned shares <= balance), `maxDepositAccepted`, `maxMintAccepted` (expected-fail, genuine), and the
  precondition-free witnesses `maxDepositAlwaysReverts` (no requires) and `maxMintAlwaysReverts` (only
  requireInvariant chiAtLeastRay): deposit/mint of the advertised maximum revert in every state.
- `actionDripBranchReachable` (satisfy): the `now > rho` drip branch of an action (redeem) is reachable with rho
  ending at `now`, so actionsDripToCurrentBlock is not vacuous on that branch.

## Every bare require and its justification
Effects / other rules:
- `other != receiver` / `other != owner`, `daiOther != caller` / `daiOther != receiver`: these only name the
  "third account" the rule checks; they do not restrict the call.
- `e2.block.timestamp == e1.block.timestamp` (round trip): the property is "within one block".
- `u != caller && u != receiver && u != owner` (third party): definition of a third party.
- `u != e.msg.sender` (deposit pulls): definition of "other than the caller".
- `dsr >= RAY` (chiNeverDecreases): stated by the property itself.

Liveness (redeemAlwaysPossible, maxRedeemSucceeds, maxWithdrawSucceeds) — `requireSoundMakerSystem`,
`requireDripNoOverflow`, `requireExitNoOverflow`, `requireValidExit`:
- `e.msg.value == 0`: redeem/withdraw are non-payable (a value-carrying call reverts by design).
- `receiver != 0 && receiver != daiMock`: Dai.mint rejects both (the property says "valid receiver").
- `shares <= balanceOf(owner)` (redeemAlwaysPossible): the property's `b' <= b`.
- `vatMock.wards[potHarness] == 1`: Maker deployment fact (drip calls the auth `vat.suck`); only trusted
  governance could deny it.
- `daiMock.wards[daiJoinMock] == 1`: Maker deployment fact (DaiJoin.exit calls the auth `dai.mint`); only trusted
  governance could deny it.
- `dsr >= RAY`: trusted governance. With dsr < RAY even mainnet Pot.drip reverts at the checked `tmp - chi`, so this
  is a Pot-level liveness condition, not an sDAI one. `Pot.cage()` sets dsr = RAY, so caged Pots satisfy it.
- Rate accumulation does not overflow (only when `now > rho`): `rpowG(dsr, now-rho) * chi <= max_uint256` and
  `Pie * (chi' - chi) <= max_uint256`. The rpow summary drops the real rpow's overflow reverts (rpow_summary.spec
  header), so this must be an explicit assumption, as the property states.
- Vat accounting does not overflow: `vat.suck` credits (`dai[pot]`, `sin[vow]`, `vice`, `debt` + `Pie*(chi'-chi)`),
  `pot.exit` credit `dai[sDAI] + chi'*shares`, `daiJoin.exit` credit `dai[daiJoin] + RAY*assets`. These are the
  "Vat/Dai sums not overflowing" Maker assumptions (in Maker, sum of dai == debt <= max_uint256). The Dai side
  needs no assumption: `Dai.totalSupply + assets` is bounded by `daiJoinVatDaiCoversDaiSupply` plus the DaiJoin
  credit bound.
- No caller restriction, no `live` restriction: the rule covers caged Pots/Vats (nothing on the exit path checks
  `live`), and any caller.
- requireInvariant (proven): totalSupplyEqualsSumOfBalances, sharesEqualPotPie, potTotalPieEqualsSumOfPie,
  potTotalPieCoversSdaiPie, daiTotalSupplyEqualsSumOfDaiBalances, sdaiSetupPermissionsPersist (sDAI's Vat hope for
  DaiJoin), potVatDaiCoversSavings (Pot can pay chi*shares), daiJoinVatDaiCoversDaiSupply.

maxDepositAccepted / maxMintAccepted — `requireCanEnter`:
- `msg.value == 0`, `receiver != 0 && receiver != sDAI` (sDAI._mint rejects both), `caller != sDAI` (sDAI never
  originates a call).
- Caller DAI balance >= amount and allowance to sDAI == max: ERC-4626 says maxDeposit/maxMint assume the user has
  unlimited assets. The DAI-supply invariants are deliberately NOT required here: with them, a balance of
  2^256-1 is infeasible and the rule would be vacuous.
- `rho <= now`: rho is only ever written with `block.timestamp` (Pot constructor, drip, setYield) and time is
  monotone; Pot.join requires `now == rho` after the drip.
- `vat.wards[pot] == 1`, `dsr >= RAY`, drip no-overflow: as above. `requireInvariant chiAtLeastRay` (invariants.spec),
  `sdaiSetupPermissionsPersist`.

## Expected failures
- **maxDepositAccepted — genuine issue.** `maxDeposit` returns `type(uint256).max`, but `deposit(assets, r)` first
  computes `assets * RAY` with checked arithmetic, so `deposit(maxDeposit(r), r)` reverts for every state and every
  caller (any `assets > (2^256-1)/1e27`, about 1.16e50 wei, overflows). CEX (iter1): `maxDeposit(r) = MAX_UINT256`,
  caller holds and approved MAX_UINT256 DAI, `now == rho` (no drip), chi >= RAY; `deposit(MAX_UINT256, r)` reverts
  right after reading chi, at the `assets * RAY` multiplication. Precondition-independent evidence:
  `maxDepositAlwaysReverts` (VERIFIED, no requires) proves `deposit(maxDeposit(r), r)` reverts in every state. ERC-4626 requires maxDeposit not to exceed what
  deposit accepts. Impact: integrators that call `deposit(maxDeposit(..))` or use maxDeposit as a cap revert; no
  funds at risk.
- **maxMintAccepted — genuine issue.** Same for `maxMint` = `type(uint256).max`: `mint(shares, r)` computes
  `shares * chi` (checked), and chi >= RAY > 1, so `mint(MAX_UINT256, r)` always reverts. CEX: `now == rho`,
  chi >= RAY; revert right after reading chi, at `shares * chi`. Evidence: `maxMintAlwaysReverts` (VERIFIED, only
  requireInvariant chiAtLeastRay) proves `mint(maxMint(r), r)` reverts in every state with chi >= RAY.

## Summaries
- Only the shared ones: `rpow_summary.spec` (one uninterpreted rpowG for sDAI._rpow and Pot._rpow; this is what makes
  previews match actions for any elapsed time), base summaries (none), call resolution (links). The imported
  invariants.spec contains its constructor-only UNRESOLVED wildcard entries. Nothing is NONDET.
- Unresolved calls in the report: only the ERC-1271 `signer.staticcall(isValidSignature)` in sDAI/Dai permit. A
  staticcall cannot change state; no rule here depends on permit's success.
