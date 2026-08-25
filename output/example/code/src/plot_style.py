from __future__ import annotations

import matplotlib.pyplot as plt


def apply_plot_style(*, dpi: int = 300, font_family: str | None = None) -> None:
    plt.style.use("default")
    plt.rcParams["axes.grid"] = True
    plt.rcParams["text.usetex"] = False
    plt.rcParams["figure.dpi"] = dpi
    if font_family:
        plt.rcParams["font.family"] = font_family


def apply_fitter_plot_style() -> None:
    apply_plot_style(dpi=300)


def apply_runner_plot_style() -> None:
    apply_plot_style(dpi=300, font_family="Times New Roman")


def apply_summary_plot_style() -> None:
    apply_plot_style(dpi=300, font_family="DejaVu Sans")
    plt.rcParams["axes.labelsize"] = 16
    plt.rcParams["axes.titlesize"] = 16
    plt.rcParams["xtick.labelsize"] = 13
    plt.rcParams["ytick.labelsize"] = 13
    plt.rcParams["legend.fontsize"] = 12
