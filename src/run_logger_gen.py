
import csv, hashlib, json, os, platform, socket, subprocess, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import numpy as np

SCHEMA_VERSION = "2.0"


def _sha256(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return "unavailable"


def _file_info(path):
    p = Path(path)
    info = {"path": str(p.resolve()), "exists": p.exists()}
    if p.exists():
        info["size_bytes"] = p.stat().st_size
        info["sha256"] = _sha256(p)
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
