import numpy as np
from scipy.stats import norm
from scipy.integrate import simpson
from scipy.interpolate import interp1d
try:
    from scipy.signal import fftconvolve
except ImportError:
    fftconvolve = None

def sum_distributions_fast(x1, y1, x2, y2):
    y1_norm = y1 / simpson(y1, x=x1)
    y2_norm = y2 / simpson(y2, x=x2)

    f1 = interp1d(x1, y1_norm, kind="cubic", bounds_error=False, fill_value=0)
    f2 = interp1d(x2, y2_norm, kind="cubic", bounds_error=False, fill_value=0)

    z_min = x1[0] + x2[0]
    z_max = x1[-1] + x2[-1]
    z = np.arange(z_min, z_max, 0.001)

    t_min = x1[0]
    t_max = x1[-1]
    t = np.arange(t_min, t_max, 0.001) # the pdf will be zero outside this range

    T, Z = np.meshgrid(t, z)
    integrand = f1(T) * f2(Z - T)

    result = simpson(integrand, x=t, axis=1)
    # result = result / simpson(result, x=z)
    return z, result

def FEP_part(bins_center, amp_gauss, center_gauss, sigma_gauss):
    return amp_gauss * np.exp(-0.5 * ((bins_center - center_gauss) / sigma_gauss) ** 2)

def EnergyResolutionModel(Evis, a, b, c):
    Eres = np.sqrt((a / np.sqrt(Evis)) ** 2 + b**2 + (c / Evis) ** 2)
    return Eres * Evis * 0.01

def extract_fit_results(m) -> dict:
    return {
        key: {"value": float(m.values[key]), "error": float(m.errors[key])}
        for key in m.parameters
    }


def normalize_histogram(values):
    total = float(np.sum(values))
    if total <= 0.0:
        return np.zeros_like(values, dtype=float)
    return np.asarray(values, dtype=float) / total


def build_c14_pileup_terms(
    bins_center,
    part_wo_pileup,
    bins_fit,
    bins_c14_center,
    c14_conv,
    convolver,
):
    if float(np.sum(c14_conv)) <= 0.0:
        zero_hist = np.zeros(len(bins_fit) - 1, dtype=float)
        return zero_hist, zero_hist.copy()

    z, sum_pdf = convolver(bins_center, part_wo_pileup, bins_c14_center, c14_conv)
    one_pileup = np.histogram(z, bins=bins_fit, weights=sum_pdf)[0]
    one_pileup = normalize_histogram(one_pileup)

    if float(np.sum(one_pileup)) <= 0.0:
        zero_hist = np.zeros(len(bins_fit) - 1, dtype=float)
        return zero_hist, zero_hist.copy()

    z, sum_pdf_1 = convolver(bins_center, one_pileup, bins_c14_center, c14_conv)
    two_pileup = np.histogram(z, bins=bins_fit, weights=sum_pdf_1)[0]
    two_pileup = normalize_histogram(two_pileup)
    return one_pileup, two_pileup

# find where the file location

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
print("Project root path:", PROJECT_ROOT)

def sum_distributions_fft(x1, y1, x2, y2):
    """Convolve two 1D PDFs on the same 1 keV grid used by the reference path."""
    step = 0.001
    y1_area = simpson(y1, x=x1)
    y2_area = simpson(y2, x=x2)
    if y1_area <= 0 or y2_area <= 0:
        z = np.arange(x1[0] + x2[0], x1[-1] + x2[-1], step)
        return z, np.zeros_like(z, dtype=float)

    y1_norm = y1 / y1_area
    y2_norm = y2 / y2_area

    f1 = interp1d(x1, y1_norm, kind="cubic", bounds_error=False, fill_value=0)
    f2 = interp1d(x2, y2_norm, kind="cubic", bounds_error=False, fill_value=0)

    t = np.arange(x1[0], x1[-1], step)
    u = np.arange(x2[0], x2[-1] + 0.5 * step, step)
    y1_sample = f1(t)
    y2_sample = f2(u)

    if fftconvolve is None:
        conv = np.convolve(y1_sample, y2_sample, mode="full")
    else:
        conv = fftconvolve(y1_sample, y2_sample, mode="full")
    conv = conv * step

    z_full = t[0] + u[0] + np.arange(len(conv)) * step
    z = np.arange(x1[0] + x2[0], x1[-1] + x2[-1], step)
    result = np.interp(z, z_full, conv, left=0.0, right=0.0)
    return z, result
