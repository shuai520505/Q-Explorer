# Q-Explorer V0.4 — Boundary Noise Robustness

## Executive result

V0.4 completed the pre-registered synthetic-noise stress test on the frozen `TASK_F01` Boundary task. The main result is **SHIFTED at N1, N2, and N3**, not a monotonic disappearance of the Boundary. Across all noisy levels, the exploration-set direction remained `RING_WORSE` and the held-out direction remained `RING_BETTER` whenever the complete comparison resolved. However, the most common estimated transition region moved from the N0 reference `[2,3]` to `[1,2]` in 8/15 N1, 7/15 N2, and 8/15 N3 runs.

This is a synthetic NISQ-style robustness result, not a real-device result and not a model of a particular mobile-cloud quantum processor. It does not establish a noise mechanism. It supports testing two targeted paired cases in a separately pre-registered V0.5 hardware study.

## Reproducibility and frozen protocol

- Branch: `v04-boundary-noise-robustness`
- Pre-registration commit: `11b80d0`
- Frozen protocol hash: `5ef21749f16d8b1f33b0c1526bf6189392a05291969394dafd86ae14c36de84c`
- Frozen task: `TASK_F01` (`BOUNDARY_TRANSITION`) from the unchanged V0.3 task suite
- Transfer hypothesis: `H_BOUNDARY_N0`, reconstructed programmatically from the immutable 15-run N0 corpus
- Live model: DeepSeek `deepseek-v4-flash`, `thinking_mode=false`
- Prompt hash: `530641052769c78fd36905fe2ecdffe6b44280657964b0493fbbcf6c1e0ac4af`
- Per-run VQE budget ceiling: 16; 15 independent LLM runs per N1/N2/N3
- V0.3, V0.3-C, and V0.3-D historical hash snapshots: unchanged

The formal protocol, noise values, signal definitions, run seeds, budgets, transfer hypothesis, estimator thresholds, and hardware-candidate selection rules were committed before any formal noisy result was generated.

## Environment

### 1–5. Noise model, interpretation, parameters, freeze, and shots

The backend uses Qiskit Aer density-matrix simulation. It attaches independent depolarizing channels to `ry` and `cx`; because the Ising observables contain only Z/ZZ terms, independent symmetric readout flips are applied analytically as an attenuation factor `(1-2p)^weight`. This preserves exact expectation evaluation and does not introduce finite-shot noise.

| Level | Meaning | 1q depolarizing | 2q depolarizing | symmetric readout | shots |
|---|---|---:|---:|---:|---:|
| N0 | historical ideal | 0 | 0 | 0 | exact/no shots |
| N1 | low synthetic | 0.0005 | 0.005 | 0.005 | exact/no shots |
| N2 | medium synthetic | 0.001 | 0.01 | 0.01 | exact/no shots |
| N3 | high synthetic | 0.002 | 0.02 | 0.02 | exact/no shots |

The error probabilities are transparent stress-test levels. They are not calibration data, do not include relaxation, drift, leakage, crosstalk, or correlated errors, and must not be described as hardware-realistic. N0 used exact statevector expectation while N1–N3 used exact density matrices; neither used finite shots. The method difference is recorded and is a limitation of direct N0/noisy comparison.

The smoke test used one 4-qubit Hamiltonian, one depth-1 linear HEA, and six optimizer iterations. All three NoiseModels executed, recorded their complete configuration, preserved density trace, and differed numerically from ideal. Smoke output was excluded from formal scientific data.

## Boundary outcomes

### 6–9. Outcome and scientific-process validity

`Scientifically validated` requires original Validated Judgment plus a complete action→experiment→evidence chain, boundary probes at at least two exploration depths, a resolved programmatic signature, and complete held-out evidence.

| Level | Original validated | Wilson 95% CI | Scientifically validated | Wilson 95% CI | Retained exact N0 boundary |
|---|---:|---:|---:|---:|---:|
| N0 | 8/15 (0.533) | [0.301, 0.752] | 7/15 (0.467) | [0.248, 0.699] | 7/15 |
| N1 | 14/15 (0.933) | [0.702, 0.988] | 14/15 (0.933) | [0.702, 0.988] | 6/15 |
| N2 | 10/15 (0.667) | [0.417, 0.848] | 8/15 (0.533) | [0.301, 0.752] | 3/15 |
| N3 | 11/15 (0.733) | [0.480, 0.891] | 9/15 (0.600) | [0.357, 0.802] | 4/15 |

V0.3-D established complete action/evidence chains for all eight N0 outcome-validated runs. V0.4 adds the pre-registered requirement that the paired BoundarySignature itself resolve; one N0 validated run lacked a resolved candidate region, hence 7/15 scientifically validated under the stricter V0.4 definition. The historical 8/15 value remains unchanged.

### 10–14. Preserved, shifted, weakened, disappeared, and counterexamples

- **Preserved:** the exact N0 region `[2,3]` was retained by 6/15 N1, 3/15 N2, and 4/15 N3 runs after process validation.
- **Shifted:** the frozen classifier labels N1, N2, and N3 `SHIFTED`. Resolved signatures split between `[2,3]` and `[1,2]`: N1 7 vs 8, N2 5 vs 7 (three unresolved), N3 6 vs 8 (one unresolved). A `[1,2]` result is a frozen `SMALL_SHIFT` of 1.0 depth unit from midpoint 2.5 to 1.5.
- **Weakened:** median noisy/reference effect-magnitude ratios were 0.897 (N1), 0.830 (N2), and 0.928 (N3), all above the frozen 0.70 weakening threshold. Thus `WEAKENED` is not the primary classification.
- **Disappeared:** scientifically validated rates and resolved-signature rates remained above the frozen disappearance floors. `DISAPPEARED` is not supported.
- **New counterexample:** 0/15 at each noise level after same-depth comparison. One initially flagged N2 case was an invalid run without a depth-3 paired comparison; the analysis correctly rejected it rather than promoting an incomparable partial observation to a counterexample.

The increase from N0 to noisy validated rates must not be interpreted as noise improving the physics or the Agent. N0 is historical, condition order assigns different initialization seed groups, and Wilson intervals are broad. The robust observation is task-scoped direction retention plus a mixed `[1,2]`/`[2,3]` location, not monotonic performance improvement.

## Scientific process

### 15. Response to noisy evidence

The frozen feedback diagnostic reports changed subsequent actions in 15/15 N1, 14/15 N2, and 15/15 N3 runs. The remaining N2 run terminated at round 5 after an invalid repeated `BOUNDARY_PROBE`; it consumed eight VQE runs and was retained without replacement. This supports feedback sensitivity but does not establish that the Agent caused the observed shift.

### 16. Revision evidence attribution

No formal hypothesis revision occurred in any of the 45 noisy LLM runs. Accordingly, revision attribution is 0/0 rather than a positive capability result. The output includes an explicit `NO_REVISION_RECORDED` trace event and does not fabricate revision IDs. The analysis recommends a future noise-conditioned revision of the transfer claim, but does not retroactively write one into the Agent history.

### 17–18. Failure modes and process validity under noise

One `INVALID_ACTION` occurred at N2: after four completed actions, the Agent requested an already-tested F3R condition as `BOUNDARY_PROBE`, repair failed, and the run stopped at 8/16 VQE. It remains in the N2 denominator.

The inherited diagnostic emitted `COUNTEREXAMPLE_IGNORED` for 44 complete LLM runs. This is retained as a warning, but it is not confirmed as a new scientific failure mode: the legacy rule treats `BOUNDARY_PROBE` as an invalid response to any preceding Judge `COUNTEREXAMPLE`, even when continued localization is scientifically relevant. The raw label is reported without changing the frozen diagnostic or using it to invalidate runs post hoc.

Scientific-process validity was 15/15 at N1, 12/15 at N2, and 13/15 at N3; combining it with outcome validity produced 14/15, 8/15, and 9/15 scientifically validated rates. N2 is the lowest, partly because of the retained invalid run and unresolved/incomplete signatures. This is not monotonic with noise level.

The single deterministic N2 Rule-Based process reference executed a complete, resolved `[2,3]` process but was outcome-not-validated. It is one trajectory, not 15 independent samples and not a strategy-ranking experiment.

## Interpretation

### 19–24. Robustness, change point, cause, supported/unsupported claims, and revision

The N0 transfer hypothesis is **directionally robust but location-sensitive** under this synthetic noise family. The earliest frozen classification change occurs at N1: `[1,2]` becomes slightly more frequent than `[2,3]`, while the exploration direction and held-out reversal remain unchanged. N2 and N3 repeat that mixed-location pattern; there is no monotonic weakening or disappearance.

The experiment cannot identify a hardware mechanism. The shift may reflect the synthetic gate/readout channels, noisy optimization and initialization-seed allocation, or their interaction with adaptive ordering. Process-validity auditing shows the shift is not explained solely by invalid Agent behavior, but it also cannot prove the Agent caused or correctly mechanistically interpreted it.

Current evidence supports only this scoped statement: **within frozen 4-qubit TASK_F01, exact-density-matrix Aer simulations with the pre-registered synthetic noise levels retain the main topology-effect directions while producing a reproducible mixed transition-location pattern between `[1,2]` and `[2,3]`.** It does not support universal HEA behavior, real-hardware robustness, a causal noise mechanism, monotonic degradation, or LLM superiority.

The Boundary hypothesis should be revised prospectively to include noise condition and location uncertainty: the strongest depth transition may occupy `[1,2]` or `[2,3]` under the tested synthetic environment while the deepest exploration direction remains `RING_WORSE`. This is an analyst recommendation triggered by V0.4, not an evidence-attributed Agent revision.

### 25. Hardware-validation candidates

The deterministic pre-registered selector retained two cases:

1. `V04_TASK_F01_N1_llm_401...`: paired depth 1/2 linear/ring conditions representing a `[2,3] → [1,2]` synthetic shift.
2. `V04_TASK_F01_N3_llm_607...`: paired depth 2/3 linear/ring conditions representing preservation at the highest synthetic level.

Both include the exploration Hamiltonian `HAM_2EEFD1CA529B` and held-out Hamiltonian `HAM_29268115BC00`. Their falsification condition is a hardware contrast that is unresolved or has a different direction/transition region. These are candidates only; V0.4 used no real quantum hardware.

`V05_RECOMMENDED=YES` because a systematic small shift and a high-noise preserved case both satisfy the pre-registered hardware-entry cases. V0.5 must be a separate pre-registration and should not begin automatically.

## Figures and artifacts

- Figure 1: scientifically validated Boundary rate with Wilson intervals
- Figure 2: programmatic shift categories by level
- Figure 3: new counterexample rate by level

No cross-level trajectory figure was generated because N0/N1/N2/N3 are independent research runs; joining them into one longitudinal Agent trajectory would fabricate provenance.

Machine-readable results are in `results/v04/`; raw formal records are in `traces/v04/`. `boundary_robustness_summary.json` is the authoritative aggregate, while `boundary_signatures.jsonl` preserves every run-level signature.
