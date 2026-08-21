"""
Comprehensive run logger for the JUNO calibration fitter pipeline.
Implements audit-grade logging with SHA-256 fingerprints, status tracking,
context manager safety, and agent workflow recording.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

SCHEMA_VERSION = "2.0"


def sha256_file(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return "unavailable"


def file_info(path):
    p = Path(path)
    info = {"path": str(p.resolve()), "exists": p.exists()}
    if p.exists():
        info["size_bytes"] = p.stat().st_size
        info["sha256"] = sha256_file(p)
    else:
        info["size_bytes"] = 0
        info["sha256"] = None
    return info


def _get_git_commit(project_root):
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                           text=True, cwd=project_root, timeout=10)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _get_git_branch(project_root):
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, text=True, cwd=project_root, timeout=10)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _get_git_dirty(project_root):
    try:
        r = subprocess.run(["git", "status", "--porcelain"],
                           capture_output=True, text=True, cwd=project_root, timeout=10)
        if r.returncode == 0:
            return len(r.stdout.strip()) > 0
    except Exception:
        pass
    return True


def _get_pip_freeze():
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "freeze", "--all"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return [line for line in r.stdout.strip().split("\n") if line and not line.startswith("#")]
    except Exception:
        pass
    return []


def _get_system_info():
    return {
        "hostname": socket.gethostname(),
        "user": os.environ.get("USER", os.environ.get("LOGNAME", "unknown")),
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def _lookup_run_info(csv_path, run_id):
    info = {"run": run_id}
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


def _compute_histogram(energy, bins=200, range_val=(0, 3)):
    hist, edges = np.histogram(energy, bins=bins, range=range_val)
    return {
        "bin_edges_full": [float(f"{e:.4f}") for e in edges],
        "counts": [int(c) for c in hist],
        "n_bins": len(hist),
        "range": [float(f"{range_val[0]:.2f}"), float(f"{range_val[1]:.2f}")],
    }


def _get_package_versions():
    versions = {}
    for mod_name in ["numpy", "scipy", "matplotlib", "iminuit", "pandas"]:
        try:
            mod = __import__(mod_name)
            versions[mod_name] = getattr(mod, "__version__", "unknown")
        except ImportError:
            versions[mod_name] = "not_installed"
    return versions


def _now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _now_local():
    return time.strftime("%Y-%m-%d %H:%M:%S %Z")


class RunLogger:
    """Collects and writes comprehensive run logs.

    Use as a context manager to ensure finalize() is called even on failure:

        with RunLogger(output_dir, project_root) as logger:
            logger.add_source_record(...)
    """

    def __init__(self, output_dir, project_root, launched_by="script"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.project_root = Path(project_root)
        self.launched_by = launched_by
        self._finalized = False
        self._console_lines = []

        run_id = f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"

        cfg_files = {
            "paths_py": str(self.project_root / "config" / "paths.py"),
            "calib_run_csv": str(self.project_root / "CalibRUN.csv"),
            "requirements_txt": str(self.project_root / "requirements.txt"),
        }
        config_snapshot = {}
        for label, path in cfg_files.items():
            p = Path(path)
            if p.exists():
                config_snapshot[label] = {
                    "path": str(p), "sha256": sha256_file(p), "size_bytes": p.stat().st_size
                }
            else:
                config_snapshot[label] = {"path": str(p), "sha256": None, "size_bytes": 0}

        self.record = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "status": "running",
            "pipeline_metadata": {
                "launched_by": launched_by,
                "timestamp_start_utc": _now_utc(),
                "timestamp_start_local": _now_local(),
                "system": _get_system_info(),
                "git": {
                    "commit": _get_git_commit(self.project_root),
                    "branch": _get_git_branch(self.project_root),
                    "has_uncommitted_changes": _get_git_dirty(self.project_root),
                },
                "packages": _get_package_versions(),
                "pip_freeze": _get_pip_freeze(),
                "command": [],
                "exit_code": None,
                "config_files": cfg_files,
                "config_snapshot": config_snapshot,
            },
            "sources": [],
            "errors": [],
            "summary": {},
            "agent_notes": None,
        }

        if launched_by == "agent":
            self.record["agent_notes"] = {
                "agent_name": "", "agent_version": "",
                "workflow_description": "",
                "decisions": [], "exceptions": [],
            }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.record["status"] = "failed"
            self.add_error("pipeline", str(exc_val), "pipeline encountered an unhandled exception")
            import traceback
            tb_path = self.output_dir / "traceback.log"
            try:
                with open(tb_path, "w") as f:
                    traceback.print_exception(exc_type, exc_val, exc_tb, file=f)
                print(f"[Log] Traceback saved to: {tb_path}", flush=True)
            except Exception:
                pass
        self.finalize()

    def set_agent_info(self, agent_name="", agent_version="", workflow_description=""):
        if self.record["agent_notes"] is None:
            self.record["agent_notes"] = {
                "agent_name": "", "agent_version": "",
                "workflow_description": "",
                "decisions": [], "exceptions": [],
            }
        self.record["agent_notes"]["agent_name"] = agent_name
        self.record["agent_notes"]["agent_version"] = agent_version
        self.record["agent_notes"]["workflow_description"] = workflow_description

    def add_agent_decision(self, decision, reason):
        if self.record["agent_notes"] is not None:
            self.record["agent_notes"]["decisions"].append({
                "timestamp_utc": _now_utc(), "decision": decision, "reason": reason,
            })

    def add_agent_exception(self, source, exception, resolution):
        if self.record["agent_notes"] is not None:
            self.record["agent_notes"]["exceptions"].append({
                "timestamp_utc": _now_utc(), "source": source,
                "exception": exception, "resolution": resolution,
            })

    def add_error(self, source, message, resolution=""):
        self.record["errors"].append({
            "timestamp_utc": _now_utc(), "source": source,
            "message": message, "resolution": resolution,
        })

    def write_console(self, text):
        self._console_lines.append(text)

    def record_command(self, command_list):
        """Record the exact command used to launch the pipeline."""
        self.record["pipeline_metadata"]["command"] = [str(c) for c in command_list]

    def set_exit_code(self, code):
        """Record the process exit code (0 = success)."""
        self.record["pipeline_metadata"]["exit_code"] = int(code)

    def flush_console_log(self):
        if not self._console_lines:
            return
        console_path = self.output_dir / "console.log"
        try:
            with open(console_path, "w", encoding="utf-8") as f:
                f.write("\n".join(self._console_lines) + "\n")
            print(f"[Log] Console log: {console_path}", flush=True)
        except Exception as e:
            print(f"[Log] Failed to write console log: {e}", flush=True)

    class ConsoleTee:
        """Tee stream: writes to both a target stream (e.g. sys.stdout) and the logger.

        Usage:
            with contextlib.redirect_stdout(logger.ConsoleTee(sys.stdout, logger)):
                ...
        """

        def __init__(self, target, logger):
            self._target = target
            self._logger = logger

        def write(self, data):
            self._target.write(data)
            self._logger.write_console(data.rstrip("\n"))

        def flush(self):
            self._target.flush()

    def add_source_record(self, *, src_name, run_id, e_true, fitter_type,
                          fitter_file, input_path, output_files,
                          event_data=None, fit_results=None,
                          fitter_params=None, elapsed_s=0.0,
                          status="success", error_message=None, extra_notes=None):
        input_path = Path(input_path)
        run_info = _lookup_run_info(self.project_root / "CalibRUN.csv", run_id)
        input_metadata = file_info(input_path)
        input_metadata["format"] = input_path.suffix

        mc_template_info = {}
        if fitter_params and "template_path" in fitter_params:
            mc_template_info = file_info(fitter_params["template_path"])

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
                fit_record["chi2_over_ndf"] = f"{fit_results['chi2']:.1f}/{fit_results['ndf']}"

        output_files_info = {}
        for label, path in (output_files or {}).items():
            output_files_info[label] = file_info(path)

        params_clean = {}
        if fitter_params:
            for k, v in fitter_params.items():
                if k != "template_path":
                    params_clean[k] = v

        source_record = {
            "status": status,
            "source": src_name, "run": run_id, "e_true_mev": e_true,
            "fitter_type": fitter_type,
            "run_info": run_info,
            "input_data": input_metadata,
            "mc_template": mc_template_info,
            "event_statistics": event_stats,
            "code_version": {
                "fitter_file": str(Path(fitter_file)),
                "fitter_type": fitter_type,
                "git_commit": _get_git_commit(self.project_root),
            },
            "fitter_parameters": params_clean,
            "fit_results": fit_record,
            "output_files": output_files_info,
            "timing_s": elapsed_s,
            "timestamp_utc": _now_utc(),
        }
        if error_message:
            source_record["error_message"] = error_message
        if extra_notes:
            source_record["notes"] = extra_notes
        self.record["sources"].append(source_record)

    def save_config_snapshot(self, extra_configs=None):
        snap = {}
        for label, path in self.record["pipeline_metadata"]["config_files"].items():
            p = Path(path)
            if p.exists():
                try:
                    snap[label] = p.read_text(encoding="utf-8")
                except Exception:
                    snap[label] = f"# ERROR: could not read {p}"
        if extra_configs:
            for label, content in extra_configs.items():
                snap[label] = content
        snap_path = self.output_dir / "config_snapshot.json"
        try:
            with open(snap_path, "w", encoding="utf-8") as f:
                json.dump(snap, f, indent=2, ensure_ascii=False)
                f.write("\n")
            print(f"[Log] Config snapshot: {snap_path}", flush=True)
        except Exception as e:
            print(f"[Log] Failed to write config snapshot: {e}", flush=True)

    def set_summary(self, summary):
        self.record["summary"] = summary

    def finalize(self):
        if self._finalized:
            return self.output_dir / "run_log.json", self.output_dir / "run_log.md"
        self._finalized = True

        if self.record["status"] == "running":
            n_failed = sum(1 for s in self.record["sources"] if s.get("status") == "failed")
            n_skipped = sum(1 for s in self.record["sources"] if s.get("status") == "skipped")
            if n_failed > 0:
                self.record["status"] = "partial_failure"
            else:
                self.record["status"] = "completed"

        self.record["pipeline_metadata"]["timestamp_end_utc"] = _now_utc()
        self.record["pipeline_metadata"]["timestamp_end_local"] = _now_local()

        json_path = self.output_dir / "run_log.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.record, f, indent=2, ensure_ascii=False, default=str)
            f.write("\n")

        md_path = self.output_dir / "run_log.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._format_markdown())

        self.flush_console_log()

        print(f"[Log] JSON log: {json_path}", flush=True)
        print(f"[Log] MD log:  {md_path}", flush=True)
        return json_path, md_path

    def _format_markdown(self):
        r = self.record
        lines = []
        m = r["pipeline_metadata"]

        lines.append(f"# Run Log — JUNO Calibration Fitter Pipeline (v{r.get('schema_version','?')})\n")
        lines.append(f"**Run ID**: `{r.get('run_id', '?')}`")
        lines.append(f"**Status**: `{r['status']}`")
        lines.append(f"**Launched by**: `{m['launched_by']}`")
        lines.append(f"**Start (UTC)**: {m.get('timestamp_start_utc', '?')}")
        lines.append(f"**End (UTC)**:   {m.get('timestamp_end_utc', '?')}")

        if m.get("command"):
            lines.append("")
            lines.append(f"**Command**: `{' '.join(m['command'])}`")
            if m.get("exit_code") is not None:
                lines.append(f"**Exit code**: `{m['exit_code']}`")
        lines.append("")

        s = m["system"]
        lines.append("## System Information\n")
        lines.append("| Field | Value |\n|-------|-------|")
        lines.append(f"| Hostname | `{s['hostname']}` |")
        lines.append(f"| User | `{s['user']}` |")
        lines.append(f"| Platform | `{s['platform']}` |")
        lines.append(f"| Python | `{s['python_version']}` |\n")

        g = m["git"]
        lines.append("## Code Version\n")
        lines.append("| Field | Value |\n|-------|-------|")
        lines.append(f"| Git commit | `{g['commit']}` |")
        lines.append(f"| Git branch | `{g['branch']}` |")
        lines.append(f"| Uncommitted changes | `{g['has_uncommitted_changes']}` |\n")
        if g["has_uncommitted_changes"]:
            lines.append("> Warning: Working tree has uncommitted changes.\n")

        lines.append("## Package Versions\n")
        for name, ver in m["packages"].items():
            lines.append(f"- **{name}**: `{ver}`")
        lines.append("")

        lines.append("## Configuration Files\n")
        lines.append("| Config | Path | SHA-256 |\n|-------|------|--------|")
        for label, path in m["config_files"].items():
            cs = m.get("config_snapshot", {}).get(label, {})
            sha = (cs.get("sha256", "") or "")[:16] + "..."
            lines.append(f"| {label} | `{path}` | `{sha}` |")
        lines.append("")

        lines.append("---\n## Per-Source Records\n")
        for src in r["sources"]:
            tag = {"success": "OK", "failed": "FAIL", "skipped": "SKIP"}.get(src.get("status", "?"), "?")
            lines.append(f"### [{tag}] {src['source']} — RUN{src['run']}\n")
            ri = src["run_info"]
            lines.append("| Field | Value |\n|-------|-------|")
            lines.append(f"| Status | {src.get('status', '?')} |")
            lines.append(f"| Source | {src['source']} |")
            lines.append(f"| Run | {src['run']} |")
            lines.append(f"| Date | {ri.get('date', '?')} |")
            lines.append(f"| Position | ({ri.get('x_m',0):.1f}, {ri.get('y_m',0):.1f}, {ri.get('z_m',0):.1f}) m |")
            lines.append(f"| E_true | {src['e_true_mev']:.4f} MeV |")
            lines.append(f"| Fitter | `{src['fitter_type']}` |\n")

            inp = src["input_data"]
            lines.append("#### Input Data\n")
            lines.append("| Field | Value |\n|-------|-------|")
            lines.append(f"| File | `{inp['path']}` |")
            sz = inp.get("size_bytes", 0)
            sha_inp = (inp.get("sha256") or "")[:16]
            lines.append(f"| Size | {sz:,} bytes |")
            lines.append(f"| SHA-256 | `{sha_inp}...` |\n")

            es = src.get("event_statistics", {})
            if es:
                lines.append("#### Events\n")
                lines.append("| Field | Value |\n|-------|-------|")
                lines.append(f"| Total | {es.get('total_events','?')} |")
                lines.append(f"| Energy range | {es.get('energy_min','?'):.4f} - {es.get('energy_max','?'):.4f} MeV |\n")

            fr = src.get("fit_results", {})
            if fr:
                lines.append("#### Fit Results\n")
                lines.append("| Field | Value |\n|-------|-------|")
                lines.append(f"| Mu | {fr.get('mu','?'):.4f} MeV |")
                lines.append(f"| Sigma/E | {fr.get('sigma_over_e_pct','?'):.2f}% |")
                lines.append(f"| Chi2/ndf | {fr.get('chi2_over_ndf','?')} |")
                lines.append(f"| Time | {src.get('timing_s',0):.1f}s |\n")

            of = src.get("output_files", {})
            if of:
                lines.append("#### Output Files\n")
                for label, info in of.items():
                    sha_out = (info.get("sha256") or "")[:12]
                    lines.append(f"- **{label}**: `{info['path']}` (SHA-256: `{sha_out}...`)")
                lines.append("")

            if src.get("notes"):
                lines.append(f"**Notes**: {src['notes']}\n")

        # Summary
        sm = r.get("summary", {})
        if sm:
            lines.append("---\n## Summary\n")
            lines.append("| Field | Value |\n|-------|-------|")
            for key, val in sm.items():
                lines.append(f"| {key} | {val} |")
            lines.append("")

        # Agent notes
        an = r.get("agent_notes")
        if an:
            lines.append("---\n## Agent Notes\n")
            lines.append(f"**Agent**: {an.get('agent_name','N/A')} v{an.get('agent_version','N/A')}")
            if an.get("workflow_description"):
                lines.append(f"\n**Workflow**: {an['workflow_description']}")
            lines.append("")
            for d in an.get("decisions", []):
                lines.append(f"- Decision [{d['timestamp_utc']}]: {d['decision']} — {d['reason']}")
            for e in an.get("exceptions", []):
                lines.append(f"- Exception [{e['timestamp_utc']}]: [{e['source']}] {e['exception']} -> {e['resolution']}")
            lines.append("")

        # Errors
        if r.get("errors"):
            lines.append("---\n## Errors\n")
            for err in r["errors"]:
                lines.append(f"- [{err['source']}] {err['message']} ({err['resolution']})")
            lines.append("")

        lines.append("---\n*End of run log*")
        return "\n".join(lines) + "\n"