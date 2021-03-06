from dolfyn.test import test_read_adv as tv
from dolfyn.test.base import load_ncdata as load, save_ncdata as save
from xarray.testing import assert_equal
import xarray as xr
import dolfyn.adv.api as avm

class adv_setup():
    def __init__(self, tv):
        self.dat = tv.dat.copy(deep=True)
        self.tdat = avm.calc_turbulence(self.dat, n_bin=20.0, fs=self.dat.fs)
        
        short = xr.Dataset()
        short['u'] = self.tdat.Veldata.u
        short['v'] = self.tdat.Veldata.v
        short['w'] = self.tdat.Veldata.w
        short['U'] = self.tdat.Veldata.U
        short['U_mag'] = self.tdat.Veldata.U_mag
        short['U_dir'] = self.tdat.Veldata.U_dir
        short["upup_"] = self.tdat.Veldata.upup_
        short["vpvp_"] = self.tdat.Veldata.vpvp_
        short["wpwp_"] = self.tdat.Veldata.wpwp_
        short["upvp_"] = self.tdat.Veldata.upvp_
        short["upwp_"] = self.tdat.Veldata.upwp_
        short["vpwp_"] = self.tdat.Veldata.vpwp_
        short['tke'] = self.tdat.Veldata.tke
        short['I'] = self.tdat.Veldata.I
        short['tau_ij'] = self.tdat.Veldata.tau_ij
        short['E_coh'] = self.tdat.Veldata.E_coh
        short['I_tke'] = self.tdat.Veldata.I_tke
        short['k'] = self.tdat.Veldata.k
        self.short = short

def test_shortcuts(make_data=False):
    test_dat = adv_setup(tv)
    
    if make_data:
        save(test_dat.short, 'shortcuts')
        return
    #saved_short = load('shortcuts.nc')
    
    assert_equal(test_dat.short, load('shortcuts.nc'))
 
if __name__=='__main__':
    test_shortcuts()
    