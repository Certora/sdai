/*
 * maker-models / constructor: what SavingsDai's constructor establishes in a consistent Maker
 * deployment. Property: constructor_wires_maker_system.
 *
 * CVL cannot call a constructor; the only CVL construct that checks one is an invariant's
 * induction base ("Induction base: After the constructor"), which runs SavingsDai's constructor
 * with arbitrary arguments (_daiJoin, _pot) on a fresh SavingsDai. The invariant below is
 * filtered to NO methods, so it is exactly that base-case check. Preservation by every SavingsDai
 * method is a separate, already-proven result: maker-integration's setupApprovalsPreserved.
 *
 * Why a separate spec and conf (instead of importing scene.spec / using base.conf's links):
 *  - scene.spec NONDETs the wildcard hope / approve / vat / dai calls, which in this scene are
 *    exactly the constructor's (unresolved) calls; that would drop the writes we want to check.
 *    This spec does not import scene.spec (nor invariants.spec, which imports it). It needs no
 *    _rpow / isValidSignature summary either: the constructor calls neither and no method runs.
 *  - base.conf's links SavingsDai:{vat,dai,daiJoin,pot}=... make the prover read SavingsDai's
 *    immutables as those constants (pass-3 iter 1 run 5ab7d489: `pot() == Pot` was a trivially
 *    true postcondition, while vat.can(sDAI, Pot) == 1 was VIOLATED with _pot != Pot). The conf
 *    maker-models-constructor.conf therefore drops those four links, so the getters below return
 *    what the constructor actually stored. It keeps DaiJoin:vat=Vat and DaiJoin:dai=Dai.
 *
 * Deployment-consistency assumption (the property's hypothesis), made explicit:
 *  (A1) the _daiJoin argument is the scene DaiJoin: the constructor's first call, daiJoin.vat(),
 *       is dispatched OPTIMISTICALLY to DaiJoin.vat() only, so paths where _daiJoin is any other
 *       address are discarded (DISPATCH matches both selector and target address, methods.html
 *       "DISPATCH list summaries").
 *  (A2) daiJoin.vat() is the Vat and daiJoin.dai() is the Dai: the conf's links DaiJoin:vat=Vat,
 *       DaiJoin:dai=Dai.
 *  _pot is NOT constrained: the constructor never calls it, it only stores it and hopes it.
 *
 * Every other constructor call is dispatched PESSIMISTICALLY with `default ASSERT_FALSE`: if
 * daiJoin.dai(), vat.hope(...) or dai.approve(...) went anywhere other than the listed scene
 * function, the run would fail. In particular dai.approve can only resolve to Dai.approve, never
 * to SavingsDai.approve (the pitfall of a plain `_.approve => DISPATCHER`, whose candidates include
 * every contract with approve(address,uint256), sDAI itself among them).
 * These wildcard entries use the default UNRESOLVED policy; with the SavingsDai links dropped,
 * the constructor's four calls are the only unresolved calls that are ever executed here (the
 * invariant checks no method).
 */

using Vat as vatC;
using Dai as daiToken;
using DaiJoin as daiJoinC;

methods {
    function _.vat() external => DISPATCH(optimistic=true) [ DaiJoin.vat() ];
    function _.dai() external => DISPATCH [ DaiJoin.dai() ] default ASSERT_FALSE;
    function _.hope(address) external => DISPATCH [ Vat.hope(address) ] default ASSERT_FALSE;
    function _.approve(address, uint256) external => DISPATCH [ Dai.approve(address, uint256) ] default ASSERT_FALSE;

    function vat() external returns (address) envfree;
    function dai() external returns (address) envfree;
    function daiJoin() external returns (address) envfree;
    function pot() external returns (address) envfree;
    function Vat.can(address, address) external returns (uint256) envfree;
    function Dai.allowance(address, address) external returns (uint256) envfree;
}

/// constructor_wires_maker_system: after construction with (_daiJoin = DaiJoin, any _pot),
/// sDAI points at the scene DaiJoin, Vat and Dai, stored _pot as pot(), and has given DaiJoin and
/// pot() the Vat permissions and DaiJoin the unlimited DAI allowance that deposit/withdraw need.
invariant constructorWiresMakerSystem()
    daiJoin() == daiJoinC
    && vat() == vatC
    && dai() == daiToken
    && vatC.can(currentContract, daiJoin()) == 1
    && vatC.can(currentContract, pot()) == 1
    && daiToken.allowance(currentContract, daiJoin()) == max_uint256
    filtered { f -> false }
