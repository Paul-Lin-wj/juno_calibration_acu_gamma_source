# Run Log — JUNO Calibration Fitter Pipeline

**Launched by**: `script`
**Start time**: 2026-08-21 10:57:59 CST
**End time**:   2026-08-21 10:58:08 CST

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
| Git commit | `5e1cdabc2457cc6f99936d9ca34ccecbb269a3b3` |
| Git branch | `main` |
| Uncommitted changes | `True` |

> ⚠️ Warning: Working tree has uncommitted changes.

## Package Versions

- **numpy**: `2.5.2`
- **scipy**: `1.18.0`
- **matplotlib**: `3.11.1`
- **iminuit**: `2.32.0`
- **pandas**: `3.0.5`

## Configuration Files

| Config | Path |
|-------|------|
| paths_py | `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/config/paths.py` |
| calib_run_csv | `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/CalibRUN.csv` |

---
## Per-Source Records

### Ge68 — RUN9541

| Field | Value |
|-------|-------|
| Source | Ge68 |
| Run | 9541 |
| Date | 2025-08-24 |
| Position (X,Y,Z) | (0.0, 0.0, 0.0) m |
| E_true | 0.8845 MeV |
| Fitter type | `fast` |
| Fitter file | `src/FastGe68Fitter.py` |
| Git commit | `5e1cdabc2457cc6f99936d9ca34ccecbb269a3b3` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/lustrefs/juno26/users/zhaorz/Calib/ReProd26B/singles_selection/Results_fromFinalcorrection/npz/Run9541_SelectionResult.npz` |
| Size | 554,510 bytes (542 KB) |
| Format | `.npz` |

#### Event Statistics

| Field | Value |
|-------|-------|
| Total events | 23049 |
| Finite events | 23049 |
| Energy range | 0.0000 – 3.7519 MeV |
| Energy mean | 0.8230 MeV |
| Energy median | 0.8871 MeV |

#### Fit Results

| Field | Value |
|-------|-------|
| Mu (μ) | 0.9056 MeV |
| Sigma (σ) | 0.0314 MeV |
| σ/E | 3.47% |
| χ²/ndf | 380.4/351 |
| Timing | 4.9s |

#### Output Files

- **result_npz**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_105759/results/RUN9541_Ge68.npz`
- **figure**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_105759/figures/RUN9541_Ge68.pdf`

### Cs137 — RUN9600

| Field | Value |
|-------|-------|
| Source | Cs137 |
| Run | 9600 |
| Date | 2025-08-25 |
| Position (X,Y,Z) | (0.0, 0.0, 0.0) m |
| E_true | 0.6620 MeV |
| Fitter type | `fast` |
| Fitter file | `src/FastSourceFitter.py` |
| Git commit | `5e1cdabc2457cc6f99936d9ca34ccecbb269a3b3` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/lustrefs/juno26/users/zhaorz/Calib/ReProd26B/singles_selection/Results_fromFinalcorrection/npz/Run9600_SelectionResult.npz` |
| Size | 3,124,166 bytes (3051 KB) |
| Format | `.npz` |

#### Event Statistics

| Field | Value |
|-------|-------|
| Total events | 130118 |
| Finite events | 130118 |
| Energy range | 0.0000 – 5.2042 MeV |
| Energy mean | 0.5558 MeV |
| Energy median | 0.5937 MeV |

#### Fit Results

| Field | Value |
|-------|-------|
| Mu (μ) | 0.5992 MeV |
| Sigma (σ) | 0.0258 MeV |
| σ/E | 4.31% |
| χ²/ndf | 222.2/124 |
| Timing | 0.8s |

#### Output Files

- **result_npz**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_105759/results/RUN9600_Cs137.npz`
- **figure**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_105759/figures/RUN9600_Cs137.pdf`

### Mn54 — RUN9624

| Field | Value |
|-------|-------|
| Source | Mn54 |
| Run | 9624 |
| Date | 2025-08-25 |
| Position (X,Y,Z) | (0.0, 0.0, 0.0) m |
| E_true | 0.8350 MeV |
| Fitter type | `fast` |
| Fitter file | `src/FastSourceFitter.py` |
| Git commit | `5e1cdabc2457cc6f99936d9ca34ccecbb269a3b3` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/lustrefs/juno26/users/zhaorz/Calib/ReProd26B/singles_selection/Results_fromFinalcorrection/npz/Run9624_SelectionResult.npz` |
| Size | 1,283,942 bytes (1254 KB) |
| Format | `.npz` |

#### Event Statistics

| Field | Value |
|-------|-------|
| Total events | 53442 |
| Finite events | 53442 |
| Energy range | 0.0000 – 4.3135 MeV |
| Energy mean | 0.6878 MeV |
| Energy median | 0.7650 MeV |

#### Fit Results

| Field | Value |
|-------|-------|
| Mu (μ) | 0.7734 MeV |
| Sigma (σ) | 0.0296 MeV |
| σ/E | 3.83% |
| χ²/ndf | 140.7/108 |
| Timing | 0.7s |

#### Output Files

- **result_npz**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_105759/results/RUN9624_Mn54.npz`
- **figure**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_105759/figures/RUN9624_Mn54.pdf`

### Co60 — RUN9591

| Field | Value |
|-------|-------|
| Source | Co60 |
| Run | 9591 |
| Date | 2025-08-24 |
| Position (X,Y,Z) | (0.0, 0.0, 0.0) m |
| E_true | 2.5060 MeV |
| Fitter type | `fast` |
| Fitter file | `src/FastSourceFitter.py` |
| Git commit | `5e1cdabc2457cc6f99936d9ca34ccecbb269a3b3` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/lustrefs/juno26/users/zhaorz/Calib/ReProd26B/singles_selection/Results_fromFinalcorrection/npz/Run9591_SelectionResult.npz` |
| Size | 2,694,134 bytes (2631 KB) |
| Format | `.npz` |

#### Event Statistics

| Field | Value |
|-------|-------|
| Total events | 112200 |
| Finite events | 112200 |
| Energy range | 0.0000 – 4.7868 MeV |
| Energy mean | 2.1822 MeV |
| Energy median | 2.3821 MeV |

#### Fit Results

| Field | Value |
|-------|-------|
| Mu (μ) | 2.4062 MeV |
| Sigma (σ) | 0.0545 MeV |
| σ/E | 2.26% |
| χ²/ndf | 244.1/182 |
| Timing | 0.8s |

#### Output Files

- **result_npz**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_105759/results/RUN9591_Co60.npz`
- **figure**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_105759/figures/RUN9591_Co60.pdf`

### K40 — RUN9632

| Field | Value |
|-------|-------|
| Source | K40 |
| Run | 9632 |
| Date | 2025-08-25 |
| Position (X,Y,Z) | (0.0, 0.0, 0.0) m |
| E_true | 1.4610 MeV |
| Fitter type | `fast` |
| Fitter file | `src/FastSourceFitter.py` |
| Git commit | `5e1cdabc2457cc6f99936d9ca34ccecbb269a3b3` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/lustrefs/juno26/users/zhaorz/Calib/ReProd26B/singles_selection/Results_fromFinalcorrection/npz/Run9632_SelectionResult.npz` |
| Size | 703,046 bytes (687 KB) |
| Format | `.npz` |

#### Event Statistics

| Field | Value |
|-------|-------|
| Total events | 29238 |
| Finite events | 29238 |
| Energy range | 0.0000 – 14.0353 MeV |
| Energy mean | 0.5214 MeV |
| Energy median | 0.1907 MeV |

#### Fit Results

| Field | Value |
|-------|-------|
| Mu (μ) | 1.4158 MeV |
| Sigma (σ) | 0.0422 MeV |
| σ/E | 2.98% |
| χ²/ndf | 154.4/145 |
| Timing | 0.6s |

#### Output Files

- **result_npz**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_105759/results/RUN9632_K40.npz`
- **figure**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_105759/figures/RUN9632_K40.pdf`

---
## Summary

| Field | Value |
|-------|-------|
| total_sources_configured | 5 |
| total_sources_fitted | 5 |
| total_time_s | 8.9 |
| total_time_min | 0.1 |
| sources | Ge68, Cs137, Mn54, Co60, K40 |
| output_directory | /datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260821_105759 |

---
*End of run log*
