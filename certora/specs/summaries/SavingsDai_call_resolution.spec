using DaiJoinMock as daiJoinMock;
using DaiMock as daiMock;
using DummyERC20Impl as dummyERC20Impl;
using PotHarness as potHarness;
using SavingsDai as savingsDai;
using VatMock as vatMock;

// Autosetup's original block is kept in certora/logs/SavingsDai_call_resolution.autosetup.spec.
// Edited by hand: autosetup left the Vat/Dai immutables of DaiJoin and Pot (and sDAI.vat) unlinked,
// so their calls were havocs, and it dispatched sDAI.dai to three candidates. In the deployed system
// sDAI.dai == DaiJoin.dai (constructor reads it from daiJoin), and every vat is the single Vat.
links {
    savingsDai.pot => potHarness;
    savingsDai.daiJoin => daiJoinMock;
    savingsDai.dai => daiMock;
    savingsDai.vat => vatMock;
    daiJoinMock.vat => vatMock;
    daiJoinMock.dai => daiMock;
    potHarness.vat => vatMock;
}
