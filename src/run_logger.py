"""
Comprehensive run logger for the JUNO calibration fitter pipeline.
Captures every detail needed for third-party audit and traceability.
"""
from __future__ import annotations

import csv
import json
import os
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np


def _get_git_commit(project_root: str | Path) -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                           text=True, cwd=project_root, timeout=10)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _get_git_branch(project_root: str | Path) -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, text=True, cwd=project_root, timeout=10)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _get_git_dirty(project_root: str | Path) -> bool:
    try:
        r = subprocess.run(["git", "status", "--porcelain"],
                           capture_output=True, text=True, cwd=project_root, timeout=10)
        if r.returncode == 0:
            return len(r.stdout.strip()) > 0
    except Exception:
        pass
    return True


def _get_system_info() -> dict[str, str]:
    return {
        "hostname": socket.gethostname(),
        "user": os.environ.get("USER", os.environ.get("LOGNAME", "unknown")),
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def _lookup_run_info(csv_path: str | Path, run_id: int) -> dict[str, Any]:
    info: dict[str, Any] = {"run": run_id}
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if int(row["RUN"]) == run_id:
                    info["source"] = row.get("Source", "?")
                    info["date"] = row.get("Date", "?")
                    info["x_m"] = float(row.get("X[m]", 0))
                    info["y_m"] = float(row.get("Y[m]", 0))
                    info["z_m"] = float(row.get("Z[m]", 0))
                    info["r_m"] = float(row.get("R[m]", 0))
                    break
    except Exception:
        pass
    return info


def _compute_histogram(energy: np.ndarray, bins: int = 200, range_val: tuple = (0, 3)) -> dict:
    hist, edges = np.histogram(energy, bins=bins, range=range_val)
    return {
        "bin_edges_full": [float(f"{e:.4f}") for e in edges],
        "counts": [int(c) for c in hist],
        "n_bins": len(hist),
        "range": [float(f"{range_val[0]:.2f}"), float(f"{range_val[1]:.2f}")],
    }


def _get_package_versions() -> dict[str, str]:
    versions = {}
    for mod_name in ["numpy", "scipy", "matplotlib", "iminuit", "pandas"]:
        try:
            mod = __import__(mod_name)
            versions[mod_name] = getattr(mod, "__version__", "unknown")
        except ImportError:
            versions[mod_name] = "not_installed"
    return versions

class RunLogger:
    """Collects and writes comprehensive run logs for the pipeline."""

    def __init__(self, output_dir: str | Path, project_root: str | Path,
                 launched_by: str = "script"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.project_root = Path(project_root)
        self.launched_by = launched_by

        self.record: dict[str, Any] = {
            "pipeline_metadata": {
                "launched_by": launched_by,
                "timestamp_start": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "system": _get_system_info(),
                "git": {
                    "commit": _get_git_commit(project_root),
                    "branch": _get_git_branch(project_root),
                    "has_uncommitted_changes": _get_git_dirty(project_root),
                },
                "packages": _get_package_versions(),
                "config_files": {
                    "paths_py": str(project_root / "config" / "paths.py"),
                    "calib_run_csv": str(project_root / "CalibRUN.csv"),
                },
            },
            "sources": [],
            "summary": {},
            "agent_notes": None,
        }

        if launched_by == "agent":
            self.record["agent_notes"] = {
                "agent_name": "", "agent_version": "",
                "workflow_description": "",
                "decisions": [], "exceptions": [],
            }

    def set_agent_info(self, agent_name: str = "", agent_version: str = "",
                       workflow_description: str = "") -> None:
        if self.record["agent_notes"] is None:
            self.record["agent_notes"] = {}
        self.record["agent_notes"]["agent_name"] = agent_name
        self.record["agent_notes"]["agent_version"] = agent_version
        self.record["agent_notes"]["workflow_description"] = workflow_description

    def add_agent_decision(self, decision: str, reason: str) -> None:
        if self.record["agent_notes"] is not None:
            self.record["agent_notes"]["decisions"].append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "decision": decision, "reason": reason,
            })

    def add_agent_exception(self, source: str, exception: str, resolution: str) -> None:
        if self.record["agent_notes"] is not None:
            self.record["agent_notes"]["exceptions"].append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source": source, "exception": exception, "resolution": resolution,
            })

    def add_source_record(self, *, src_name, run_id, e_true, fitter_type,
                          fitter_file, input_path, output_files,
                          event_data=None, fit_results=None,
                          fitter_params=None, elapsed_s=0.0,
                          extra_notes=None) -> None:
        input_path = Path(input_path)
        run_info = _lookup_run_info(self.project_root / "CalibRUN.csv", run_id)

        input_metadata = {
            "path": str(input_path.resolve()),
            "exists": input_path.exists(),
            "size_bytes": input_path.stat().st_size if input_path.exists() else 0,
            "format": input_path.suffix,
        }

        event_stats = {}
        if event_data is not None:
            energy = event_data.get("energy")
            if energy is not None:
                finite = energy[np.isfinite(energy)]
                event_stats = {
                    "total_events": int(len(energy)),
                    "finite_events": int(len(finite)),
                    "energy_min": float(np.min(finite)) if len(finite) > 0 else None,
                    "energy_max": float(np.max(finite)) if len(finite) > 0 else None,
                    "energy_mean": float(np.mean(finite)) if len(finite) > 0 else None,
                    "energy_median": float(np.median(finite)) if len(finite) > 0 else None,
                    "pre_selection_spectrum": _compute_histogram(energy),
                }

        fit_record = {}
        if fit_results is not None:
            for k in ("mu", "sigma", "sigma_over_e_pct", "chi2", "ndf"):
                if k in fit_results:
                    fit_record[k] = fit_results[k]
            if fit_results.get("chi2") is not None and fit_results.get("ndf") is not None:
                fit_record["chi2_over_ndf"] = (
                    f"{fit_results['chi2']:.1f}/{fit_results['ndf']}"
                )

        source_record = {
            "source": src_name, "run": run_id, "e_true_mev": e_true,
            "fitter_type": fitter_type,
            "run_info": run_info,
            "input_data": input_metadata,
            "event_statistics": event_stats,
            "code_version": {
                "fitter_file": str(Path(fitter_file)),
                "fitter_type": fitter_type,
                "git_commit": _get_git_commit(self.project_root),
            },
            "fitter_parameters": fitter_params or {},
            "fit_results": fit_record,
            "output_files": output_files,
            "timing_s": elapsed_s,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if extra_notes:
            source_record["notes"] = extra_notes
        self.record["sources"].append(source_record)

    def set_summary(self, summary: dict[str, Any]) -> None:
        self.record["summary"] = summary

    def finalize(self) -> tuple[Path, Path]:
        self.record["pipeline_metadata"]["timestamp_end"] = (
            time.strftime("%Y-%m-%d %H:%M:%S %Z"))
        json_path = self.output_dir / "run_log.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.record, f, indent=2, ensure_ascii=False, default=str)
            f.write("\n")
        md_path = self.output_dir / "run_log.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._format_markdown())
        print(f"[Log] JSON log: {json_path}")
        print(f"[Log] MD log:  {md_path}")
        return json_path, md_path

    def _format_markdown(self) -> str:
        r = self.record
        lines = []
        m = r["pipeline_metadata"]

        # -- Header --
        lines.append("# Run Log — JUNO Calibration Fitter Pipeline\n")
        lines.append(f"**Launched by**: `{m['launched_by']}`")
        lines.append(f"**Start time**: {m['timestamp_start']}")
        lines.append(f"**End time**:   {m['timestamp_end']}\n")

        # -- System --
        s = m["system"]
        lines.append("## System Information\n")
        lines.append("| Field | Value |\n|-------|-------|")
        lines.append(f"| Hostname | `{s['hostname']}` |")
        lines.append(f"| User | `{s['user']}` |")
        lines.append(f"| Platform | `{s['platform']}` |")
        lines.append(f"| Python | `{s['python_version']}` |\n")

        # -- Git --
        g = m["git"]
        lines.append("## Code Version\n")
        lines.append("| Field | Value |\n|-------|-------|")
        lines.append(f"| Git commit | `{g['commit']}` |")
        lines.append(f"| Git branch | `{g['branch']}` |")
        lines.append(f"| Uncommitted changes | `{g['has_uncommitted_changes']}` |\n")
        if g["has_uncommitted_changes"]:
            lines.append("> ⚠️ Warning: Working tree has uncommitted changes.\n")

        # -- Packages --
        lines.append("## Package Versions\n")
        for name, ver in m["packages"].items():
            lines.append(f"- **{name}**: `{ver}`")
        lines.append("")

        # -- Config --
        lines.append("## Configuration Files\n")
        lines.append("| Config | Path |\n|-------|------|")
        for label, path in m["config_files"].items():
            lines.append(f"| {label} | `{path}` |")
        lines.append("")

        # -- Per-source --
        lines.append("---\n## Per-Source Records\n")
        for src in r["sources"]:
            lines.append(f"### {src['source']} — RUN{src['run']}\n")
            ri = src["run_info"]
            lines.append("| Field | Value |\n|-------|-------|")
            lines.append(f"| Source | {src['source']} |")
            lines.append(f"| Run | {src['run']} |")
            lines.append(f"| Date | {ri.get('date', '?')} |")
            lines.append(f"| Position (X,Y,Z) | ({ri.get('x_m',0):.1f}, {ri.get('y_m',0):.1f}, {ri.get('z_m',0):.1f}) m |")
            lines.append(f"| E_true | {src['e_true_mev']:.4f} MeV |")
            lines.append(f"| Fitter type | `{src['fitter_type']}` |")
            lines.append(f"| Fitter file | `{src['code_version']['fitter_file']}` |")
            lines.append(f"| Git commit | `{src['code_version']['git_commit']}` |\n")

            inp = src["input_data"]
            lines.append("#### Input Data\n")
            lines.append("| Field | Value |\n|-------|-------|")
            sz = inp.get("size_bytes", 0)
            lines.append(f"| File | `{inp['path']}` |")
            lines.append(f"| Size | {sz:,} bytes ({sz/1024:.0f} KB) |")
            lines.append(f"| Format | `{inp['format']}` |\n")

            es = src.get("event_statistics", {})
            if es:
                lines.append("#### Event Statistics\n")
                lines.append("| Field | Value |\n|-------|-------|")
                lines.append(f"| Total events | {es.get('total_events', '?')} |")
                lines.append(f"| Finite events | {es.get('finite_events', '?')} |")
                lines.append(f"| Energy range | {es.get('energy_min','?'):.4f} – {es.get('energy_max','?'):.4f} MeV |")
                lines.append(f"| Energy mean | {es.get('energy_mean','?'):.4f} MeV |")
                lines.append(f"| Energy median | {es.get('energy_median','?'):.4f} MeV |\n")

            fr = src.get("fit_results", {})
            if fr:
                lines.append("#### Fit Results\n")
                lines.append("| Field | Value |\n|-------|-------|")
                lines.append(f"| Mu (μ) | {fr.get('mu','?'):.4f} MeV |")
                lines.append(f"| Sigma (σ) | {fr.get('sigma','?'):.4f} MeV |")
                lines.append(f"| σ/E | {fr.get('sigma_over_e_pct','?'):.2f}% |")
                lines.append(f"| χ²/ndf | {fr.get('chi2_over_ndf','?')} |")
                lines.append(f"| Timing | {src.get('timing_s',0):.1f}s |\n")

            of = src.get("output_files", {})
            if of:
                lines.append("#### Output Files\n")
                for label, path in of.items():
                    lines.append(f"- **{label}**: `{path}`")
                lines.append("")

            if src.get("notes"):
                lines.append(f"**Notes**: {src['notes']}\n")

        # -- Summary --
        sm = r.get("summary", {})
        if sm:
            lines.append("---\n## Summary\n")
            lines.append("| Field | Value |\n|-------|-------|")
            for key, val in sm.items():
                lines.append(f"| {key} | {val} |")
            lines.append("")

        # -- Agent notes --
        an = r.get("agent_notes")
        if an:
            lines.append("---\n## Agent Notes\n")
            lines.append(f"**Agent**: {an.get('agent_name','N/A')} v{an.get('agent_version','N/A')}")
            if an.get("workflow_description"):
                lines.append(f"\n**Workflow**: {an['workflow_description']}")
            lines.append("")
            for d in an.get("decisions", []):
                lines.append(f"- **Decision [{d['timestamp']}]**: {d['decision']} — {d['reason']}")
            for e in an.get("exceptions", []):
                lines.append(f"- **Exception [{e['timestamp']}]**: [{e['source']}] {e['exception']} → {e['resolution']}")
            lines.append("")

        lines.append("---\n*End of run log*")
        return "\n".join(lines) + "\n"
