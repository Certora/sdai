# Savings Dai design and verification properties

## Purpose

`SavingsDai` is a non-upgradeable tokenized vault for DAI deposited in Maker's
Dai Savings Rate (DSR). A user deposits DAI and receives transferable sDAI
shares. Those shares represent a proportional claim on DAI held through the
Maker `Pot`; as the DSR accumulates, the DAI value of each share changes while
the number of shares does not.

The contract is intended to provide:

- an ERC-20 share token named `Savings Dai` (`sDAI`), with 18 decimals;
- the synchronous ERC-4626 deposit, mint, withdraw, redeem, preview, conversion,
  and limit interface over DAI;
- gasless share approvals following EIP-2612, including contract-wallet
  signatures through EIP-1271; and
- optional referral events for deposits and mints, without changing their
  accounting.

This document describes the implementation in `src/SavingsDai.sol`. It is also
intended as input to AutoProver: statements under **Properties to verify** are
the desired formal behavior, subject to the environmental assumptions below.

## Components and trust boundaries

`SavingsDai` receives two constructor arguments and derives the other external
dependencies from them:

- `daiJoin`: the canonical Maker adapter between ERC-20 DAI and internal Vat DAI;
- `vat`: returned by `daiJoin.vat()` and used only to authorize `daiJoin` and
  `pot` during construction;
- `dai`: returned by `daiJoin.dai()`, the ERC-20 asset accepted by the vault; and
- `pot`: the Maker DSR accumulator in which normalized DAI balances are held.

All four addresses are immutable. The contract has no owner, administrator,
upgrade mechanism, pause switch, fee recipient, or privileged user after
deployment.

The Maker contracts are trusted dependencies, not adversarial callbacks. The
properties in this document assume that they implement their documented
interfaces atomically and do not reenter `SavingsDai`. In particular:

- DAI's `transferFrom` either transfers exactly the requested amount or reverts;
- `DaiJoin.join` consumes that amount of DAI and credits the same amount of
  internal Vat DAI, with the expected WAD-to-RAD scaling;
- `DaiJoin.exit` consumes the requested internal Vat DAI and sends exactly that
  amount of ERC-20 DAI to the receiver;
- `Pot.join(shares)` and `Pot.exit(shares)` change
  `pot.pie(address(this))` by exactly `shares`;
- after `Pot.drip()`, `pot.rho() == block.timestamp` and the returned value is
  the current `pot.chi()`; and
- `pot.chi()`, `pot.dsr()`, and `pot.rho()` satisfy the Maker Pot arithmetic and
  authorization rules.

Properties about increasing share value additionally assume `pot.dsr() >= RAY`.
If governance can set `dsr < RAY`, share value is allowed to decrease and those
monotonicity properties do not apply.

## Units and terminology

- **Asset**: ERC-20 DAI, measured in WAD (`10^18`) units.
- **Share**: sDAI, also measured in WAD units.
- **RAY**: `10^27`, Maker's fixed-point scale for rates.
- **RAD**: `10^45`, the Vat's internal DAI scale (`WAD * RAY`).
- **`chi`**: the Pot's accumulated DSR rate in RAY units.
- **`dsr`**: the Pot's per-second savings factor in RAY units.
- **`rho`**: the timestamp at which stored `chi` was last updated.
- **`pie`**: a normalized Pot balance. One sDAI share corresponds to one unit
  of `pie` held by the `SavingsDai` contract.

For view functions, define the effective rate at timestamp `t` as:

```text
effectiveChi(t) = pot.chi(),                                      if t <= pot.rho()
effectiveChi(t) = rpow(pot.dsr(), t - pot.rho()) * pot.chi() / RAY, otherwise
```

All divisions are integer divisions. `floor(x / y)` rounds down, while
`ceil(x / y)` is `_divup(x, y)`.

## Accounting model

The primary accounting relationship is:

```text
totalSupply == pot.pie(address(SavingsDai))
```

It holds from deployment, when both values are zero, and is preserved because
every mint of `shares` is paired with `pot.join(shares)`, while every burn is
paired with `pot.exit(shares)`.

The ERC-20 share ledger must also satisfy:

```text
totalSupply == sum(balanceOf[user])
```

The sum is conceptual over all addresses. Transfers redistribute shares without
changing `totalSupply`; deposits and mints create exactly the shares credited to
the receiver; withdrawals and redemptions destroy exactly the owner's shares.

At a fixed effective `chi`, the vault's reported asset value is:

```text
totalAssets() == floor(totalSupply * effectiveChi / RAY)
```

Rounding dust is expected. It must favor the vault rather than allow a user to
receive more assets than their shares represent or receive more shares than the
assets they supplied represent.

Each operation can leave a sub-share rounding remainder as internal Vat DAI
owned by `SavingsDai`:

- deposit/mint joins `shares * chi` RAD into the Pot after DaiJoin credits
  `assets * RAY` RAD; and
- withdraw/redeem exits `shares * chi` RAD from the Pot before DaiJoin sends
  `assets * RAY` RAD to the receiver.

The selected rounding directions make each per-operation remainder
non-negative. This internal Vat dust is not part of `totalAssets()`, and the
design does not promise that `vat.dai(address(this))` is zero. Formal properties
should distinguish this internal RAD balance from ERC-20 DAI held by the
wrapper.

Unsolicited DAI transfers directly to `SavingsDai` are not donations to the
ERC-4626 accounting and do not change `totalAssets()`: the implementation values
only the shares deposited in the Pot.

## ERC-4626 operations

All four state-changing operations first use the current Pot rate. If
`block.timestamp > pot.rho()`, they call `pot.drip()`; otherwise they read
`pot.chi()`. Subject to the trusted-Pot assumptions, this rate is equal to
`effectiveChi(block.timestamp)`.

### Deposit an exact amount of assets

`deposit(assets, receiver)` computes:

```text
shares = floor(assets * RAY / chi)
```

It transfers exactly `assets` DAI from the caller, deposits that DAI through
`DaiJoin`, joins exactly `shares` into the Pot, and mints exactly `shares` sDAI
to `receiver`.

### Mint an exact amount of shares

`mint(shares, receiver)` computes:

```text
assets = ceil(shares * chi / RAY)
```

It transfers and deposits exactly `assets` DAI and mints exactly `shares` sDAI.
Rounding up prevents the caller from receiving a chosen number of shares for
less than their current asset value.

### Withdraw an exact amount of assets

`withdraw(assets, receiver, owner)` computes:

```text
shares = ceil(assets * RAY / chi)
```

It burns exactly `shares` from `owner`, exits exactly `shares` from the Pot, and
sends exactly `assets` DAI to `receiver`. If the caller is not `owner`, the
caller must have sufficient share allowance from `owner`.

### Redeem an exact amount of shares

`redeem(shares, receiver, owner)` computes:

```text
assets = floor(shares * chi / RAY)
```

It burns and exits exactly `shares`, then sends exactly `assets` DAI to
`receiver`. Rounding down prevents the redeemer from receiving more than the
current asset value of the burned shares.

### Limits, conversions, and previews

There are no protocol-level per-user or global deposit/mint limits:

```text
maxDeposit(any receiver) == type(uint256).max
maxMint(any receiver)    == type(uint256).max
maxRedeem(owner)         == balanceOf[owner]
maxWithdraw(owner)       == convertToAssets(balanceOf[owner])
```

The conversion and preview functions use the projected `effectiveChi` without
calling `drip`:

```text
convertToShares(assets)  == floor(assets * RAY / effectiveChi)
convertToAssets(shares)  == floor(shares * effectiveChi / RAY)
previewDeposit(assets)   == convertToShares(assets)
previewMint(shares)      == ceil(shares * effectiveChi / RAY)
previewWithdraw(assets)  == ceil(assets * RAY / effectiveChi)
previewRedeem(shares)    == convertToAssets(shares)
```

If no external dependency changes between a preview and the corresponding
operation in the same transaction, the returned operation amount must equal
the previewed amount.

## ERC-20 share behavior

- `transfer` and `transferFrom` move exactly `value` shares, preserve
  `totalSupply`, and leave all unrelated balances unchanged.
- Neither function may send shares to the zero address or the `SavingsDai`
  contract itself.
- A transfer may send shares back to the sender and is then accounting-neutral.
- `transferFrom` does not consume allowance when the caller is `from`.
- A finite allowance is reduced by exactly the transferred value.
- An allowance equal to `type(uint256).max` is treated as infinite and is not
  reduced.
- `approve` replaces the caller's allowance for `spender` with `value`.
- `increaseAllowance` and `decreaseAllowance` change only the selected
  allowance by the requested amount; subtraction below zero reverts.
- Every successful share creation, destruction, or transfer emits the
  corresponding ERC-20 `Transfer` event.

## Permit behavior

The permit digest binds the owner, spender, value, current owner nonce,
deadline, chain ID, and this contract's address through the EIP-712 domain.

A permit succeeds only when:

- `owner` is not the zero address;
- `block.timestamp <= deadline`;
- either the signature is 65 bytes and ECDSA recovery returns `owner`, or a
  static call to `owner.isValidSignature(digest, signature)` returns the
  EIP-1271 magic value.

On success, and assuming the starting nonce is less than `type(uint256).max`,
the permit increments `nonces[owner]` exactly once, sets
`allowance[owner][spender]` to `value`, and changes no token balances or supply.
On failure, all state including the nonce and allowance remains unchanged.
Therefore a successful permit cannot be replayed while nonces do not wrap.

The deployment-time domain separator is used while `block.chainid` equals
`deploymentChainId`. If the chain ID changes, `DOMAIN_SEPARATOR()` and permit
validation use a separator recomputed for the current chain, preventing a
signature from being replayed across the two chain domains.

## Referral behavior

The referral overloads of `deposit` and `mint` must have exactly the same state
changes and return values as their non-referral counterparts. They additionally
emit one `Referral(referral, receiver, assets, shares)` event. A referral code
has no effect on balances, supply, allowances, conversion rates, or Maker state.

## Properties to verify

The following are the highest-value AutoProver targets.

### Global invariants

1. **Share/Pot conservation:** `totalSupply == pot.pie(address(this))` after
   construction and after every successful public operation.
2. **Share-ledger conservation:** `totalSupply` equals the sum of all sDAI
   balances.
3. **No stranded ERC-20 operation value:** a successful deposit/mint moves all
   ERC-20 DAI supplied by that operation out of `SavingsDai`; a successful
   withdraw/redeem sends the computed ERC-20 DAI to the chosen receiver.
   Non-negative internal Vat DAI rounding dust is expected and excluded.
4. **Immutable dependencies:** `vat`, `daiJoin`, `dai`, and `pot` never change.
5. **No privilege:** no caller can alter dependencies, create shares without
   the corresponding Pot join, or destroy another user's shares without being
   that user or having enough allowance.

### Conversion and rounding

6. **Conversions round down:**
   `convertToAssets(convertToShares(assets)) <= assets` and
   `convertToShares(convertToAssets(shares)) <= shares`, whenever the
   intermediate arithmetic does not overflow and the rate is nonzero.
7. **User-facing rounding favors the vault:** deposit and redeem round down;
   mint and withdraw round up, exactly as defined above.
8. **Preview correspondence:** with no intervening environmental change,
   `previewDeposit`, `previewMint`, `previewWithdraw`, and `previewRedeem` equal
   the amount returned by their corresponding operation.
9. **View/drip consistency:** projecting the rate in a conversion immediately
   before `pot.drip()` gives the same conversion result immediately after the
   drip, assuming the Pot uses the same `rpow` arithmetic.
10. **Share-value monotonicity:** if time does not go backward and `dsr >= RAY`,
    `convertToAssets(shares)` cannot decrease for fixed `shares` unless Maker
    governance or a trusted dependency violates the assumptions.

### State transitions and authorization

11. **Exact mint transition:** deposit/mint increases `totalSupply` and the
    receiver's balance by exactly the returned/requested shares, and increases
    the vault's Pot `pie` by the same amount.
12. **Exact burn transition:** withdraw/redeem decreases `totalSupply`, the
    owner's balance, and the vault's Pot `pie` by exactly the burned shares.
13. **Unrelated-account framing:** vault operations change only the named
    receiver/owner share balance; transfers change only sender and receiver
    balances; no other user's balance changes.
14. **Allowance enforcement:** delegated transfer, withdraw, and redeem revert
    when finite allowance is insufficient and consume exactly the used shares
    otherwise; infinite allowance remains unchanged.
15. **Invalid receiver atomicity:** deposit/mint to the zero address or this
    contract, and transfer to either address, revert without any state change.
16. **Insufficient balance atomicity:** transfer, withdraw, and redeem revert
    without state change when the source/owner lacks shares.
17. **Referral equivalence:** each referral overload is state-equivalent to the
    matching ordinary operation for identical inputs and starting state.

### Permit

18. **Permit authorization:** only a 65-byte ECDSA signature recovering to the
    owner, or an EIP-1271 signature accepted by the owner, can set an allowance;
    in both cases the digest uses the current nonce and domain.
19. **Permit replay protection:** a signature accepted once cannot succeed
    again because the nonce has advanced, assuming the nonce does not wrap.
20. **Permit failure atomicity:** expired, malformed, wrong-domain, wrong-nonce,
    and invalid contract-wallet signatures do not change nonce or allowance.
21. **Chain-domain separation:** changing the chain ID changes the domain
    separator and invalidates signatures from the prior chain domain.

## Reverts and acceptable limits

Arithmetic overflow, permit nonce wrap, a zero effective rate, or a failure in
a trusted external contract are numeric or environmental boundaries. The exact
state-transition properties assume additions and multiplications remain within
`uint256`, as expected from the relationship between sDAI supply and DAI supply.
`maxDeposit` and `maxMint` report no explicit vault limit, but actual calls can
still revert because of uint256 arithmetic, insufficient DAI balance or
approval, invalid receivers, or Maker dependency conditions. Verification
should not interpret these limits as an authorization bypass.

Zero-asset deposits and zero-share mints are permitted when the external Maker
contracts accept them. Very small nonzero asset deposits may mint zero shares
because deposit conversion rounds down; this is a consequence of the specified
integer arithmetic and should not be "proved away" by assuming positive inputs
always produce positive outputs.

## Out of scope

- Correctness, solvency, governance, or availability of Maker's Vat, Pot,
  DaiJoin, or DAI contracts beyond the assumptions stated above.
- Economic sustainability of the DSR or governance choosing an appropriate
  `dsr`.
- Front-running, censorship, or transaction ordering outside a single call.
- Off-chain interpretation, attribution, or revenue sharing based on referral
  events.
- DAI sent directly to the `SavingsDai` address outside a vault operation.
- Gas bounds and liveness when an external dependency reverts.

## Reference material

- [ERC-4626: Tokenized Vaults](https://eips.ethereum.org/EIPS/eip-4626),
  especially its preview semantics and prescribed rounding directions.
- [ERC-2612: Permit Extension for EIP-20](https://eips.ethereum.org/EIPS/eip-2612).
- [Maker Pot detailed documentation](https://docs.makerdao.com/smart-contract-modules/rates-module/pot-detailed-documentation).
- `src/test/SavingsDai-erc4626.t.sol` and
  `src/test/SavingsDai-integration.t.sol` for the repository's existing
  executable expectations.
