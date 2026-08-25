import numpy as np

def convolve(bin_contents, bin_edges, bin_sigmas):
    """
    Variable Gaussian Smearing (Convolution) preserving event counts.
    Pure Python implementation replacing C++ extension.
    """
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    bin_widths = np.diff(bin_edges)

    E_i = bin_centers[:, np.newaxis]
    E_j = bin_centers[np.newaxis, :]
    Sigma_j = bin_sigmas[np.newaxis, :]
    Sigma_j = np.where(Sigma_j <= 0, 1e-9, Sigma_j)

    prefactor = 1.0 / (np.sqrt(2 * np.pi) * Sigma_j)
    exponent = -0.5 * ((E_i - E_j) / Sigma_j) ** 2
    G_ij = prefactor * np.exp(exponent)

    P_ij = G_ij * bin_widths[:, np.newaxis]
    col_sums = np.sum(P_ij, axis=0)
    col_sums = np.where(col_sums == 0, 1, col_sums)
    P_ij_normalized = P_ij / col_sums[np.newaxis, :]

    convolved = P_ij_normalized @ bin_contents
    return convolved


# =============================================================================
# Python fallback for C++ extension functions
# The C++ extension (smx_ana_cpp*.so) provides sum_distributions_fast_cpp,
# ak_unique, and get_copy_numbers. Here we provide pure-Python fallbacks.
# =============================================================================

def sum_distributions_fast_cpp(x1, y1, x2, y2):
    """
    Pure Python fallback for the C++ sum_distributions_fast_cpp.
    Uses the same interpolation+integration logic as FitterUtils.sum_distributions_fast.
    """
    from scipy.integrate import simpson
    from scipy.interpolate import interp1d

    y1_norm = y1 / simpson(y1, x=x1)
    y2_norm = y2 / simpson(y2, x=x2)

    f1 = interp1d(x1, y1_norm, kind="cubic", bounds_error=False, fill_value=0)
    f2 = interp1d(x2, y2_norm, kind="cubic", bounds_error=False, fill_value=0)

    z_min = x1[0] + x2[0]
    z_max = x1[-1] + x2[-1]
    z = np.arange(z_min, z_max, 0.001)

    t_min = x1[0]
    t_max = x1[-1]
    t = np.arange(t_min, t_max, 0.001)

    T, Z = np.meshgrid(t, z)
    integrand = f1(T) * f2(Z - T)
    result = simpson(integrand, x=t, axis=1)
    return z, result
