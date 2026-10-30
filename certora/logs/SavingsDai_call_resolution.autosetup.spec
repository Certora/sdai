using DaiJoinMock as daiJoinMock;
using DaiMock as daiMock;
using DummyERC20Impl as dummyERC20Impl;
using PotHarness as potHarness;
using SavingsDai as savingsDai;

links {
    savingsDai.pot => potHarness;
    savingsDai.daiJoin => daiJoinMock;
    savingsDai.dai => [daiMock, dummyERC20Impl, savingsDai];
}
