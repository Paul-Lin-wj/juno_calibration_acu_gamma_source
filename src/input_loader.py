from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

RUN_PATTERN = re.compile(r"RUN(\d+)")


def _optional_float_array(frame: pd.DataFrame, column: str) -> Optional[np.ndarray]:
    if column not in frame.columns:
        return None
    return pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)


def _csv_metadata(frame: pd.DataFrame) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if "runid" in frame.columns:
        runids = pd.to_numeric(frame["runid"], errors="coerce").dropna().unique()
        if len(runids) == 1:
            metadata["runid"] = int(runids[0])
    if "position_tag" in frame.columns:
        tags = frame["position_tag"].dropna().astype(str).unique()
        if len(tags) == 1:
            metadata["position_tag"] = tags[0]
    return metadata


def normalize_event_input(input_path: str | Path, source: str = "") -> dict[str, Any]:
    path = Path(input_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

    path_str = str(path)
    source_upper = source.upper()
    if path.suffix.lower() == ".npz":
        with np.load(path, allow_pickle=False) as data:
            energy_key = "fast_omilrec_energy" if source_upper in {"AMC", "O16"} and "fast_omilrec_energy" in data else "calib_omilrec_energy"
            if energy_key not in data:
                raise RuntimeError(f"Missing required energy key '{energy_key}' in {path}. Available keys: {list(data.keys())}")
            return {
                "energy": np.asarray(data[energy_key], dtype=float),
                "x": np.asarray(data["calib_omilrec_x"], dtype=float) if "calib_omilrec_x" in data else None,
                "y": np.asarray(data["calib_omilrec_y"], dtype=float) if "calib_omilrec_y" in data else None,
                "z": np.asarray(data["calib_omilrec_z"], dtype=float) if "calib_omilrec_z" in data else None,
                "metadata": {},
                "input_path": path_str,
            }

    if path_str.endswith(".csv") or path_str.endswith(".csv.gz"):
        frame = pd.read_csv(path)
        if "rec_energy" not in frame.columns:
            raise RuntimeError(f"CSV input is missing required column 'rec_energy': {path}")
        energy = pd.to_numeric(frame["rec_energy"], errors="coerce").to_numpy(dtype=float)
        return {
            "energy": energy,
            "x": _optional_float_array(frame, "x_mm"),
            "y": _optional_float_array(frame, "y_mm"),
            "z": _optional_float_array(frame, "z_mm"),
            "metadata": _csv_metadata(frame),
            "input_path": path_str,
        }

    raise RuntimeError(f"Unsupported input format: {path}")


def infer_sample_label(
    input_path: str | Path,
    metadata: Optional[dict[str, Any]] = None,
    explicit_label: str = "",
    run_id: Optional[int] = None,
) -> str:
    if explicit_label:
        return explicit_label
    if run_id is not None:
        return f"RUN{int(run_id)}"
    metadata = metadata or {}
    if "runid" in metadata:
        return f"RUN{int(metadata['runid'])}"
    if "position_tag" in metadata:
        return str(metadata["position_tag"])

    path = Path(input_path)
    match = RUN_PATTERN.search(path.name)
    if match:
        return f"RUN{int(match.group(1))}"
    if path.name.endswith(".csv.gz"):
        return path.name[:-7]
    return path.stem
