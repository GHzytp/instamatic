import numpy as np
import lmfit
from instamatic.tools import *


def fit_affine_transformation(a, b, rotation=True, scaling=True, translation=False, shear=False, as_params=False, verbose=False, **x0):
    params = lmfit.Parameters()
    params.add("angle", value=x0.get("angle", 0), vary=rotation, min=-np.pi, max=np.pi)
    params.add("sx"   , value=x0.get("sx"   , 1), vary=scaling)
    params.add("sy"   , value=x0.get("sy"   , 1), vary=scaling)
    params.add("tx"   , value=x0.get("tx"   , 0), vary=translation)
    params.add("ty"   , value=x0.get("ty"   , 0), vary=translation)
    params.add("k1"   , value=x0.get("k1"   , 1), vary=shear)
    params.add("k2"   , value=x0.get("k2"   , 1), vary=shear)
    
    def objective_func(params, arr1, arr2):
        angle = params["angle"].value
        sx    = params["sx"].value
        sy    = params["sy"].value 
        tx    = params["tx"].value
        ty    = params["ty"].value
        k1    = params["k1"].value
        k2    = params["k2"].value
        
        sin = np.sin(angle)
        cos = np.cos(angle)

        r = np.array([
            [ sx*cos, -sy*k1*sin],
            [ sx*k2*sin,  sy*cos]])
        t = np.array([tx, ty])

        fit = np.dot(arr1, r) + t
        return fit-arr2
    
    method = "leastsq"
    args = (a, b)
    res = lmfit.minimize(objective_func, params, args=args, method=method)
    
    if res.success and not verbose:
        print("Minimization converged after {} cycles with chisqr of {}".format(res.nfev, res.chisqr))
    else:
        lmfit.report_fit(res)

    angle = res.params["angle"].value
    sx    = res.params["sx"].value
    sy    = res.params["sy"].value 
    tx    = res.params["tx"].value
    ty    = res.params["ty"].value
    k1    = res.params["k1"].value
    k2    = res.params["k2"].value
    
    sin = np.sin(angle)
    cos = np.cos(angle)
    
    r = np.array([
        [ sx*cos, -sy*k1*sin],
        [ sx*k2*sin,  sy*cos]])
    t = np.array([tx, ty])
    
    if as_params:
        return res.params
    else:
        return r, t

