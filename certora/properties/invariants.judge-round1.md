VERDICT: REJECT

Spec: certora/specs/invariants.spec, conf certora/confs/invariants.conf, run 9122f592-4c3a-4f21-bba9-7df523bb1c60 (all VERIFIED, rule_sanity basic).

The four unfiltered invariants are sound and well built: totalSupplyEqualsSumOfBalances, sharesEqualPotPie, sdaiSetupPermissionsPersist and daiTotalSupplyEqualsSumOfDaiBalances. The reason for rejecting is scope (criteria 4 and 8). Three invariants are proven only over SavingsDai's methods. For one of them the filter has no governance justification at all. For the other two it hides far more than the trusted ward-only actions the commentary uses to justify it.

## 1. Code smells
No blocking issue. Every methods-block entry is used: the envfree getters are read by the invariants, and the four wildcard entries are the constructor resolution. No tautological asserts. Minor: the `to_mathint(...)` wrappers are redundant (guideline 19), and the `with (env e)` in totalSupplyEqualsSumOfBalances / daiJoinVatDaiCoversDaiSupply binds an unused env. Cosmetic only.

## 2. Guideline compliance
No blocking issue.
- Rule 18 (never require I itself): `preserved constructor()` of potVatDaiCoversSavings, daiJoinVatDaiCoversDaiSupply and daiTotalSupplyEqualsSumOfDaiBalances requires the invariant's own predicate. In the base step the invariant is not auto-assumed, so this is not the redundancy rule 18 forbids. But it does make those three base cases trivial: the invariant is "assumed at sDAI deployment, proven preserved". The commentary states this honestly, and it is acceptable because the Maker state predates sDAI. sDAI's constructor provably does not write `Vat.dai`, `Dai.balanceOf` or `Dai.totalSupply`.
- Rule 23 is respected. Ghosts are used only for sums, which storage cannot express.
- Rule 6 is respected: the wildcard expression summaries all carry `expect`.

## 3. Precondition validity
No issue for the invariants as scoped. The supporting invariants are correctly identified and used through requireInvariant:
- sharesEqualPotPie → totalSupplyEqualsSumOfBalances: checked Pot.join addition guards the unchecked `_mint`.
- daiTotalSupplyEqualsSumOfDaiBalances → daiJoinVatDaiCoversDaiSupply: guards the unchecked `Dai.burn`.

When the scope is widened (see 8), new supporting invariants are needed:
- `Pie == Σ pie` for the Pot;
- "Pot and DaiJoin grant no Vat `can`" (`vatMock.can[potHarness][x] == 0 && vatMock.can[daiJoinMock][x] == 0`). Neither contract ever calls `hope`, so this holds given msg.sender ∉ {Pot, DaiJoin}. Without it a free prestate lets `Vat.move`/`Vat.frob` drain `dai[pot]` / `dai[daiJoin]`.

## 4. Overconstrained inputs
Each bare require was examined; all are acceptable as written:
- **Constructor-resolution summaries** (`require callee == daiJoinMock` in `ctorDaiJoinVat`; `require ctorHopeCalls == 1 => usr == potHarness`). These pin the two constructor arguments to the linked scene contracts. That is exactly the assumption the links block already makes for every post-construction state (`savingsDai.daiJoin => daiJoinMock`, `savingsDai.pot => potHarness`), so nothing new is assumed.
  - Everything derivable is asserted rather than assumed: the callee of `dai()`/`hope`/`approve`, and the first `hope` going to daiJoin.
  - The summaries run the real `vatMock.hope` / `daiMock.approve` with msg.sender = sDAI and msg.value = 0, which is the faithful model of a Solidity interface call.
  - They use the UNRESOLVED policy, so they do not fire after construction. I checked: the only remaining unresolved call in the scene is the ERC-1271 `staticcall(isValidSignature)`, a different selector.
  - No vacuity: the base cases passed rule_sanity.
- **Load-hook requires** (`bal <= sumBalances`, `bal <= sumDaiBalances`). This is the standard "summand ≤ sum" fact and holds in every reachable state. In checks that do not requireInvariant the DAI-sum invariant, `sumDaiBalances` is free and the require only bounds that free variable. Accepted.
- **`require e.msg.sender != savingsDai`** (sharesEqualPotPie, sdaiSetupPermissionsPersist). Strictly, the checklist carve-out covers contracts outside the task, and sDAI is in it. It is still justified here by in-task, verifiable evidence:
  - sDAI is a CREATE-deployed contract with no private key, so it cannot originate a transaction.
  - Every state-changing call sDAI makes (pot.join/exit, daiJoin.join/exit, dai.transferFrom, plus vat.hope/dai.approve in the constructor) is executed inline in the SavingsDai method instances of the same invariant.
  - Its only other external call is a `staticcall`, which cannot write state.

  Accepted.
- **DaiMock.permit `require owner != savingsDai`** (both overloads). This is ECDSA unforgeability: no key exists for sDAI's address, and the prover models `ecrecover` as arbitrary. sDAI also has no `isValidSignature` or fallback, so the ERC-1271 path fails for real. It is a standard cryptographic assumption, scoped to the one method where it is needed. Accepted.
- **`preserved constructor()` `require potHarness.pie[savingsDai] == 0`**. `pie[usr]` is written only by Pot.join/exit with usr == msg.sender, and sDAI's address has never run code before its constructor. Accepted.
- **Maker-state constructor requires** (Pot solvent, DaiJoin backs DAI, DAI sum consistent). These are explicit Maker-system assumptions about pre-existing state. Each holds trivially from a fresh Maker deployment (all zero). Accepted *only* together with preservation over Maker's permissionless methods. Under the current SavingsDai-only filters, the base-case assumption plus a narrow preservation check means the invariant is never actually tied to how Maker's own users evolve that state. See 8.

## 5. Trivializing summaries
No issue.
- The rpow summary is an over-approximation whose constraints are true facts of the real rpow: n=0→RAY, n=1→x, x≥RAY→z≥RAY. Pot.drip's checked `tmp - chi` still enforces chi monotonicity, so `potVatDaiCoversSavings` is non-trivially exercised through drip+suck.
- The constructor summaries run real callee code.
- Nothing is NONDET or havoced.

## 6. Manifest errors
No issue. Every invariant states obviously-correct intended behaviour.

## 7. Meaningful contract interaction
No issue. Every invariant compares contract storage or getters on both sides; there is no free-variable arithmetic. The ghosts are tied to storage through Sstore hooks.

## 8. Property coverage
All six properties are mapped (property_rules.json). The scope of three of them is not justified:
- **pot_total_pie_covers_sdai_pie** (`filtered { f -> f.contract == currentContract }`). No governance action is involved. Pot.join and Pot.exit are permissionless and touch `Pie`, and other users call them constantly on mainnet. The commentary itself says the wider proof only needs a Σpie ghost, and calls Pot accounting "Maker's responsibility". That reasoning does not justify skipping a check that is cheap and expressible here.
  - Moreover, NOTES_FOR_AGENTS.md offers this invariant to component specs for `requireInvariant` at arbitrary states. As proven, it only covers states reached through sDAI's own methods, so those uses would rest on an unproven assumption.
- **pot_vat_dai_covers_savings** and **daijoin_vat_dai_covers_dai_supply**. The stated justification is that *ward-only* actions break them (Dai.mint by a ward, Vat.fold/suck/grab, etc.). The filter, however, also removes every permissionless method by other actors. I checked each relevant method in the mocks; with governance excluded and msg.sender ∉ {sDAI, Pot, DaiJoin}, each one preserves both invariants:
  - Pot.join/exit by other users;
  - PotHarness.drip by anyone;
  - DaiJoin.join/exit by anyone;
  - Vat.move, Vat.frob, Vat.heal;
  - Dai.burn and Dai.transfer.

  Given the "no Vat `can`" lemma from 3, these are exactly the interactions that happen concurrently with sDAI in production, and the filter leaves them unchecked. The governance-trust assumption can be expressed precisely instead of with a blanket filter.
  - The only non-governance method that breaks potVatDaiCoversSavings is `PotMock.setYield`. It is test-only, is not part of mainnet Pot, and is replaced by the harness's mainnet `drip()`, so filtering it out by selector is justified.

## Required changes
1. **potTotalPieCoversSdaiPie: drop the `f.contract == currentContract` filter** and prove it over all parametric contracts.
   - Add a ghost sum over `potHarness.pie` with an Sstore hook, and a supporting invariant `potHarness.Pie() == sumPie`. For its constructor base case, use a documented Maker-state require, the same pattern as daiTotalSupplyEqualsSumOfDaiBalances.
   - In the preserved block, use requireInvariant of that supporting invariant, plus the existing `e.msg.sender != savingsDai` justification.
2. **potVatDaiCoversSavings and daiJoinVatDaiCoversDaiSupply: replace the SavingsDai-only filter** with a scope over all parametric contracts that excludes only trusted governance and the test-only mock function:
   - (a) filter out `PotHarness.setYield(uint256)` by selector, with a comment saying it is a PotMock test hook absent from mainnet Pot;
   - (b) in a generic `preserved with (env e)`, express governance trust explicitly: `require vatMock.wards[e.msg.sender] == 0 && potHarness.wards[e.msg.sender] == 0 && daiMock.wards[e.msg.sender] == 0` (the top-level caller is not a Maker ward). Also require `e.msg.sender ∉ {savingsDai, potHarness, daiJoinMock}`, with the same "contracts never originate a transaction; their calls are modeled inline" justification;
   - (c) add and requireInvariant a supporting invariant that Pot and DaiJoin grant no Vat permissions (`vatMock.can(potHarness, x) == 0 && vatMock.can(daiJoinMock, x) == 0`, parameterised on x). It should be proven under the same msg.sender restriction, with a documented Maker-state constructor require.

   If some Maker method still yields a counterexample under these exclusions, report it and excuse that specific method with a reason; do not restore the blanket filter.
3. Update invariants.commentary.md, and the scope statement in NOTES_FOR_AGENTS.md, to reflect the new scopes and supporting invariants. Until changes 1–2 land, NOTES must not advertise the filtered invariants for unconditional `requireInvariant` use.
