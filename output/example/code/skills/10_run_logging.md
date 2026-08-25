# Skill: Run Logging & Workflow Traceability

## Description

This skill defines the **mandatory logging requirements** for every pipeline run. Whether launched by a human via `bash run_pipeline.sh` or by an AI agent, every run **must** produce a complete, auditable log in the output directory. The log enables third-party reviewers to trace exactly what code was run, on what data, with what results, and why any decisions were made.

---

## Why This Matters

Every calibration fit is a **scientific measurement** that may be used for:
- Energy non-linearity correction
- Detector response modeling
- Publication-quality results
- Collaboration review

Without a complete log, a result is **not reproducible** and **not citable**.

---

## Log Output Files

Each pipeline run produces the following files in the output directory:

| File | Format | Purpose |
|------|--------|---------|
| `run_log.json` | JSON | Structured, machine-readable. For programmatic analysis and comparison. |
| `run_log.md` | Markdown | Human-readable formatted report. For quick visual inspection. |
| `config_snapshot.json` | JSON | Full content of `config/paths.py`, `CalibRUN.csv`, `requirements.txt` at run time. |
| `console.log` | Text | Captured console output (optional, enabled via `logger.write_console()`). |
| `traceback.log` | Text | Full traceback if the pipeline fails (only on errors). |
| `code/` | Code tree | **Complete code snapshot** of the project at run time + `code/sha256.json` fingerprints. |
| `audit` (in `run_log.json`) | JSON | **End-of-run completeness audit**: code snapshot byte-identity + deliverable presence. |

All files are generated automatically by `pipeline/run_fit_all.py` via the `RunLogger` class in `src/run_logger.py`. The logger is a **context manager** — `finalize()` is guaranteed to run even if the pipeline fails partway through.

### End-of-Run Audit (automatic, do not skip)

Every run ends with:

1. **`snapshot_code_full()`** — copies the complete code tree (config/fitters/
   pipeline/skills/smx_ana/src/tests + root files; excludes only .venv/output/
   TMP/__pycache__/.git/pyc) into `code/` with `code/sha256.json`;
2. **`run_audit()`** — verifies (a) every code file exists in `code/` and is
   byte-identical to the working tree (missing/mismatched/extra detected),
   (b) every deliverable exists (per-source result NPZ + fit PDF, ENL plot,
   config_snapshot);
3. **`finalize()`** re-checks the four log files themselves and rewrites both
   logs with the final `audit` record (`audit.passed`).

On audit failure: **script mode exits with code 3**; **agent mode prints
`[AUDIT] WARNING`** and the run status becomes `audit-failed`. In both cases
the failure detail (missing/mismatched file lists) is in
`run_log.json -> audit` — agents MUST state the audit result in their report.

---

## Log Contents

Every run log **must** contain the following sections:

### 1. Pipeline Metadata

| Field | Description | Example |
|-------|-------------|---------|
| `schema_version` | Log format version | `"2.0"` |
| `run_id` | Unique run identifier (timestamp + UUID) | `20260821T132751_8b263f0c` |
| `status` | Run outcome | `"completed"`, `"partial_failure"`, `"failed"` |
| `launched_by` | How the run was started | `"script"` or `"agent"` |
| `timestamp_start_utc` | ISO 8601 UTC start time | `2026-08-21T05:27:51.123Z` |
| `timestamp_end_utc` | ISO 8601 UTC end time | `2026-08-21T05:27:59.456Z` |

### Content Fingerprints (SHA-256)

Every file referenced by the log is fingerprinted with SHA-256:

| What | Where |
|------|-------|
| Input NPZ data | `sources[].input_data.sha256` |
| MC template NPZ | `sources[].mc_template.sha256` |
| Output files | `sources[].output_files.*.sha256` |
| `config/paths.py` | `pipeline_metadata.config_snapshot.paths_py.sha256` |
| `CalibRUN.csv` | `pipeline_metadata.config_snapshot.calib_run_csv.sha256` |
| `requirements.txt` | `pipeline_metadata.config_snapshot.requirements_txt.sha256` |

This allows a third party to verify they are looking at **byte-identical** inputs and outputs.

### 2. System Information

| Field | Description |
|-------|-------------|
| `hostname` | Machine hostname |
| `user` | OS user who ran the pipeline |
| `platform` | Full OS/platform string |
| `python_version` | Python interpreter version |
| `python_executable` | Full path to Python binary |

### 3. Code Version (Git)

| Field | Description |
|-------|-------------|
| `commit` | Full git commit hash (`git rev-parse HEAD`) |
| `branch` | Git branch name |
| `has_uncommitted_changes` | Whether the working tree is dirty |

> ⚠️ **If `has_uncommitted_changes` is `True`**, the log includes a warning. This means the code may differ from the committed version. Always commit changes before a production run.

### 4. Package Versions

All key Python package versions are recorded: `numpy`, `scipy`, `matplotlib`, `iminuit`, `pandas`.
The full `pip freeze --all` output is also stored in `pipeline_metadata.pip_freeze`.

### 5. Per-Source Records

For each source in `SOURCES`, the log records:

| Category | Fields |
|----------|--------|
| **Status** | `success`, `skipped`, or `failed` (+ `error_message` when failed) |
| **Run info** | Source name, run number, date, position (X, Y, Z, R), E_true |
| **Input data** | Full file path, file size, **SHA-256 hash**, format |
| **MC template** | Template NPZ path, size, SHA-256 |
| **Event statistics** | Total events, finite events, energy range (min/max/mean/median), **pre-selection spectrum** (200-bin histogram) |
| **Code version** | Fitter file path, fitter type, git commit |
| **Fit results** | μ (MeV), σ (MeV), σ/E (%), χ², ndf, χ²/ndf, timing |
| **Output files** | Paths, sizes, SHA-256 hashes of result NPZ and fit figures |

### 6. Summary

Total sources configured, total sources fitted, total execution time, list of sources, output directory.

### 7. Agent Notes (only when `launched_by = "agent"`)

| Field | Description |
|-------|-------------|
| `agent_name` | Name of the AI agent |
| `agent_version` | Version identifier |
| `workflow_description` | Free-text description of what the agent did |
| `decisions` | List of `{timestamp, decision, reason}` entries |
| `exceptions` | List of `{timestamp, source, exception, resolution}` entries |

### 8. Audit (end-of-run completeness, always present)

| Field | Description |
|-------|-------------|
| `code_snapshot.n_files` | Number of files in `code/` snapshot |
| `code_snapshot.all_match` | Every code file byte-identical to working tree |
| `code_snapshot.missing/mismatched/extra` | File lists (should be empty) |
| `outputs.all_present` / `missing` | Deliverable presence check |
| `finalized_files.all_present` | The four log files themselves exist |
| `passed` | Overall audit result (all of the above) |

---

## MANDATORY: Agent Run Requirements

When an **AI agent** drives the pipeline, the agent **must**:

### 1. Identify itself (CLI method)

Use the command-line arguments when calling `pipeline/run_fit_all.py`:

```bash
python pipeline/run_fit_all.py \
    --launched-by agent \
    --agent-name "DeepSeek Agent" \
    --agent-version "v4-flash" \
    --agent-workflow "Full pipeline run with 5 sources at CD center"
```

Or programmatically via the logger API:

```python
logger.set_agent_info(
    agent_name="DeepSeek Agent",
    agent_version="v4-flash",
    workflow_description="Full pipeline run with all 5 sources at CD center",
)
```

### 2. Log every decision

Any non-trivial choice the agent makes must be recorded:

```python
logger.add_agent_decision(
    decision="Skip O16 source",
    reason="O16/AmC data requires correlate_selection path not configured in default SOURCES",
)
logger.add_agent_decision(
    decision="Use FastGe68Fitter for Ge68",
    reason="Fast version is 50-100x faster with identical results (verified by compare_fast_vs_classic.py)",
)
```

### 3. Log every exception

Any error encountered and how it was resolved:

```python
logger.add_agent_exception(
    source="Cs137 RUN9600",
    exception="Data file not found at expected path",
    resolution="Checked alternate path, found file at /data/backup/Run9600_SelectionResult.npz, updated DATA_INPUT_PATH",
)
```

### 4. Do NOT modify the log after the run

The log is a **record of fact**. It must be written once by `logger.finalize()` and never edited afterward.

### 5. Include the output directory path in the final response

When an agent completes a run, it **must** report the output directory path so the user can find the results and logs.

### 6. Report the audit result

The agent **must** state in its final response whether the end-of-run audit
passed, quoting `[AUDIT] PASSED` or `[AUDIT] WARNING` from the console and the
`audit.passed` value in `run_log.json`. On `[AUDIT] WARNING`, the agent must
list the missing/mismatched files and state that the outputs were produced
with a failed completeness audit.

---

## Log Template (Agent Response)

When reporting results to a user, the agent **must** include this information:

```
## Run Complete

**Output directory**: `/path/to/output/YYYYMMDD_HHMMSS/`

### Summary
- Sources fitted: Ge68, Cs137, Mn54, Co60, K40
- Total time: 8.9s
- Log files: run_log.json, run_log.md

### Results
| Source | μ (MeV) | σ/E (%) | χ²/ndf |
|--------|:-------:|:-------:|:------:|
| Ge68 | 0.9056 | 3.47% | 380/351 |
| Cs137 | 0.5992 | 4.31% | 222/124 |
| ... | ... | ... | ... |

### Key Files
- Fit results: `output/.../results/`
- Fit figures: `output/.../figures/`
- Summary plot: `output/.../enl_style_resolution.png`
- Log (JSON): `output/.../run_log.json`
- Log (MD): `output/.../run_log.md`

### Code Version
- Git commit: `5e1cdabc2457cc6f99936d9ca34ccecbb269a3b3`
- Branch: `main`
```

---

## Verifying the Log

After any run, verify the log contains all required fields:

```bash
# Check JSON log structure
python -c "
import json
with open('output/YYYYMMDD_HHMMSS/run_log.json') as f:
    r = json.load(f)
print('Sections:', list(r.keys()))
print('Sources:', len(r['sources']))
for s in r['sources']:
    print(f'  {s[\"source\"]}: mu={s[\"fit_results\"][\"mu\"]:.4f}')
"

# Check Markdown log readability
head -5 output/YYYYMMDD_HHMMSS/run_log.md
```

## Smoke Test

Run `bash tests/smoke_test.sh` to verify the logging infrastructure is intact. The smoke test checks:
- Module imports
- Config file integrity
- Python package availability

It does **not** run the full pipeline (requires data access).