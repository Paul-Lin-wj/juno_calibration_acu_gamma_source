# Run Log — JUNO Calibration Fitter Pipeline (v2.0)

**Run ID**: `20260825T090333_b763ee07`
**Status**: `completed`
**Launched by**: `script`
**Start (UTC)**: 2026-08-25T01:03:33.505747Z
**End (UTC)**:   2026-08-25T01:03:39.984217Z

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
| Git commit | `ff0a2011e464729c856b7a532b8ba4a0bf4eb5b3` |
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
| paths_py | `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/config/paths.py` | `aa272c242f264da7...` |
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
| File | `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_esd2npz/output/20260825_084459/results/selection_npz/Run12370_SelectionResult.npz` |
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
| Time | 4.1s |

#### Output Files

- **result_npz**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260825_090333/results/RUN12370_Ge68.npz` (SHA-256: `0247b0f4584e...`)
- **figure**: `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260825_090333/figures/RUN12370_Ge68.pdf` (SHA-256: `21b8058f78de...`)

### [SKIP] Cs137 — RUN12295

| Field | Value |
|-------|-------|
| Status | skipped |
| Source | Cs137 |
| Run | 12295 |
| Date | 2025-12-16 |
| Position | (0.0, 0.0, 0.0) m |
| E_true | 0.6620 MeV |
| Fitter | `fast` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_esd2npz/output/20260825_084459/results/selection_npz/Run12295_SelectionResult.npz` |
| Size | 0 bytes |
| SHA-256 | `...` |

### [SKIP] Mn54 — RUN12247

| Field | Value |
|-------|-------|
| Status | skipped |
| Source | Mn54 |
| Run | 12247 |
| Date | 2025-12-15 |
| Position | (0.0, 0.0, 0.0) m |
| E_true | 0.8350 MeV |
| Fitter | `fast` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_esd2npz/output/20260825_084459/results/selection_npz/Run12247_SelectionResult.npz` |
| Size | 0 bytes |
| SHA-256 | `...` |

### [SKIP] Co60 — RUN12216

| Field | Value |
|-------|-------|
| Status | skipped |
| Source | Co60 |
| Run | 12216 |
| Date | 2025-12-15 |
| Position | (0.0, 0.0, 0.0) m |
| E_true | 2.5060 MeV |
| Fitter | `fast` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_esd2npz/output/20260825_084459/results/selection_npz/Run12216_SelectionResult.npz` |
| Size | 0 bytes |
| SHA-256 | `...` |

### [SKIP] K40 — RUN9632

| Field | Value |
|-------|-------|
| Status | skipped |
| Source | K40 |
| Run | 9632 |
| Date | 2025-08-25 |
| Position | (0.0, 0.0, 0.0) m |
| E_true | 1.4610 MeV |
| Fitter | `fast` |

#### Input Data

| Field | Value |
|-------|-------|
| File | `/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_esd2npz/output/20260825_084459/results/selection_npz/Run9632_SelectionResult.npz` |
| Size | 0 bytes |
| SHA-256 | `...` |

---
## Summary

| Field | Value |
|-------|-------|
| total_sources_configured | 5 |
| total_sources_fitted | 1 |
| total_time_s | 4.6 |
| sources | Ge68 |
| output_directory | /datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter/output/20260825_090333 |

---
## Audit (end-of-run completeness)

| Check | Result |
|-------|--------|
| code/ snapshot files | `53` |
| code all sha256 match | `True` |
| outputs all present | `True` |
| log files all present | `True` |
| **audit passed** | **`True`** |

---
*End of run log*
