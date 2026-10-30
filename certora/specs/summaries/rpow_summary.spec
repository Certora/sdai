// Shared summary of the two fixed-point exponentiation loops (SavingsDai._rpow and the Pot's _rpow).
// Why: with loop_iter=3 + optimistic_loop the real loop would only be explored for exponents < 16,
// i.e. < 16 seconds since the last drip. Summarizing both with ONE uninterpreted function keeps the
// views (sDAI extrapolating chi) and Pot.drip consistent for any elapsed time.
// Soundness: rpowG is an arbitrary deterministic function, constrained only by facts that hold for
// the real rpow whenever it returns: n == 0 -> RAY, n == 1 -> x, x >= RAY -> result >= RAY.
// What is lost: the real rpow's overflow reverts (only relevant to "does not revert" rules, which
// must then state "rate accumulation does not overflow" as an explicit assumption).
methods {
    function SavingsDai._rpow(uint256 x, uint256 n) internal returns (uint256) => rpowCVL(x, n);
    function PotMock._rpow(uint256 x, uint256 n, uint256 base) internal returns (uint256) => rpowBaseCVL(x, n, base);
}

definition RAY() returns uint256 = 10^27;

ghost rpowG(uint256, uint256) returns uint256;

function rpowCVL(uint256 x, uint256 n) returns uint256 {
    uint256 z = rpowG(x, n);
    require n == 0 => z == RAY(), "real rpow returns RAY for exponent 0";
    require n == 1 => z == x, "real rpow returns x for exponent 1";
    require x >= RAY() => z >= RAY(), "real rpow with half-up rounding never drops below RAY when x >= RAY";
    return z;
}

function rpowBaseCVL(uint256 x, uint256 n, uint256 base) returns uint256 {
    assert base == RAY(), "Pot always calls rpow with base RAY";
    return rpowCVL(x, n);
}
