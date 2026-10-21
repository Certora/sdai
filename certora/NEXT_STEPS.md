# Pass 2: state and remaining work (2026-10-21)

## Done in pass 2
- Autosetup re-run diagnosed: autosetup cannot parse certora-cli 8.20.0 job links
  (`utils/job_utils.py` regex expects /output/ URLs; CLI prints /orgs/<org>/jobs/<id>/report) and
  `utils/cloud_runner.py:715` maps exit code 0 to -1 (`process.returncode or -1`). Every cloud stage
  therefore "fails"; local stages worked. Not patched (installed tool).
- Scene audit against makerdao/dss master: Pot port matches; Vat matches for hope/move/suck.
  Replaced DaiJoinMock -> certora/harnesses/DaiJoin.sol (real dss DaiJoin: live/cage, exit requires live)
  and DaiMock -> certora/harnesses/Dai.sol (real dss dai.sol v1: no receiver checks, checked math).
- Added certora/harnesses/SigPacker.sol (Solidity-built abi.encodePacked(r,s,v)) to close the permit gap.
- scene.spec: isValidSignature now a deterministic ghost of (signer, digest, keccak256(sig)) instead of NONDET.
- All confs switched to the new scene (files + links). invariants / erc20-token / permit typecheck.
- Re-runs launched: logs/sanity-linked_pass2.log, logs/invariants_pass2.log, logs/erc20-token_pass2.log.
- New property batch: properties/maker-integration.properties.json (5 properties, not yet formalized).

## Completed after the usage-limit pause
- Pass-2 re-runs: sanity clean; invariants/erc20 first failed on permit(bytes) due to a deterministic
  isValidSignature ghost summary (impossible storage changes) -> reverted to NONDET; re-runs clean.
- erc4626-vault migrated to Dai/DaiJoin, DAI assumptions removed, all 23 VERIFIED, judge ACCEPT.
- permit: SigPacker equivalence VERIFIED, nonce require removed, 7/7 VERIFIED, judge ACCEPT.
- maker-integration: 5 rules VERIFIED + finding F-1 (redeemDoesNotDependOnDrip), judge ACCEPT.
- report/report.md + report.json regenerated (pass 2).

## Remaining
- Push the pass-2 commit to Certora/sdai (awaiting go-ahead).
