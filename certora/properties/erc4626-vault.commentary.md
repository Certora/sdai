# erc4626-vault — commentary (round 1)

Round-1 full unfiltered run (iter 2, rule_sanity basic): https://prover.certora.com/orgs/certora/jobs/3b0aeea4-5664-41bf-a0a7-77b25258d6a1/report — every rule VERIFIED (22 rules incl. envfree static check; all `rule_not_vacuous` sanity children pass).
Iter 1: https://prover.certora.com/orgs/certora/jobs/9f4bb394-0475-4262-a35a-fa3edcc4e00c/report — 3 spurious violations (see below).

## Setup
- Spec `certora/specs/erc4626-vault.spec` imports the standard four files; adds `using DaiMock as daiToken`. Conf = invariants.conf with verify/msg changed; no extra prover_args needed (nonlinear rules solved within default timeouts).
- No new summaries. The scene's `rpowG` ghost function (scene.spec) summarizes both `SavingsDai._rpow` and `Pot._rpow`, so view-side chi estimates and `Pot.drip` agree exactly. Rules compute the expected chi independently from the Pot pre-state via `expectedChi(e)` = `now > rho ? rpowG(dsr, now - rho, RAY) * chi / RAY : chi` and assert that the post-state `pot.chi()` (the chi the operation used) equals it.
- Accounting/attack rules `requireInvariant` the three proven invariants (totalSupplyIsSumOfBalances, sharesBackedByPie, zeroAndSelfHoldNoShares) so the unchecked `_mint`/`_burn` arithmetic cannot wrap.
- No `e.msg.sender != currentContract` restriction was needed: every rule is proven for arbitrary callers, receivers and owners, including aliases to scene contracts.

## Formalization decisions
- previews_match_operations: preview call followed by the operation in the same state and env (same timestamp). The Pot is not required to be dripped; timestamps < rho are not excluded (deposit/mint then revert in Pot.join, withdraw/redeem and the previews both use the stored chi).
- conversions_round_in_vault_favor: directly compares previewMint vs convertToAssets and previewWithdraw vs convertToShares in the same env.
- max_functions_consistent: equality rule for maxRedeem/maxWithdraw/maxDeposit/maxMint, plus two strengthening rules: redeem above maxRedeem and withdraw above maxWithdraw (same block) always revert.
- withdraw_redeem_require_authorization: one parametric rule filtered to withdraw/redeem (dispatch through a CVL helper with explicit args); spender != owner; burned shares = owner's balance decrease must be <= prior allowance; finite allowance reduced by exactly burned, infinite allowance untouched.
- invalid_receiver_rejected: parametric over the four deposit/mint overloads (incl. referral variants); receiver 0 or SavingsDai => revert.
- no_profit_from_deposit_redeem_roundtrip: deposit→redeem of all received shares in one env (caller = receiver = owner) returns <= assets and the caller's DAI balance does not increase; mint→withdraw of the paid assets burns >= minted shares.
- share_price_never_decreases: parametric over all SavingsDai methods; asserts `pot.chi()` does not decrease and `convertToAssets(s)` evaluated in the same block does not decrease. (Comparing across different timestamps is not meaningful: rpowG is uninterpreted, and real rpow rounding makes compounding path-dependent.)
- vault_ops_do_not_affect_other_holders: two parametric rules (deposit-side ops with other != receiver; withdraw-side ops with other != owner).

## Trust assumptions (bare requires)
1. `requirePotChiAtLeastRay()` — `pot.chi() >= RAY`, used only in withdrawAccounting and mintWithdrawRoundtripNoProfit. Iter-1 CEXs started from chi == 0 (CVL ceil-division by zero in the expectation; mint hands out shares for 0 assets). Unreachable: Pot's constructor sets chi = RAY and the justification rule `potChiNeverDecreases` (VERIFIED) shows no Pot entry point (drip, join, exit, both file overloads, cage, rely, deny) lowers chi. Cannot be an invariant here because parametric_contracts = [SavingsDai] and the base case does not run Pot's constructor.
2. `requireDaiSupplyIsSum()` (round 2, replaces the bare `requireDaiBalanceBounded`) — `daiToken.totalSupply() == sumDaiBalances`, used in withdrawAccounting/redeemAccounting. `sumDaiBalances` is a ghost maintained by Sstore/Sload hooks on `daiToken.balanceOf` (separate from invariants.spec's `sumOfBalances`); the Sload hook (`sum >= bal`) then bounds every read balance by totalSupply, which rules out the iter-1 CEX (receiver DAI balance > totalSupply, unchecked DaiMock.mint wrap). Justification: base case — DaiMock's constructor writes no balance, totalSupply = 0, ghost init 0; step — justification rule `daiSupplyIsSumPreserved` calls every state-changing DaiMock entry point directly (transfer, transferFrom, approve, increase/decreaseAllowance, mint, burn, rely, deny, both permits) and asserts preservation. Only DaiMock writes its storage, so this covers calls via DaiJoinMock/SavingsDai. That rule carries one extra require: for distinct accounts p != q, balanceOf(p) + balanceOf(q) <= sum (the pairs (msg.sender, a) and (a, b) touched by transfer/transferFrom) — a direct consequence of the ghost being a sum of non-negative terms, needed because the Sload hook only bounds single balances while transfer adds unchecked.
- Plus the scene's standing assumptions: rpowG never reverts; Pot/Vat are verification models.

## Expected failures / skipped
None.

## Round 2
- Iter 3 (full, unfiltered): https://prover.certora.com/orgs/certora/jobs/b4c84dec-6030-4573-b299-c9a1eadae623/report — the local client lost its connection (HTTP 401 'Server is currently unavailable') before the job finished. Streamed log up to then: daiSupplyIsSumPreserved VERIFIED, all depositOps/withdrawOpsDoNotAffectOthers instances VERIFIED, every `rule_not_vacuous` sanity check reported so far non-vacuous, no assertion violations. Final per-rule statuses must be read from the report.

## Requests
- Structural invariant for the scene: `Pot.chi() >= RAY` (would replace bare require #1; needs a setup where Pot's constructor/state is in scope, e.g. a Pot-verifying conf).

## Pass 2 (scene: DaiMock -> Dai, DaiJoinMock -> DaiJoin)
Final full unfiltered run (pass2 iter 1, rule_sanity basic): https://prover.certora.com/orgs/certora/jobs/653c426b-33ce-490f-a6db-fff70055c773/report. All 23 rules VERIFIED, and all 225 tree nodes, including every `rule_not_vacuous` child, are VERIFIED. The local client disconnected (HTTP 401) before the final summary, so the statuses were read from `treeViewStatus_18.json` in the job's output archive.

Changes:
- `using DaiMock as daiToken` became `using Dai as daiToken`. The methods entries `DaiMock.balanceOf`/`totalSupply` became `Dai.*`. The ghost hooks still go through the `daiToken` alias, which now points at `Dai.balanceOf`. The spec never named DaiJoin, so nothing changed there.
- `daiSupplyIsSumPreserved` now calls every state-changing entry point of the real Dai: transfer, transferFrom, mint, burn, approve, push, pull, move, rely, deny, and the DAI-style `permit(holder, spender, nonce, expiry, allowed, v, r, s)`. DaiMock's increase/decreaseAllowance and its two EIP-2612 permits no longer exist and were dropped.
- **Removed the pairwise require** (`bal(p) + bal(q) <= sum` for distinct p and q) from `daiSupplyIsSumPreserved`. It was needed only because DaiMock's transfer added without a check. Dai's `add` is checked, so an overflowing credit reverts and the rule verifies with only the induction hypothesis.
- **Removed `requireDaiSupplyIsSum()` from withdrawAccounting and redeemAccounting.** In pass 1 it ruled out a spurious success where DaiMock.mint's unchecked `balanceOf[usr] + wad` wrapped. Dai.mint uses the checked `add` for both the balance and totalSupply, so a would-be wrap now reverts. These success-only rules make no claim about reverting paths, so they hold without the assumption, and both VERIFIED without it.
- `requireDaiSupplyIsSum()` now appears only as the induction hypothesis inside `daiSupplyIsSumPreserved`. That rule is kept as a proven fact about the DAI model, but no vault rule depends on it anymore.
- DaiJoin's `live` flag and `exit` (which requires live == 1) only add revert paths to withdraw and redeem. No rule needed a change. `withdrawAboveMaxReverts` and `redeemAboveMaxReverts` are one-directional (above max => revert), so extra reverts cannot break them.

Remaining bare requires:
1. `requirePotChiAtLeastRay()` in withdrawAccounting and mintWithdrawRoundtripNoProfit. It is unchanged from pass 1 and justified by `potChiNeverDecreases` plus Pot's constructor.
2. `spender != owner` and `other != receiver/owner`. These are part of the property statements, unchanged.
3. `requireDaiSupplyIsSum()` as the induction hypothesis of `daiSupplyIsSumPreserved` only.
