import numpy as np


def GetBinCenter(bin_edges):
    edges = np.asarray(bin_edges, dtype=float)
    if edges.ndim != 1 or edges.size < 2:
        raise ValueError("bin_edges must be a one-dimensional array with at least two entries")
    return 0.5 * (edges[:-1] + edges[1:])
