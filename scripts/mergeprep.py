from indexer import read_ycsv
import glob
from xcore import UnitCell
from xcore.formats import write_shelx_ins
from xcore.scattering.dt1968 import table, keys
from xcore.scattering.atomic_radii import table as radii_table

from serialmerge import serialmerge_fns

def make_sfac_for_electrons(composition):
    sfac = {}
    for key in composition.keys():
        t = dict(zip(keys, table[key]))
        newkey = "{key:2s} {a1:7.4f} {b1:7.4f} {a2:7.4f} {b2:7.4f}         =\n        {a3:7.4f} {b3:7.4f} {a4:7.4f} {b4:7.4f} {c:7.4f} =\n".format(key=key, **t)
        newkey += "         0.0000  0.0000  0.0000 {covrad:7.4f} {wght:7.4f}".format(wght=radii_table[key][1], covrad=radii_table[key][2])
        sfac[newkey] = composition[key]
    return sfac


def prepare_shelx(inp="results.csv", composition={"Si":192, "O":384}):
    """Simple function to prepare input files for shelx
    Reads the cell/experimental parameters from the input file"""

    df, d = read_ycsv(inp)

    cell = d["cell"]
    cell = UnitCell(cell["params"], spgr=cell["spgr"], name=cell["name"])

    drc = d["data"]["drc_out"]
    fns = glob.glob(drc + "\\*.hkl")

    serialmerge_fns(fns)

    use_electron_sfac = False
    if use_electron_sfac:
        composition = make_sfac_for_electrons(composition)

    write_shelx_ins(cell, wavelength=0.0251, composition=composition)


if __name__ == '__main__':
    prepare_shelx()