# erc20-token — generator commentary (round 2)

- Spec: `certora/specs/erc20-token.spec`
- Conf: `certora/confs/erc20-token.conf`. It overlays `SavingsDai.conf` with:
  - `verify` pointing at this spec;
  - `parametric_contracts: ["SavingsDai"]`;
  - `optimistic_loop: true`;
  - `rule_sanity: basic`;
  - `wait_for_results: none`.
- There is no rule filter.
- `certora/confs/erc20-token_tc.conf` is the typecheck-only copy (`compilation_steps_only`).

## Runs
| Tag | Job | Result |
|---|---|---|
| erc20_token_iter1 | 6546abea-9c7f-42de-87dc-4fe1c8b01b22 | full, unfiltered; every rule and instance VERIFIED |
| erc20_token_iter2 | 6d16a4fe-5e91-4bc1-b6c6-ab606be4620e | round 1 final; all VERIFIED (judge rejected: excerpt, weak assertion (b)) |
| erc20_token_iter3 | 31e29977-c51f-44e2-a565-e7348b6bff78 | round 2 FINAL, full, unfiltered: every rule and instance VERIFIED (40+40 parametric, 5 vault-backing, 7 single, envfree check) |

- Report: https://app.certora.com/orgs/certora/jobs/<job>/report

There are no expected failures and no skipped properties.

## Imports
- The spec has a single `import "invariants.spec";` (the barrier made it importable; job 1080ee77-78e7-4afb-bb57-8a5da4e46a62).
- Its only own methods entries are `allowance(address,address)` envfree and `DaiMock.balanceOf(address)` envfree.
- The round-1 workaround (direct summary imports plus an excerpt of invariants.spec) is gone.
- Per the CVL import semantics, the imported invariants are not re-checked in this run; they are proven in job 1080ee77.

## Property → rules
| Property | Rule(s) |
|---|---|
| transfer_moves_exact_amount | transferMovesExactAmount |
| transfer_from_moves_exact_amount_and_spends_allowance | transferFromMovesExactAmountAndSpendsAllowance |
| transfer_revert_conditions | transferRevertConditions |
| transfer_from_revert_conditions | transferFromRevertConditions |
| balance_decrease_requires_owner_or_allowance | balanceDecreaseRequiresOwnerOrAllowance (parametric, all 40 SavingsDai methods) |
| allowance_increase_requires_owner_authorization | allowanceChangeRequiresAuthorization (parametric, all 40 SavingsDai methods) |
| allowance_management_functions_correct | approveCorrect, increaseAllowanceCorrect, decreaseAllowanceCorrect |
| erc20_ops_preserve_vault_backing | erc20OpsPreserveVaultBacking (parametric, filtered to the 5 ERC20 ops named by the property) |

## Decisions
- **The four revert-characteristic rules** (transfer and transferFrom, plus the `reverted <=>` assertions in the three
  allowance rules) state each function's full revert condition with `<=>`.
  - There is no require of any kind in them, not even a requireInvariant.
  - Non-payability is part of each condition (`e.msg.value != 0`).
- **Strict equalities everywhere.** No property states a tolerance and none is used.
- **The exact-amount rules** split the `from == to` / `from != to` cases. Self-transfer leaves the balance unchanged,
  which is stated in the property.
  - Each rule also covers an arbitrary third account and totalSupply.
  - transferFrom covers all three allowance cases: a third party with a finite allowance, an infinite allowance, and
    `caller == from`.
- **balanceDecreaseRequiresOwnerOrAllowance** ranges over every SavingsDai method: deposit/mint (both overloads),
  withdraw, redeem, transfer, transferFrom, both permit overloads and the views. For withdraw/redeem burns it checks the
  same thing as for transferFrom: either the caller is the owner, or the allowance covers the decrease and is reduced
  by exactly the decrease (unchanged if it is max).
- **allowanceChangeRequiresAuthorization** ranges over every SavingsDai method.
  - For the two permit overloads, the rule calls permit with explicit symbolic arguments. This lets the assertion pin
    the only pair permit may change to exactly `(pOwner, pSpender)`. Every other method is called with an arbitrary
    `calldataarg`.
  - It has two asserts:
    - (a) An increase only happens through `approve`/`increaseAllowance` by the owner, or through a permit for exactly
      that pair.
    - (b) Any change happens only through one of these (round 2, strengthened per the judge):
      - the owner's approve/increaseAllowance/decreaseAllowance (`caller == owner`);
      - a permit for exactly that pair;
      - a decrease by the spender itself (`caller == spender`) inside transferFrom, withdraw or redeem, which is spending.
      A method that lowers `allowance[x][msg.sender]` or the caller's own allowances as a side effect is caught.
  - It does not check that the permit signature is valid. That belongs to the permit component.
- **erc20OpsPreserveVaultBacking** reads the cross-contract state directly:
  - `totalSupply()`;
  - `potHarness.pie(savingsDai)`;
  - `daiMock.balanceOf(x)` for an arbitrary x;
  - `vatMock.dai(y)` for an arbitrary y.

  The filter keeps exactly the five functions the property names (transfer, transferFrom, approve, increaseAllowance,
  decreaseAllowance). The filter is the scope of the property, not a way around a failure.

## requireInvariant uses (no bare requires in any rule)
- `transferMovesExactAmount` and `transferFromMovesExactAmountAndSpendsAllowance` use
  `requireInvariant totalSupplyEqualsSumOfBalances()`.
  - Why: `balanceOf[to] += value` is unchecked. Together with the shared "one balance <= sum" load hook, the invariant
    bounds `balanceOf[to] + value` by totalSupply, so the addition cannot wrap.
- `balanceDecreaseRequiresOwnerOrAllowance` uses `requireInvariant totalSupplyEqualsSumOfBalances()` and
  `requireInvariant sharesEqualPotPie()`.
  - Why: `_mint` adds to `balanceOf[receiver]` unchecked. A wrap would look like a balance decrease. Pot.join does the
    same addition on pie[sDAI] with checked arithmetic, and `pie[sDAI] == totalSupply == sum(balances)`, which rules
    the wrap out.
- Neither invariant needs the trusted-governance restriction. Both are imported from invariants.spec and proven in
  job 1080ee77-78e7-4afb-bb57-8a5da4e46a62.

## Bare requires
- **None in this component's rules.**
- invariants.spec's own bare requires (Sload-hook summand facts and others) were accepted by the judge there. In
  rules that do not requireInvariant the matching sum invariant, the hooks only bound a free ghost.

## Summaries
- No component-specific summaries.
- The shared rpow summary is imported, but no rule here depends on it.
- The permit path calls `_isValidSignature`, which does `ecrecover` and a staticcall to `signer`. These stay as the
  prover models them. The staticcall cannot modify state, and the rules hold for any signature-check outcome.

## Structural-invariant requests
- None.
