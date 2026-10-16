// Summaries for SavingsDai external interfaces
// Abstracts away VatLike, PotLike, DaiJoinLike, DaiLike, and IERC1271

methods {
    // --- VatLike ---
    // hope(address): called twice during construction to authorize DaiJoin and Pot.
    // No return value; modeled as a non-reentrant external call.
    function _.hope(address) external => HAVOC_ECF;

    // --- PotLike (view functions) ---
    // chi(): accumulated savings-rate multiplier (RAY units). View, returns uint256.
    function _.chi() external => NONDET;
    // rho(): timestamp of last drip. View, returns uint256.
    function _.rho() external => NONDET;
    // dsr(): per-second savings rate. View, returns uint256.
    function _.dsr() external => NONDET;

    // --- PotLike (state-changing functions) ---
    // drip(): advances chi to current time, returns the updated chi value.
    function _.drip() external => HAVOC_ECF;
    // join(uint256): increases SavingsDai's pie by shares. No return value.
    function _.join(uint256) external => HAVOC_ECF;
    // exit(uint256): decreases SavingsDai's pie by shares. No return value.
    function _.exit(uint256) external => HAVOC_ECF;

    // --- DaiJoinLike (view functions) ---
    // vat(): returns the Vat address. Used during construction.
    function _.vat() external => NONDET;
    // dai(): returns the DAI ERC-20 address. Used during construction.
    function _.dai() external => NONDET;

    // --- DaiJoinLike (state-changing functions) ---
    // join(address, uint256): converts ERC-20 DAI to internal Vat DAI. No return value.
    function _.join(address, uint256) external => HAVOC_ECF;
    // exit(address, uint256): converts internal Vat DAI to ERC-20 DAI for receiver. No return value.
    function _.exit(address, uint256) external => HAVOC_ECF;

    // --- DaiLike ---
    // transferFrom: pull DAI from depositors; dispatched to DummyERC20Impl in scene.
    function _.transferFrom(address, address, uint256) external => DISPATCHER(true);
    // approve: grant infinite allowance to DaiJoin; dispatched to DummyERC20Impl in scene.
    function _.approve(address, uint256) external => DISPATCHER(true);

    // --- IERC1271 ---
    // isValidSignature: contract-wallet signature validation. View, returns bytes4.
    function _.isValidSignature(bytes32, bytes) external => NONDET;
}
