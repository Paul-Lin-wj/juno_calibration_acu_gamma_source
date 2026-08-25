import os
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.legend_handler import HandlerTuple

multi_gamma = ["Ge68", "Co60", "nC"]

gamma_source_type = ["Cs137", "Mn54", "Co60", "K40", "Ge68", "AmC", "AmBe"]

single_source = {
    "Cs137": 0.662,
    "Mn54": 0.835,
    "Co60": 2.506,
    "K40": 1.461,
    "Ge68": 1.022,
}
dict_AmC= {
    "nH": 2.223,
    "nC": 4.95,
    "O16": 6.13
}

# Try multiple paths for calibration data
_calib_paths = [
    "/afs/ihep.ac.cn/users/s/sunmingxia/lustrefs/AnalysisTool/smx_ana",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."),
    os.path.dirname(os.path.abspath(__file__)),
]

_calib_path = None
for path in _calib_paths:
    if os.path.exists(os.path.join(path, "Calib_label.npz")):
        _calib_path = path
        break

if _calib_path is None:
    raise FileNotFoundError("Could not find Calib_label.npz or Calib_energy.npz in any known location")

dict_label = dict(np.load(os.path.join(_calib_path, "Calib_label.npz")))
for key in dict_label.keys():
    dict_label[key] = str(dict_label[key])
dict_label["nC"] = 'n$^{12}$C 4.94 MeV'
    
dict_energy = dict(np.load(os.path.join(_calib_path, "Calib_energy.npz")))
for key in dict_energy.keys():
    dict_energy[key] = float(dict_energy[key])
    
dict_LSNL_gamma = dict_energy.copy()
dict_LSNL_gamma["Ge68"] = 0.511
dict_LSNL_gamma["Co60"] = (1.173 + 1.332) / 2
dict_LSNL_gamma["nC"] = 4.94 * 0.68 + (1 - 0.68) * ((3.68 + 1.26) / 2)

print("Calib label:", dict_label)
print("Calib energy:", dict_energy)

# for my result orginization
def calc_resolution(mean, mean_err, sigma, sigma_err):
    resolution = sigma / mean * 100
    resolution_err = resolution * np.sqrt(
        (mean_err / mean) ** 2 + (sigma_err / sigma) ** 2
    )
    return resolution, resolution_err


def build_key_plot_dict(
    dict_center_fit, dict_energy, multi_gamma, key_fit, position=None, if_correct_Energy = False
):
    result = {
        "source": [],
        "energy": [],
        "energy_err": [],
        "resolution": [],
        "resolution_err": [],
        "is_multi_gamma": [],
        "is_Ge68_in_multi": [],
    }
    sources, energies, energy_errs, resolution_erec, resolution_erec_err = [], [], [], [], []
    for source_type in dict_energy.keys():
        if position is None:
            mean, mean_err = dict_center_fit[key_fit][source_type][0]
            sigma, sigma_err = dict_center_fit[key_fit][source_type][1]
        else:
            if position not in dict_center_fit[key_fit][source_type].keys():
                print(
                    f"Warning: position {position} not in dict_center_fit for source {source_type}, check: {dict_center_fit[key_fit][source_type].keys()}"
                )
                continue
            mean, mean_err = dict_center_fit[key_fit][source_type][position][0]
            sigma, sigma_err = dict_center_fit[key_fit][source_type][position][1]
        sources.append(source_type)
        energies.append(mean)
        energy_errs.append(mean_err)
        res, res_err = calc_resolution(mean, mean_err, sigma, sigma_err)
        resolution_erec.append(res)
        resolution_erec_err.append(res_err)
    energies = np.array(energies)
    energy_errs = np.array(energy_errs)
    resolution_erec = np.array(resolution_erec)
    resolution_erec_err = np.array(resolution_erec_err)
    # resort by energy
    index_sort = np.argsort(energies)
    sources = np.array(sources)[index_sort]
    energies = energies[index_sort]
    energy_errs = energy_errs[index_sort]
    resolution_erec = resolution_erec[index_sort]
    resolution_erec_err = resolution_erec_err[index_sort]
    is_multi_gamma = np.array([src in multi_gamma for src in sources])
    is_Ge68_in_multi = np.array([src == "Ge68" for src in sources])
    if key_fit in ["PE_det", "PE_rec"] and position is not None:
        LY_MC = energies[sources == "nH"] / 2.223
        energies = energies / LY_MC
        energy_errs = energy_errs / LY_MC
    if if_correct_Energy:
        energy_nH = energies[sources == "nH"][0]
        energy_nH_err = energy_errs[sources == "nH"][0]
        # calculate err propagation
        energy_errs = (energies * 2.223 / energy_nH) * np.sqrt(
            (energy_errs / energies) ** 2 + (energy_nH_err / energy_nH) ** 2
        )
        energies = energies * 2.223 / energy_nH

    result["source"] = sources
    result["energy"] = energies
    result["energy_err"] = energy_errs
    result["resolution"] = resolution_erec
    result["resolution_err"] = resolution_erec_err
    result["is_multi_gamma"] = is_multi_gamma
    result["is_Ge68_in_multi"] = is_Ge68_in_multi
    return result


def JUNOResolutionModel(x, a, b, c):
    return np.sqrt((a / np.sqrt(x)) ** 2 + b**2 + (c / x) ** 2)


def getJUNO_ABC_Target():
    #  from energy resolution paper
    return {"a": 2.614, "b": 0.640, "c": 1.205}

def Fit_JUNOResolutionModel(x_arr, y_arr, y_err_arr, abc_init, x_model_plot, is_show_migrid=True):
    from iminuit import Minuit
    from iminuit.cost import LeastSquares
    from IPython.display import display

    c = LeastSquares(
        x_arr,
        y_arr,
        # np.ones_like(y_err_arr),
        y_err_arr,
        JUNOResolutionModel,
    )
    m = Minuit(
        c,
        **abc_init
    )
    m.limits["a"] = (0, None)
    m.limits["b"] = (0, None)
    m.limits["c"] = (0, None)
    if is_show_migrid:
        display(m.migrad())
    else:
        m.migrad()

    dict_abc_values = {
        key: [m.values[key], m.errors[key]] for key in ["a", "b", "c"]
    }
    dict_tmp = {
        key: m.values[key] for key in ["a", "b", "c"]
    }

    # best fit result
    y_predict_plot = JUNOResolutionModel(x_model_plot, **dict_tmp)
    y_predict = JUNOResolutionModel(x_arr, **dict_tmp)
    bias = (y_predict - y_arr) / y_predict * 100

    return dict_abc_values, y_predict_plot, bias
