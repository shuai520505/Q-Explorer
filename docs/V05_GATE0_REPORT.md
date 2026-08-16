# Q-Explorer V0.5 Gate 0 Report

## Scope and outcome

Gate 0 completed a capability and integration audit only. It submitted **zero** real-hardware jobs and ran **zero** hardware VQE experiments. The current machine has no configured China Mobile quantum credential, so account inventory, execution permission, quotas, native gates, connectivity, and calibration values remain `UNKNOWN`; none were inferred from publicity or example device identifiers.

## Platform

1. The identified platform is **China Mobile Cloud WuYue Quantum Computing Cloud Platform**. The identification is supported by the [official China Mobile Cloud product page](https://qiye.cmcloud.com/taizhou2/zy-WYQCLOUD.html) and the [official WuYue open-source organization](https://gitee.com/WUYUEQbit).
2. The preferred automatable interface is the official [WuYueSDK](https://gitee.com/WUYUEQbit/WuYueSDK), with QCOS API capabilities documented in the official [QCOS repository](https://gitee.com/WUYUEQbit/QCOS). Audited source versions were WuYueSDK 1.1.0 at `5fb5cd9` and QCOS 1.5.0 at `4d0706c`.
3. Current account authentication is **not available**: `MOBILE_QUANTUM_CREDENTIAL=NOT_SET`. No secret value was printed or persisted.
4. Real-hardware permission is **not confirmed**. Device discovery was not attempted because credentials are absent.

The official SDK source accepts `access_key` and `secret_key`, exposes a `Runner`, and QCOS source exposes device, calibration, option, and job APIs. This proves an integration path exists, not that this account owns hardware access. WuYueSDK 1.1.0 pins Qiskit 1.4.3 while Q-Explorer uses Qiskit 2.5.1; QCOS 1.5.0 targets Python >=3.11,<3.13 and POSIX. A separate pinned integration environment is therefore recommended instead of modifying the working VQE environment.

## Hardware inventory

5–14. Actual account-visible devices: **0 confirmed**. Real devices: 0 confirmed; simulators: 0 confirmed. Gate-model VQE suitability, qubit counts, native gate sets, connectivity, shot limits, quotas, and calibration metadata are all `UNKNOWN`. `hardware_inventory.json` deliberately contains an empty `devices` array with `NOT_QUERIED_CREDENTIAL_NOT_SET`. The SDK/API capability to request calibration exists in source, but account calibration availability is not evidence until a credentialed query succeeds.

Coherent Ising/optical/QUBO machines, if later returned by the API, must be marked unsuitable unless they explicitly execute gate-model parameterized circuits. A product name containing “quantum” is not sufficient.

## Candidate requirements and compilation

15. Exactly 2 frozen V0.4 candidates were loaded. Both use two 4-qubit ring Ising Hamiltonians with only Z and ZZ observables. HWCAND_01 compares depth 1 and 2; HWCAND_02 compares depth 2 and 3. Each depth contains paired linear/ring HEA circuits.
16. Candidate-to-account-device compatibility is `UNKNOWN` because no device metadata is available.
17–19. Device-specific transpilation was not possible. A deterministic local Qiskit dry-run was performed against explicitly labelled generic fully-connected and linear 4-qubit references. The linear-reference stress case reached up to 10 inserted SWAP instructions and a depth ratio of 2.467. Ring and linear HEA can therefore incur unequal routing overhead on sparse connectivity, but these numbers are **not** claims about a China Mobile device. Actual native-gate mapping remains required.

The important future confound is the separation of ansatz-intrinsic behavior from routing/connectivity overhead. Gate 0 records both physical-depth/logical-depth and physical-2q/logical-2q ratios for that reason.

## Hardware-A — fixed-parameter validation

20. Hardware-A is **not executable now**. Historical V0.4 traces store energy trajectories but not final parameter vectors; account hardware and limits are also unknown. No guessed parameters were introduced. An offline simulation re-optimization, parameter freeze, and separate V0.5-A preregistration are required.
21. The draft recommendation is 2048 shots, with 512/1024/2048/4096 retained as audited options pending hardware limits and variance analysis.
22. The draft repeat policy is three repeats within each of three calibration windows, so shot noise and drift can be separated.
23. Physical mapping is pending actual connectivity/calibration metadata. Generic mappings are preparation checks only.
24. Each candidate has 8 unique Hamiltonian×Ansatz circuit configurations and a draft 72 circuit executions at 9 repeats (147,456 shots at 2048 shots/execution). Without batching this is up to 72 jobs per candidate; with all eight circuits batched, 9 jobs per candidate. Provider batch limits are unknown.

All candidate Hamiltonians contain only Z/ZZ terms, so one computational-basis measurement group is sufficient. `MEASUREMENT_GROUPING_SIMPLE=YES` for these candidates only.

## Hardware-B — limited hardware VQE

25–27. Hardware-B feasibility is **UNCERTAIN** and is not recommended before Hardware-A. With two candidates, eight Hamiltonian×Ansatz configurations per candidate, 40 COBYLA iterations, one Z-basis group, 2048 shots, and three repeats, the transparent lower bound is 1,920 circuit executions and 3,932,160 shots. Actual optimizer evaluations may exceed the one-evaluation-per-iteration lower-bound assumption. Quota, batching, and parameter binding remain unknown.

## Scientific risk

28. The largest risks are routing overhead, calibration/readout drift, finite-shot uncertainty, and the missing frozen parameter vectors.
29. Yes, connectivity/transpilation can plausibly change the apparent boundary; the generic sparse-connectivity audit already shows topology-dependent overhead. This is a confound to measure, not a hardware effect conclusion.
30. Calibration drift can be recorded only if the credentialed device API returns timestamps and error/T1/T2 data. The interface exists, availability is `UNKNOWN`.
31. V0.4 synthetic N1/N2/N3 errors may later be compared descriptively to device error scales as `ROUGH_ERROR_SCALE_COMPARISON`; real hardware must never be labelled equivalent to one synthetic level.

Gate 0 enables no mitigation. A future protocol should report raw results even if readout mitigation or zero-noise extrapolation is later added.

## Decision

32. Entry to V0.5-A is **not recommended yet**.
33. A minimal smoke job is required after credentials/device discovery and explicit user confirmation. The prepared 2-qubit, shallow, 128-shot plan is `SMOKE_ONLY` and excluded from scientific analysis.
34. The immediate requirement is credentials and possibly account permission/quota approval. No claim about recharge needs can be made without an account query.
35. Both frozen candidates remain preserved; neither was modified to fit unknown hardware.
36. No hardware-adapted candidate is created in Gate 0. If a mismatch is later confirmed, it must be a separately labelled and preregistered derived candidate.

## Gate

```text
QEXPLORER_V05_GATE0_COMPLETE=YES

V01_REGRESSION=PASS
V02_REGRESSION=PASS
V03_REGRESSION=PASS
V03C_REGRESSION=PASS
V03D_REGRESSION=PASS
V04_REGRESSION=PASS

MOBILE_QUANTUM_PLATFORM_IDENTIFIED=YES
MOBILE_QUANTUM_SDK_IDENTIFIED=YES
MOBILE_QUANTUM_CREDENTIAL=NOT_SET

REAL_HARDWARE_ACCESS_CONFIRMED=NO
AVAILABLE_REAL_DEVICES=0

GATE_MODEL_HARDWARE_AVAILABLE=NO
VQE_COMPATIBLE_HARDWARE_AVAILABLE=NO

CANDIDATES_LOADED=2/2
CANDIDATE_1_COMPATIBILITY=UNKNOWN
CANDIDATE_2_COMPATIBILITY=UNKNOWN

NATIVE_GATE_SET_AVAILABLE=NO
CONNECTIVITY_AVAILABLE=NO
CALIBRATION_METADATA_AVAILABLE=UNKNOWN

PARAMETERIZED_CIRCUIT_SUPPORTED=UNKNOWN
BATCH_SUBMISSION_SUPPORTED=UNKNOWN
MAX_SHOTS=UNKNOWN

TRANSPILATION_AUDIT=PASS
MEASUREMENT_DECOMPOSITION=PASS

HARDWARE_A_FEASIBLE=NO
HARDWARE_B_FEASIBLE=UNCERTAIN

HARDWARE_SMOKE_JOB_REQUIRED=YES
HARDWARE_SMOKE_JOB_EXECUTED=NO

FORMAL_HARDWARE_RESEARCH_JOBS=0
FORMAL_HARDWARE_VQE_RUNS=0

V05A_RECOMMENDED=NO
BLOCKED_BY_HARDWARE_CREDENTIALS=YES

ALL_TESTS_PASS=YES

V03_HISTORY_IMMUTABLE=PASS
V03C_HISTORY_IMMUTABLE=PASS
V03D_HISTORY_IMMUTABLE=PASS
V04_HISTORY_IMMUTABLE=PASS

SECRET_SCAN_HITS=0
```
