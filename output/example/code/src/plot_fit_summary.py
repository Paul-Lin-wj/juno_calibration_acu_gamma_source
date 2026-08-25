#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import glob
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from plot_style import apply_summary_plot_style

apply_summary_plot_style()
# plt.rcParams["axes.unicode_minus"] = False

# Compatibility shim: some result NPZ files were written with newer NumPy
# and pickle references `numpy._core.*`, while older runtime environments
# only expose `numpy.core.*`.
sys.modules.setdefault("numpy._core", np.core)
sys.modules.setdefault("numpy._core.multiarray", np.core.multiarray)
sys.modules.setdefault("numpy._core.numeric", np.core.numeric)


RUN_PATTERN = re.compile(r"RUN(\d+)")
POSITION_TAG_PATTERN = re.compile(r"(X-?\d+_Y-?\d+_Z-?\d+)")

SOURCE_COLORS = {
    "Ge68": "#1f77b4",
    "Cs137": "#ff7f0e",
    "Co60": "#2ca02c",
    "Mn54": "#d62728",
    "K40": "#9467bd",
    "AmC": "#8c564b",
}

SOURCE_MARKERS = {
    "Ge68": "o",
    "Cs137": "s",
    "Co60": "^",
    "Mn54": "D",
    "K40": "v",
    "AmC": "P",
}

SOURCE_LINESTYLES = {
    "Ge68": "-",
    "Cs137": "--",
    "Co60": "-.",
    "Mn54": ":",
    "K40": (0, (3, 1, 1, 1)),
    "AmC": (0, (5, 2)),
}

VERSION_COLORS = [
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#8c564b",
]

VERSION_MARKERS = ["o", "s", "^", "D", "v", "P"]
EVENT_KEYS = [
    ("calib_omilrec_x", "rec x [mm]"),
    ("calib_omilrec_y", "rec y [mm]"),
    ("calib_omilrec_z", "rec z [mm]"),
    ("calib_omilrec_energy", "energy"),
]
MAX_SCATTER_POINTS = 200000
DIFF_OUTLIER_THRESHOLDS = {
    "calib_omilrec_x": 1000.0,
    "calib_omilrec_y": 1000.0,
    "calib_omilrec_z": 1000.0,
    "calib_omilrec_energy": 0.1,
}
DIFF_UNITS = {
    "calib_omilrec_x": "mm",
    "calib_omilrec_y": "mm",
    "calib_omilrec_z": "mm",
    "calib_omilrec_energy": "MeV",
}
PANEL_LABEL_SIZE = 13
PANEL_TICK_SIZE = 11
PANEL_TEXT_SIZE = 10
PANEL_SUPTITLE_SIZE = 14
SUMMARY_REFERENCE_Z_M = 17.2


def _coerce_float(text, default=0.0):
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _value_from_row(row, candidates, default=0.0):
    for key in candidates:
        if key in row and str(row[key]).strip() != "":
            return _coerce_float(row[key], default=default)
    return default


def _run_from_row(row):
    for key in ["RUN", "run", "runid", "Run", "RunID"]:
        if key in row and str(row[key]).strip() != "":
            return int(float(row[key]))
    raise ValueError("missing run id")


def _dict_row_is_mm(row):
    keys = set(row)
    if {"X[m]", "Y[m]", "Z[m]"} & keys:
        return False
    if {"X[mm]", "Y[mm]", "Z[mm]", "x_mm", "y_mm", "z_mm"} & keys:
        return True
    return True


def _add_run_info_entry(run_info, run, x_value, y_value, z_value, source, values_are_mm=False):
    if values_are_mm:
        x_value /= 1000.0
        y_value /= 1000.0
        z_value /= 1000.0
    run_info[run] = {
        "x": x_value,
        "y": y_value,
        "z": z_value,
        "r": float(np.sqrt(x_value * x_value + y_value * y_value + z_value * z_value)),
        "source": source,
    }


def _load_run_info_table(csv_path, default_source=""):
    run_info = {}
    with open(csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return run_info
        for row in reader:
            try:
                run = _run_from_row(row)
            except (KeyError, ValueError):
                continue
            x_value = _value_from_row(row, ["X[m]", "X[mm]", "x_mm", "x", "X"], default=0.0)
            y_value = _value_from_row(row, ["Y[m]", "Y[mm]", "y_mm", "y", "Y"], default=0.0)
            z_value = _value_from_row(row, ["Z[m]", "Z[mm]", "z_mm", "z", "Z"], default=None)
            if z_value is None:
                continue
            source = str(row.get("Source", "") or default_source or "Unknown")
            _add_run_info_entry(
                run_info,
                run,
                x_value,
                y_value,
                z_value,
                source,
                values_are_mm=_dict_row_is_mm(row),
            )
    return run_info


def _load_run_info_position_file(path, default_source=""):
    run_info = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = re.split(r"[\s,]+", stripped)
            if len(parts) < 4:
                continue
            try:
                run = int(float(parts[0]))
                x_value = float(parts[1])
                y_value = float(parts[2])
                z_value = float(parts[3])
            except ValueError:
                continue
            _add_run_info_entry(
                run_info,
                run,
                x_value,
                y_value,
                z_value,
                str(default_source or "Unknown"),
                values_are_mm=True,
            )
    return run_info


def load_run_info(csv_path, default_source=""):
    run_info = _load_run_info_table(csv_path, default_source=default_source)
    if run_info:
        return run_info
    return _load_run_info_position_file(csv_path, default_source=default_source)


def extract_run_number(path):
    match = RUN_PATTERN.search(os.path.basename(path))
    return int(match.group(1)) if match else -1


def extract_position_tag(path):
    match = POSITION_TAG_PATTERN.search(os.path.basename(path))
    return match.group(1) if match else ""


def extract_xyz_from_position_tag(position_tag):
    match = re.search(r"X(-?\d+)_Y(-?\d+)_Z(-?\d+)", position_tag)
    if not match:
        return None
    x_mm = float(match.group(1))
    y_mm = float(match.group(2))
    z_mm = float(match.group(3))
    return {
        "x": x_mm / 1000.0,
        "y": y_mm / 1000.0,
        "z": z_mm / 1000.0,
    }


def unpack_npz_value(value):
    if isinstance(value, np.ndarray) and value.shape == ():
        value = value.item()
    return value


def extract_param(npz_data, key):
    if key not in npz_data.files:
        return None
    value = unpack_npz_value(npz_data[key])
    if isinstance(value, dict):
        if "value" in value:
            return float(value["value"])
        return None
    if np.isscalar(value):
        return float(value)
    return None


def extract_mu_and_resolution(npz_path):
    with np.load(npz_path, allow_pickle=True) as data:
        mu = extract_param(data, "center_gauss")
        sigma = extract_param(data, "sigma_gauss")

        if mu is None or sigma is None:
            mu = extract_param(data, "center_gauss_6_13")
            sigma = extract_param(data, "sigma_gauss_6_13")

        if mu is None or sigma is None or mu == 0.0:
            return None

        resolution = sigma / mu * 100.0
        return {
            "mu": mu,
            "resolution_percent": resolution,
        }


def collect_summary(results_dir, run_info, default_source="", max_radius_m=None):
    rows_by_source = defaultdict(list)
    files = sorted(glob.glob(os.path.join(results_dir, "*.npz")))

    for path in files:
        run = extract_run_number(path)
        position_tag = extract_position_tag(path)
        sample_key = ""
        source = ""
        x_value = 0.0
        y_value = 0.0
        z_value = None
        radius_value = None

        if run >= 0:
            if run not in run_info:
                print(f"[Warning] Run {run} not found in run-info CSV, skipped")
                continue
            source = run_info[run]["source"]
            x_value = run_info[run]["x"]
            y_value = run_info[run]["y"]
            z_value = run_info[run]["z"]
            radius_value = run_info[run]["r"]
            sample_key = f"RUN{run}"
        elif position_tag:
            xyz = extract_xyz_from_position_tag(position_tag)
            if xyz is None:
                print(f"[Warning] Failed to parse X/Y/Z from position tag in: {path}")
                continue
            x_value = xyz["x"]
            y_value = xyz["y"]
            z_value = xyz["z"]
            radius_value = float(np.sqrt(x_value * x_value + y_value * y_value + z_value * z_value))
            source = str(default_source or "Unknown")
            sample_key = position_tag
        else:
            print(f"[Warning] Failed to parse run or position tag from: {path}")
            continue

        if max_radius_m is not None and float(radius_value) > float(max_radius_m):
            continue

        fit_result = extract_mu_and_resolution(path)
        if fit_result is None:
            label = sample_key or f"run {run}"
            print(f"[Warning] {label}: failed to extract mu/sigma from {path}")
            continue

        rows_by_source[source].append(
            {
                "run": run,
                "sample_key": sample_key,
                "position_tag": position_tag,
                "x": x_value,
                "y": y_value,
                "z": z_value,
                "r": radius_value,
                "mu": fit_result["mu"],
                "resolution_percent": fit_result["resolution_percent"],
            }
        )

    for source in rows_by_source:
        rows_by_source[source].sort(key=lambda row: row["z"])
    return rows_by_source


def find_data_dir_from_results_dir(results_dir):
    return os.path.dirname(os.path.normpath(results_dir))


def collect_event_arrays(data_dir):
    run_arrays = {}
    files = sorted(glob.glob(os.path.join(data_dir, "SelectionResult_RUN*.npz")))
    for path in files:
        run = extract_run_number(path)
        if run < 0:
            continue
        with np.load(path) as data:
            if not all(key in data.files for key, _ in EVENT_KEYS):
                print(f"[Warning] Missing event keys in {path}, skipped")
                continue
            run_arrays[run] = {key: np.asarray(data[key]) for key, _ in EVENT_KEYS}
    return run_arrays


def build_event_comparison(version_data_map):
    version_labels = list(version_data_map.keys())
    if len(version_labels) != 2:
        return None

    left_label, right_label = version_labels
    left_runs = version_data_map[left_label]
    right_runs = version_data_map[right_label]
    common_runs = sorted(set(left_runs.keys()) & set(right_runs.keys()))
    if not common_runs:
        return None

    merged = {key: [[], []] for key, _ in EVENT_KEYS}
    used_runs = []
    total_events = 0

    for run in common_runs:
        left_data = left_runs[run]
        right_data = right_runs[run]
        lengths = []
        for key, _ in EVENT_KEYS:
            lengths.append(len(left_data[key]))
            lengths.append(len(right_data[key]))
        n_event = min(lengths)
        if n_event <= 0:
            continue
        if len(set(lengths)) != 1:
            print(
                f"[Warning] Run {run}: event counts differ between versions, trimming to {n_event}",
                flush=True,
            )

        for key, _ in EVENT_KEYS:
            merged[key][0].append(left_data[key][:n_event])
            merged[key][1].append(right_data[key][:n_event])
        used_runs.append(run)
        total_events += n_event

    if total_events <= 0:
        return None

    merged_arrays = {}
    for key, _ in EVENT_KEYS:
        merged_arrays[key] = (
            np.concatenate(merged[key][0]),
            np.concatenate(merged[key][1]),
        )

    return {
        "labels": (left_label, right_label),
        "runs": used_runs,
        "total_events": total_events,
        "arrays": merged_arrays,
    }


def maybe_downsample(x_values, y_values, max_points=MAX_SCATTER_POINTS):
    if len(x_values) <= max_points:
        return x_values, y_values
    rng = np.random.default_rng(12345)
    index = rng.choice(len(x_values), size=max_points, replace=False)
    index.sort()
    return x_values[index], y_values[index]


def make_event_comparison_plot(comparison, output_path):
    left_label, right_label = comparison["labels"]
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    axes = axes.ravel()

    for axis, (key, axis_label) in zip(axes, EVENT_KEYS):
        x_values, y_values = comparison["arrays"][key]
        x_plot, y_plot = maybe_downsample(x_values, y_values)
        axis.scatter(
            x_plot,
            y_plot,
            s=3,
            alpha=0.15,
            color="#1f77b4",
            edgecolors="none",
            rasterized=True,
        )
        diag_min = min(np.min(x_plot), np.min(y_plot))
        diag_max = max(np.max(x_plot), np.max(y_plot))
        axis.plot([diag_min, diag_max], [diag_min, diag_max], color="k", linestyle="--", linewidth=1.0)
        axis.set_xlabel(f"{left_label} {axis_label}", fontsize=PANEL_LABEL_SIZE)
        axis.set_ylabel(f"{right_label} {axis_label}", fontsize=PANEL_LABEL_SIZE)
        axis.tick_params(axis="both", which="major", labelsize=PANEL_TICK_SIZE)
        axis.grid(True, alpha=0.3)

    fig.suptitle(
        f"Event-by-event comparison: {left_label} vs {right_label}\n"
        f"runs={len(comparison['runs'])}, events={comparison['total_events']}",
        fontsize=PANEL_SUPTITLE_SIZE,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"[Output] Saved plot: {output_path}")


def compute_diff_stats(diff_values, outlier_threshold):
    abs_diff = np.abs(diff_values)
    return {
        "mean": float(np.mean(diff_values)),
        "rms": float(np.std(diff_values)),
        "p997_abs": float(np.percentile(abs_diff, 99.7)),
        "outlier_fraction": float(np.mean(abs_diff > outlier_threshold)),
    }


def make_event_difference_plot(comparison, output_path):
    left_label, right_label = comparison["labels"]
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    axes = axes.ravel()

    for axis, (key, axis_label) in zip(axes, EVENT_KEYS):
        left_values, right_values = comparison["arrays"][key]
        diff_values = right_values - left_values
        threshold = DIFF_OUTLIER_THRESHOLDS[key]
        unit = DIFF_UNITS[key]
        stats = compute_diff_stats(diff_values, threshold)

        abs_diff = np.abs(diff_values)
        hist_limit = max(
            np.percentile(abs_diff, 99.9),
            stats["p997_abs"] * 1.1,
            threshold * 1.1,
            1e-6,
        )
        axis.hist(
            diff_values,
            bins=150,
            range=(-hist_limit, hist_limit),
            histtype="step",
            linewidth=1.5,
            color="#1f77b4",
        )
        axis.axvline(0.0, color="k", linestyle="--", linewidth=1.0)
        axis.set_xlabel(f"{right_label} - {left_label} {axis_label}", fontsize=PANEL_LABEL_SIZE)
        axis.set_ylabel("Events", fontsize=PANEL_LABEL_SIZE)
        axis.tick_params(axis="both", which="major", labelsize=PANEL_TICK_SIZE)
        axis.ticklabel_format(axis="y", style="sci", scilimits=(3, 3), useMathText=True)
        axis.grid(True, alpha=0.3)
        stats_text = (
            f"mean = {stats['mean']:.4g} {unit}\n"
            f"RMS = {stats['rms']:.4g} {unit}\n"
            f"abs(diff) p99.7 = {stats['p997_abs']:.4g} {unit}\n"
            f"outlier fraction\n"
            f"threshold {threshold:g} {unit}: {100.0 * stats['outlier_fraction']:.3f}%"
        )
        axis.text(
            0.97,
            0.97,
            stats_text,
            transform=axis.transAxes,
            ha="right",
            va="top",
            fontsize=PANEL_TEXT_SIZE,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.75, edgecolor="0.7"),
        )

    fig.suptitle(
        f"Difference distributions: {right_label} - {left_label}\n"
        f"runs={len(comparison['runs'])}, events={comparison['total_events']}",
        fontsize=PANEL_SUPTITLE_SIZE,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"[Output] Saved plot: {output_path}")


def make_delta_z_energy_correlation_plot(comparison, output_path):
    left_label, right_label = comparison["labels"]
    left_z, right_z = comparison["arrays"]["calib_omilrec_z"]
    left_e, right_e = comparison["arrays"]["calib_omilrec_energy"]

    dz = right_z - left_z
    de = right_e - left_e
    dz_plot, de_plot = maybe_downsample(dz, de)

    fig, axis = plt.subplots(figsize=(7, 5.5))
    axis.scatter(
        dz_plot,
        de_plot,
        s=4,
        alpha=0.18,
        color="#1f77b4",
        edgecolors="none",
        rasterized=True,
    )
    axis.axhline(0.0, color="k", linestyle="--", linewidth=1.0)
    axis.axvline(0.0, color="k", linestyle="--", linewidth=1.0)
    axis.set_xlabel(f"{right_label} - {left_label} rec z [mm]", fontsize=14)
    axis.set_ylabel(f"{right_label} - {left_label} energy [MeV]", fontsize=14)
    axis.tick_params(axis="both", which="major", labelsize=12)
    axis.grid(True, alpha=0.3)
    axis.set_title("Correlation between z difference and energy difference", fontsize=15)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"[Output] Saved plot: {output_path}")


def make_selected_z_scatter_plot(comparison, output_path):
    left_label, right_label = comparison["labels"]
    left_z, right_z = comparison["arrays"]["calib_omilrec_z"]
    left_e, right_e = comparison["arrays"]["calib_omilrec_energy"]

    select = (left_e > 1.05 * right_e) & (right_e > 1.0)
    if not np.any(select):
        print("[Warning] No events satisfy baseline-energy selection for z diagnostic plot")
        return

    left_z_sel = left_z[select]
    right_z_sel = right_z[select]
    left_z_plot, right_z_plot = maybe_downsample(left_z_sel, right_z_sel)

    diag_min = min(np.min(left_z_plot), np.min(right_z_plot))
    diag_max = max(np.max(left_z_plot), np.max(right_z_plot))

    fig, axis = plt.subplots(figsize=(7, 5.5))
    axis.scatter(
        left_z_plot,
        right_z_plot,
        s=5,
        alpha=0.22,
        color="#d62728",
        edgecolors="none",
        rasterized=True,
    )
    axis.plot([diag_min, diag_max], [diag_min, diag_max], color="k", linestyle="--", linewidth=1.0)
    axis.set_xlabel(f"{left_label} rec z [mm]", fontsize=14)
    axis.set_ylabel(f"{right_label} rec z [mm]", fontsize=14)
    axis.tick_params(axis="both", which="major", labelsize=12)
    axis.grid(True, alpha=0.3)
    axis.set_title(
        f"rec z for events with {left_label} E > 1.05 x {right_label} E and {right_label} E > 1 MeV\n"
        f"selected events = {np.count_nonzero(select)}",
        fontsize=14,
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"[Output] Saved plot: {output_path}")


def parse_results_dir_arg(arg_text):
    if "=" not in arg_text:
        raise ValueError(
            f"Invalid --results-dir '{arg_text}'. Use the form label=path."
        )
    label, path = arg_text.split("=", 1)
    label = label.strip()
    path = path.strip()
    if not label or not path:
        raise ValueError(
            f"Invalid --results-dir '{arg_text}'. Use the form label=path."
        )
    return label, path


def make_baseline_lookup(rows_by_source, y_key):
    lookup = {}
    for source, rows in rows_by_source.items():
        for row in rows:
            lookup[(source, row["sample_key"])] = row[y_key]
    return lookup


def add_reference_z_lines(axis, *, include_label=False):
    for z_value in (-SUMMARY_REFERENCE_Z_M, SUMMARY_REFERENCE_Z_M):
        axis.axvline(
            z_value,
            color="#666666",
            linestyle="--",
            linewidth=1.0,
            alpha=0.75,
            label="z = +/-17.2 m" if include_label and z_value < 0 else None,
        )


def make_plot(version_rows_map, version_order, y_key, y_label, title, output_path):
    has_comparison = len(version_order) > 1
    if has_comparison:
        fig, (top_axis, bottom_axis) = plt.subplots(
            2,
            1,
            figsize=(7, 6.5),
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1], "hspace": 0.05},
        )
    else:
        fig, top_axis = plt.subplots(figsize=(7, 5))
        bottom_axis = None

    for version_index, version_label in enumerate(version_order):
        rows_by_source = version_rows_map[version_label]
        version_color = VERSION_COLORS[version_index % len(VERSION_COLORS)]
        version_marker = VERSION_MARKERS[version_index % len(VERSION_MARKERS)]
        for source, rows in sorted(rows_by_source.items()):
            if not rows:
                continue
            z_values = [row["z"] for row in rows]
            y_values = [row[y_key] for row in rows]
            top_axis.plot(
                z_values,
                y_values,
                marker=version_marker,
                color=version_color,
                linestyle=SOURCE_LINESTYLES.get(source, "-"),
                linewidth=1.0,
                markersize=5,
                label=f"{version_label}: {source}",
            )

    top_axis.set_ylabel(y_label)
    top_axis.set_title(title)
    add_reference_z_lines(top_axis, include_label=True)
    top_axis.grid(True, alpha=0.3)
    top_axis.legend(framealpha=0.8, fontsize=12)

    if has_comparison:
        baseline_label = version_order[0]
        baseline_lookup = make_baseline_lookup(version_rows_map[baseline_label], y_key)
        has_ratio_points = False
        bottom_axis.axhline(1.0, color="k", linestyle="--", linewidth=1.0)
        for version_index, version_label in enumerate(version_order[1:], start=1):
            rows_by_source = version_rows_map[version_label]
            version_color = VERSION_COLORS[version_index % len(VERSION_COLORS)]
            version_marker = VERSION_MARKERS[version_index % len(VERSION_MARKERS)]
            for source, rows in sorted(rows_by_source.items()):
                z_values = []
                ratio_values = []
                for row in rows:
                    baseline_value = baseline_lookup.get((source, row["sample_key"]))
                    if baseline_value is None or baseline_value == 0.0:
                        continue
                    z_values.append(row["z"])
                    ratio_values.append(row[y_key] / baseline_value)
                if not z_values:
                    continue
                has_ratio_points = True
                bottom_axis.plot(
                    z_values,
                    ratio_values,
                    marker=version_marker,
                    color=version_color,
                    linestyle=SOURCE_LINESTYLES.get(source, "-"),
                    linewidth=1.0,
                    markersize=4,
                    label=f"{version_label}: {source}",
                )
        bottom_axis.set_ylabel(f"Ratio to {baseline_label}")
        bottom_axis.set_xlabel("True Z [m]")
        add_reference_z_lines(bottom_axis)
        bottom_axis.grid(True, alpha=0.3)
        if has_ratio_points:
            bottom_axis.legend(framealpha=0.8, fontsize=10, ncol=2)
        else:
            bottom_axis.text(
                0.5,
                0.5,
                "No common source/run points with baseline",
                transform=bottom_axis.transAxes,
                ha="center",
                va="center",
                fontsize=10,
            )
    else:
        top_axis.set_xlabel("True Z [m]")

    if has_comparison:
        fig.subplots_adjust(left=0.13, right=0.97, bottom=0.11, top=0.92, hspace=0.08)
    else:
        fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"[Output] Saved plot: {output_path}")


def plot_fit_summary(results_dir_args, run_info_path, output_dir, diagnostics=False, default_source="", max_radius_m=None):
    if not results_dir_args:
        raise ValueError("At least one results-dir label=path entry must be provided.")

    run_info_path = Path(run_info_path).expanduser()
    output_dir = Path(output_dir).expanduser()
    if not run_info_path.exists():
        raise FileNotFoundError(f"Run info CSV not found: {run_info_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    run_info = load_run_info(str(run_info_path), default_source=default_source)
    version_rows_map = {}
    version_data_map = {}
    version_order = []
    for arg_text in results_dir_args:
        version_label, results_dir = parse_results_dir_arg(arg_text)
        if not os.path.isdir(results_dir):
            raise FileNotFoundError(f"Results directory not found: {results_dir}")
        if version_label in version_rows_map:
            raise ValueError(f"Duplicate --results-dir label: {version_label}")
        rows_by_source = collect_summary(
            results_dir,
            run_info,
            default_source=default_source,
            max_radius_m=max_radius_m,
        )
        if not rows_by_source:
            raise RuntimeError(f"No valid fit summaries found in: {results_dir}")
        version_order.append(version_label)
        version_rows_map[version_label] = rows_by_source
        if diagnostics:
            data_dir = find_data_dir_from_results_dir(results_dir)
            version_data_map[version_label] = collect_event_arrays(data_dir)

    summary_prefix = "comparison_" if len(version_order) > 1 else ""
    outputs = {}

    make_plot(
        version_rows_map,
        version_order,
        y_key="mu",
        y_label=r"Fitted $\mu$ [MeV]",
        title=r"Fitted Energy $\mu$ vs True Z",
        output_path=str(output_dir / f"{summary_prefix}fit_mu_vs_true_z.png"),
    )
    outputs["fit_mu_vs_true_z"] = output_dir / f"{summary_prefix}fit_mu_vs_true_z.png"
    make_plot(
        version_rows_map,
        version_order,
        y_key="resolution_percent",
        y_label=r"Resolution $\sigma / \mu$ [%]",
        title=r"Energy Resolution vs True Z",
        output_path=str(output_dir / f"{summary_prefix}fit_resolution_vs_true_z.png"),
    )
    outputs["fit_resolution_vs_true_z"] = output_dir / f"{summary_prefix}fit_resolution_vs_true_z.png"

    if diagnostics:
        comparison = build_event_comparison(version_data_map)
        if comparison is not None:
            make_event_comparison_plot(
                comparison,
                output_path=str(output_dir / "event_by_event_compare_xyz_energy.png"),
            )
            outputs["event_by_event_compare"] = output_dir / "event_by_event_compare_xyz_energy.png"
            make_event_difference_plot(
                comparison,
                output_path=str(output_dir / "event_by_event_difference_xyz_energy.png"),
            )
            outputs["event_by_event_difference"] = output_dir / "event_by_event_difference_xyz_energy.png"
            make_delta_z_energy_correlation_plot(
                comparison,
                output_path=str(output_dir / "diagnostic_delta_z_vs_delta_energy.png"),
            )
            outputs["delta_z_vs_delta_energy"] = output_dir / "diagnostic_delta_z_vs_delta_energy.png"
            make_selected_z_scatter_plot(
                comparison,
                output_path=str(output_dir / "diagnostic_selected_rec_z_compare.png"),
            )
            outputs["selected_rec_z_compare"] = output_dir / "diagnostic_selected_rec_z_compare.png"

    return outputs


def build_parser():
    parser = argparse.ArgumentParser(
        description="Plot fitted energy mu and resolution versus true Z from result NPZ files."
    )
    parser.add_argument(
        "--results-dir",
        action="append",
        default=None,
        help="Result directory in the form label=path. Repeat this option for multiple versions.",
    )
    parser.add_argument(
        "--run-info",
        default=str(Path(__file__).resolve().parent.parent / "CalibRUN.csv"),
        help="CSV containing RUN to true-Z/source mapping.",
    )
    parser.add_argument(
        "--outdir",
        default=str(Path(__file__).resolve().parent.parent / "output" / "figures"),
        help="Output directory for summary figures.",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Also produce event-by-event diagnostic plots. This loads per-event NPZ arrays and can be slow.",
    )
    parser.add_argument(
        "--max-radius-m",
        type=float,
        default=None,
        help="Optional radius cut in meters for summary trend plots, applied as sqrt(X^2 + Y^2 + Z^2) <= max-radius-m.",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    outputs = plot_fit_summary(
        results_dir_args=args.results_dir,
        run_info_path=args.run_info,
        output_dir=args.outdir,
        diagnostics=bool(args.diagnostics),
        max_radius_m=args.max_radius_m,
    )
    for path in outputs.values():
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
