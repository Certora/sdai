using DummyERC20Impl as dummyERC20Impl;
using SavingsDai as savingsDai;

links {
    savingsDai.dai => [dummyERC20Impl, savingsDai];
}
