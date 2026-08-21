# Run Log — JUNO Calibration Fitter Pipeline (v2.0)

**Run ID**: `20260821T141704_d65cd093`
**Status**: `completed`
**Launched by**: `script`
**Start (UTC)**: 2026-08-21T06:17:04.416199Z
**End (UTC)**:   2026-08-21T06:17:14.420498Z

**Command**: `pipeline/run_fit_all.py`
**Exit code**: `0`

## System Information

| Field | Value |
|-------|-------|
| Hostname | `user-Super-Server` |
| User | `lin` |
| Platform | `Linux-6.8.0-136-generic-x86_64-with-glibc2.39` |
| Python | `3.12.3` |

## Code Version

| Field | Value |
|-------|-------|
| Git commit | `32fd3cc8ba8f1107c03a3e61ca19d6cfb40f6f3b` |
| Git branch | `main` |
| Uncommitted changes | `True` |

> Warning: Working tree has uncommitted changes.

## Package Versions

- **numpy**: `2.5.2`
- **scipy**: `1.18.0`
- **matplotlib**: `3.11.1`
- **iminuit**: `2.32.0`
- **pandas**: `3.0.5`

## Configuration Files

| Config | Path | SHA-256 |
|-------|------|--------|
| paths_py | `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/config/paths.py` | `477ee5913819bf39...` |
| calib_run_csv | `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/CalibRUN.csv` | `84d39f499b8b560a...` |
| requirements_txt | `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/requirements.txt` | `0351e588f90a087a...` |

---
## Per-Source Records

### [OK] Ge68 — RUN12370

| Field | Value |
|-------|-------|
| Status | success |
| Source | Ge68 |
| Run | 12370 |
| Date | 2025-12-17 |
| Position | (0.0, 0.0, 0.0) m |
| E_true | 0.8845 MeV |
| Fitter | `fast` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/lustrefs/juno26/users/zhaorz/Calib/ReProd26B/singles_selection/Results_fromFinalcorrection/npz/Run12370_SelectionResult.npz` |
| Size | 2,622,422 bytes |
| SHA-256 | `875b1662638ca16a...` |

#### Events

| Field | Value |
|-------|-------|
| Total | 109212 |
| Energy range | 0.0000 - 11.6899 MeV |

#### Fit Results

| Field | Value |
|-------|-------|
| Mu | 0.9102 MeV |
| Sigma/E | 3.54% |
| Chi2/ndf | 600.2/358 |
| Time | 5.5s |

#### Output Files

- **result_npz**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_141704/results/RUN12370_Ge68.npz` (SHA-256: `0247b0f4584e...`)
- **figure**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_141704/figures/RUN12370_Ge68.pdf` (SHA-256: `f89e72fb71bb...`)

### [OK] Cs137 — RUN12295

| Field | Value |
|-------|-------|
| Status | success |
| Source | Cs137 |
| Run | 12295 |
| Date | 2025-12-16 |
| Position | (0.0, 0.0, 0.0) m |
| E_true | 0.6620 MeV |
| Fitter | `fast` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/lustrefs/juno26/users/zhaorz/Calib/ReProd26B/singles_selection/Results_fromFinalcorrection/npz/Run12295_SelectionResult.npz` |
| Size | 3,028,142 bytes |
| SHA-256 | `57103a9631b0f699...` |

#### Events

| Field | Value |
|-------|-------|
| Total | 126117 |
| Energy range | 0.0000 - 11.5701 MeV |

#### Fit Results

| Field | Value |
|-------|-------|
| Mu | 0.6034 MeV |
| Sigma/E | 4.40% |
| Chi2/ndf | 226.2/122 |
| Time | 0.8s |

#### Output Files

- **result_npz**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_141704/results/RUN12295_Cs137.npz` (SHA-256: `edea029c1b4f...`)
- **figure**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_141704/figures/RUN12295_Cs137.pdf` (SHA-256: `6f417aa9b1d3...`)

### [OK] Mn54 — RUN12247

| Field | Value |
|-------|-------|
| Status | success |
| Source | Mn54 |
| Run | 12247 |
| Date | 2025-12-15 |
| Position | (0.0, 0.0, 0.0) m |
| E_true | 0.8350 MeV |
| Fitter | `fast` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/lustrefs/juno26/users/zhaorz/Calib/ReProd26B/singles_selection/Results_fromFinalcorrection/npz/Run12247_SelectionResult.npz` |
| Size | 1,004,750 bytes |
| SHA-256 | `83ce89e9420ff3c8...` |

#### Events

| Field | Value |
|-------|-------|
| Total | 41809 |
| Energy range | 0.0000 - 9.1776 MeV |

#### Fit Results

| Field | Value |
|-------|-------|
| Mu | 0.7780 MeV |
| Sigma/E | 3.92% |
| Chi2/ndf | 148.6/111 |
| Time | 0.7s |

#### Output Files

- **result_npz**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_141704/results/RUN12247_Mn54.npz` (SHA-256: `d2059fed24e8...`)
- **figure**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_141704/figures/RUN12247_Mn54.pdf` (SHA-256: `1245fb475989...`)

### [OK] Co60 — RUN12216

| Field | Value |
|-------|-------|
| Status | success |
| Source | Co60 |
| Run | 12216 |
| Date | 2025-12-15 |
| Position | (0.0, 0.0, 0.0) m |
| E_true | 2.5060 MeV |
| Fitter | `fast` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/lustrefs/juno26/users/zhaorz/Calib/ReProd26B/singles_selection/Results_fromFinalcorrection/npz/Run12216_SelectionResult.npz` |
| Size | 2,580,518 bytes |
| SHA-256 | `317a6e726591fbe0...` |

#### Events

| Field | Value |
|-------|-------|
| Total | 107466 |
| Energy range | 0.0000 - 9.1696 MeV |

#### Fit Results

| Field | Value |
|-------|-------|
| Mu | 2.4113 MeV |
| Sigma/E | 2.34% |
| Chi2/ndf | 254.8/183 |
| Time | 0.8s |

#### Output Files

- **result_npz**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_141704/results/RUN12216_Co60.npz` (SHA-256: `48b340520a55...`)
- **figure**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_141704/figures/RUN12216_Co60.pdf` (SHA-256: `db445a693d8e...`)

### [OK] K40 — RUN9632

| Field | Value |
|-------|-------|
| Status | success |
| Source | K40 |
| Run | 9632 |
| Date | 2025-08-25 |
| Position | (0.0, 0.0, 0.0) m |
| E_true | 1.4610 MeV |
| Fitter | `fast` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/lustrefs/juno26/users/zhaorz/Calib/ReProd26B/singles_selection/Results_fromFinalcorrection/npz/Run9632_SelectionResult.npz` |
| Size | 703,046 bytes |
| SHA-256 | `21da388b126da04f...` |

#### Events

| Field | Value |
|-------|-------|
| Total | 29238 |
| Energy range | 0.0000 - 14.0353 MeV |

#### Fit Results

| Field | Value |
|-------|-------|
| Mu | 1.4158 MeV |
| Sigma/E | 2.98% |
| Chi2/ndf | 154.4/145 |
| Time | 0.6s |

#### Output Files

- **result_npz**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_141704/results/RUN9632_K40.npz` (SHA-256: `41ccea147e2e...`)
- **figure**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_141704/figures/RUN9632_K40.pdf` (SHA-256: `c70026993911...`)

---
## Summary

| Field | Value |
|-------|-------|
| total_sources_configured | 5 |
| total_sources_fitted | 5 |
| total_time_s | 9.7 |
| sources | Ge68, Cs137, Mn54, Co60, K40 |
| output_directory | /datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_141704 |

---
*End of run log*
