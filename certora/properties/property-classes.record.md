# Phase 4 property-class record (all components)

Three rounds per component. Round 1 drafted the lists; round 2 removed duplicates (e.g. a separate
"self-transfer" property, folded into transfer_moves_exact_amount) and added the blocking/liveness
properties; round 3 added nothing for ERC20 token and Permit (stop signal), and added
share_price_independent_of_donations for the vault.

| Class | ERC20 token | ERC4626 vault | Permit |
|---|---|---|---|
| Value conservation | erc20_ops_preserve_vault_backing; invariant total_supply_equals_sum_of_balances | shares_equal_pot_pie (inv), rounding_favors_vault, deposit/mint/withdraw/redeem_effects_exact | permit_effects_exact (moves no value) |
| Who absorbs change over time | n/a: transfers are instantaneous, no two-step flow | actions_price_at_accrued_rate, share_price_never_decreases, third_party_value_unaffected (interest accrues pro-rata via chi) | n/a: no value captured |
| What going first is worth | n/a: no price-bearing state | third_party_value_unaffected, actions_price_at_accrued_rate | Front-running a permit only consumes the nonce while setting the same allowance; griefing of integrators is outside the contract — no property |
| Rounding direction | n/a: no division | rounding_favors_vault, round_trip_no_profit, effects_exact rules fix floor/ceil per function | n/a |
| Empty state / first participant | n/a | share_price_independent_of_donations (price is chi from Pot, not a balance ratio) | n/a |
| What must not be blocked | transfer_revert_conditions, transfer_from_revert_conditions | redeem_always_possible, max_functions_accurate | Not stated: a valid permit can be blocked only by consuming its nonce (same effect); no other blocker |
| Who the attacker may be | balance_decrease_requires_owner_or_allowance, allowance_increase_requires_owner_authorization | deposit_pulls_only_from_caller; sDAI has no admin — Maker governance (Pot/Vat/Dai wards) is trusted and excluded as adversary | permit_requires_owner_signature, nonces_change_only_by_permit |
| Staleness of external values | n/a | actions_price_at_accrued_rate, preview_matches_action (views extrapolate chi with rpow) | domain_separator_bound_to_chain (cached separator vs chain id) |
| Re-entrancy | n/a: no external calls | Control only reaches Maker core contracts (Dai, DaiJoin, Pot, Vat), all in scene and trusted; no untrusted callee — no property | isValidSignature is reached by staticcall, which cannot modify state — no property |
| Fees, splits | n/a: no fees | n/a: no fees; referral is an event only | n/a |
| Lifecycle | n/a: no pause | redeem_always_possible includes post-cage Pot (exit has no live check) | n/a |
| Two roles, one address | transfer rules cover from == to and caller == from | effects_exact rules cover owner == caller == receiver; receiver == sDAI is rejected on entry; on exit it strands the receiver's own DAI (user choice, no third party harmed) — no property | owner == spender is a plain allowance set — no property |
