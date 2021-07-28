from dolfyn.io.api import read_example as read
import dolfyn.io.api as io
import dolfyn.io.rdi as wh
import dolfyn.io.nortek as awac
import dolfyn.io.nortek as vector
import dolfyn.io.nortek2 as sig
from dolfyn.rotate.api import rotate2, calc_principal_heading, \
    set_declination, set_inst2head_rotmat
from dolfyn.rotate.base import euler2orient, orient2euler
import dolfyn.time as time
import pkg_resources
import atexit
import warnings
import os
import sys
import unittest
from datetime import datetime
import numpy as np
import numpy.testing as npt
from xarray.testing import assert_equal, assert_identical, assert_allclose
warnings.simplefilter('ignore', UserWarning)
atexit.register(pkg_resources.cleanup_resources)

# Base definitions
def drop_config(dataset):
    # Can't save configuration string in netcdf
    for key in list(dataset.attrs.keys()):
        if 'config' in key:
            dataset.attrs.pop(key)
    return dataset

class ResourceFilename():

    def __init__(self, package_or_requirement, prefix=''):
        self.pkg = package_or_requirement
        self.prefix = prefix

    def __call__(self, name):
        return pkg_resources.resource_filename(self.pkg, self.prefix + name)

rfnm = ResourceFilename('dolfyn.test', prefix='data/') #!!! github link
exdt = ResourceFilename('dolfyn', prefix='example_data/') #!!! github link

def load(name, *args, **kwargs):
    return io.load(rfnm(name), *args, **kwargs)

def save(data, name, *args, **kwargs):
    io.save(data, rfnm(name), *args, **kwargs)

def load_matlab(name,  *args, **kwargs):
    return io.load_mat(rfnm(name), *args, **kwargs)

def save_matlab(data, name,  *args, **kwargs):
    io.save_mat(data, rfnm(name), *args, **kwargs)

# Import test data
dat = load('vector_data01.nc')
dat_imu = load('vector_data_imu01.nc')
dat_imu_json = load('vector_data_imu01-json.nc')
dat_burst = load('burst_mode01.nc')

dat_rdi = load('RDI_test01.nc')
dat_rdi_bt = load('RDI_withBT.nc')
dat_rdi_i = load('RDI_test01_rotate_beam2inst.nc')
dat_rdi_vm = load('vmdas01.nc')
dat_wr1 = load('winriver01.nc')
dat_wr2 = load('winriver02.nc')

dat_awac = load('AWAC_test01.nc')
dat_awac_ud = load('AWAC_test01_ud.nc')
dat_hwac = load('H-AWAC_test01.nc')
dat_sig = load('BenchFile01.nc')
dat_sig_i = load('Sig1000_IMU.nc')
dat_sig_i_ud = load('Sig1000_IMU_ud.nc')
dat_sig_ieb = load('VelEchoBT01.nc')
dat_sig_ie = load('Sig500_Echo.nc')


class io_testcase(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        sys.stdout = open(os.devnull, 'w') # block printing output
        #pass

    @classmethod
    def tearDownClass(self):
        sys.stdout = sys.__stdout__ # restart printing output
        #pass

    def test_save(self):
        save(dat, 'test_save')
        save_matlab(dat, 'test_save')
        
        assert os.path.exists(rfnm('test_save.nc'))
        assert os.path.exists(rfnm('test_save.mat'))
    
    
    def test_read(self):
        td = read('vector_data01.VEC', nens=100)
        tdm = read('vector_data_imu01.VEC',
                   userdata=False,
                   nens=100)
        tdb = read('burst_mode01.VEC',
                   nens=100)
        tdm2 = read('vector_data_imu01.VEC',
                    userdata=exdt('vector_data_imu01.userdata.json'),
                    nens=100)
        td_debug = drop_config(vector.read_nortek(exdt('vector_data_imu01.VEC'), 
                               debug=True, do_checksum=True, nens=100))
        
        # These values are not correct for this data but I'm adding them for
        # test purposes only.
        tdm = set_inst2head_rotmat(tdm, np.eye(3))
        tdm.attrs['inst2head_vec'] = np.array([-1.0, 0.5, 0.2])
        
        assert_equal(td, dat)
        assert_equal(tdm, dat_imu)
        assert_equal(tdb, dat_burst)
        assert_equal(tdm2, dat_imu_json)
        assert_equal(td_debug, tdm2)
        
    
    def test_io_rdi(self):
        td_rdi = drop_config(read('RDI_test01.000'))
        td_rdi_bt = drop_config(read('RDI_withBT.000', nens=500))
        td_vm = drop_config(read('vmdas01.ENX', nens=500))
        td_wr1 = drop_config(read('winriver01.PD0'))
        td_wr2 = drop_config(read('winriver02.PD0'))
        td_debug = drop_config(wh.read_rdi(exdt('RDI_withBT.000'), debug=11,
                                           nens=500))
                                              
        assert_equal(td_rdi, dat_rdi)
        assert_equal(td_rdi_bt, dat_rdi_bt)
        assert_equal(td_vm, dat_rdi_vm)
        assert_equal(td_wr1, dat_wr1)
        assert_equal(td_wr2, dat_wr2)
        assert_equal(td_debug, td_rdi_bt)
    
    
    def test_io_nortek(self):
        td_awac = drop_config(read('AWAC_test01.wpr', userdata=False, nens=500))
        td_awac_ud = drop_config(read('AWAC_test01.wpr', nens=500))
        td_hwac = drop_config(read('H-AWAC_test01.wpr'))
        td_debug = drop_config(awac.read_nortek(exdt('AWAC_test01.wpr'), 
                               debug=True, do_checksum=True, nens=500))
                                  
        assert_equal(td_awac, dat_awac)
        assert_equal(td_awac_ud, dat_awac_ud)
        assert_equal(td_hwac, dat_hwac)
        assert_equal(td_awac_ud, td_debug)
        
    
    def test_io_nortek2(self):
        td_sig = drop_config(read('BenchFile01.ad2cp', nens=500))
        td_sig_i = drop_config(read('Sig1000_IMU.ad2cp', userdata=False, nens=500))
        td_sig_i_ud = drop_config(read('Sig1000_IMU.ad2cp', nens=500))
        td_sig_ieb = drop_config(read('VelEchoBT01.ad2cp', nens=500))
        td_sig_ie = drop_config(read('Sig500_Echo.ad2cp', nens=500))
        
        os.remove(exdt('BenchFile01.ad2cp.index'))
        os.remove(exdt('Sig1000_IMU.ad2cp.index'))
        os.remove(exdt('VelEchoBT01.ad2cp.index'))
        os.remove(exdt('Sig500_Echo.ad2cp.index'))
    
        assert_equal(td_sig, dat_sig)
        assert_equal(td_sig_i, dat_sig_i)
        assert_equal(td_sig_i_ud, dat_sig_i_ud)
        assert_equal(td_sig_ieb, dat_sig_ieb)
        assert_equal(td_sig_ie, dat_sig_ie)
        
    
    def test_badtime(self):
        dat = sig.read_signature(rfnm('Sig1000_BadTime01.ad2cp'))
        os.remove(rfnm('Sig1000_BadTime01.ad2cp.index'))
        
        assert dat.time[199].isnull(), \
        "A good timestamp was found where a bad value is expected."
        
        
    def test_matlab_io(self):
        mat_rdi_bt = load_matlab('dat_rdi_bt')
        mat_sig_ieb = load_matlab('dat_sig_ieb')
            
        assert_identical(mat_rdi_bt, dat_rdi_bt)
        assert_identical(mat_sig_ieb, dat_sig_ieb)
    
    
    def test_read_warnings(self):
        with self.assertRaises(Exception):
            wh.read_rdi(exdt('H-AWAC_test01.wpr'))
        with self.assertRaises(Exception):
            awac.read_nortek(exdt('BenchFile01.ad2cp'))
        with self.assertRaises(Exception):
            sig.read_signature(exdt('AWAC_test01.wpr'))


class rotate_testcase(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        sys.stdout = open(os.devnull, 'w') # block printing output
        #pass
    @classmethod
    def tearDownClass(self):
        sys.stdout = sys.__stdout__ # restart printing output
        #pass
    
    def test_heading(self):
        td = dat_imu.copy(deep=True)
    
        head, pitch, roll = orient2euler(td)
        td['pitch'].values = pitch
        td['roll'].values = roll
        td['heading'].values = head
    
        cd = load('vector_data_imu01_head_pitch_roll.nc')
        assert_equal(td, cd)
        
    
    def test_inst2head_rotmat(self):
        td = dat.copy(deep=True)
    
        #Swap x,y, reverse z
        td = set_inst2head_rotmat(td, [[0, 1, 0],
                                       [1, 0, 0],
                                       [0, 0,-1]])
    
        # assert ((td.Veldata.u == tr.dat.Veldata.v).all() and
        #         (td.Veldata.v == tr.dat.Veldata.u).all() and
        #         (td.Veldata.w == -tr.dat.Veldata.w).all()
        #         ), "head->inst rotations give unexpeced results."
        #Coords don't get altered here
        npt.assert_allclose(td.Veldata.u.values, dat.Veldata.v.values)
        npt.assert_allclose(td.Veldata.v.values, dat.Veldata.u.values)
        npt.assert_allclose(td.Veldata.w.values, -dat.Veldata.w.values)
    
        # Validation for non-symmetric rotations
        td = dat.copy(deep=True)
        R = euler2orient(20, 30, 60, units='degrees') # arbitrary angles
        td = set_inst2head_rotmat(td, R)
        vel1 = td.vel
        # validate that a head->inst rotation occurs (transpose of inst2head_rotmat)
        vel2 = np.dot(R, dat.vel)
        #assert (vel1 == vel2).all(), "head->inst rotations give unexpeced results."
        npt.assert_allclose(vel1.values, vel2)
        
    
    def test_rotate_inst2earth_adv(self):
        td = dat.copy(deep=True)
        td = rotate2(td, 'earth', inplace=True)
        tdm = dat_imu.copy(deep=True)
        tdm = rotate2(tdm, 'earth', inplace=True)
        tdo = dat.copy(deep=True)
        tdo = rotate2(tdo.drop_vars('orientmat'), 'earth', inplace=True)
    
        cd = load('vector_data01_rotate_inst2earth.nc')
        cdm = load('vector_data_imu01_rotate_inst2earth.nc')
    
        assert_equal(td, cd)
        assert_equal(tdm, cdm)
        assert_equal(td, cd)
    
    
    def test_rotate_earth2inst_adv(self):
        td = load('vector_data01_rotate_inst2earth.nc')
        td = rotate2(td, 'inst', inplace=True)
        tdm = load('vector_data_imu01_rotate_inst2earth.nc')
        tdm = rotate2(tdm, 'inst', inplace=True)
    
        cd = dat.copy(deep=True)
        cdm = dat_imu.copy(deep=True)
        # The heading/pitch/roll data gets modified during rotation, so it
        # doesn't go back to what it was.
        cdm = cdm.drop_vars(['heading','pitch','roll'])
        tdm = tdm.drop_vars(['heading','pitch','roll'])
    
        assert_allclose(td, cd, atol=1e-6)
        assert_allclose(tdm, cdm, atol=1e-6)
    
    
    def test_rotate_inst2beam_adv(self):
        td = dat.copy(deep=True)
        td = rotate2(td, 'beam', inplace=True)
        tdm = dat_imu.copy(deep=True)
        tdm = rotate2(tdm, 'beam', inplace=True)
    
        cd = load('vector_data01_rotate_inst2beam.nc')
        cdm = load('vector_data_imu01_rotate_inst2beam.nc')
    
        assert_allclose(td, cd, atol=1e-6)
        assert_allclose(tdm, cdm, atol=1e-6)
    
    
    def test_rotate_beam2inst_adv(self):
        td = load('vector_data01_rotate_inst2beam.nc')
        td = rotate2(td, 'inst', inplace=True)
        tdm = load('vector_data_imu01_rotate_inst2beam.nc')
        tdm = rotate2(tdm, 'inst', inplace=True)
    
        cd = dat.copy(deep=True)
        cdm = dat_imu.copy(deep=True)
    
        assert_allclose(td, cd, atol=1e-6)
        assert_allclose(tdm, cdm, atol=1e-6)
    
    
    def test_rotate_earth2principal_adv(self):
        td = load('vector_data01_rotate_inst2earth.nc')
        td.attrs['principal_heading'] = calc_principal_heading(td['vel'])
        td = rotate2(td, 'principal', inplace=True)
        tdm = load('vector_data_imu01_rotate_inst2earth.nc')
        tdm.attrs['principal_heading'] = calc_principal_heading(tdm['vel'])
        tdm = rotate2(tdm, 'principal', inplace=True)
    
        cd = load('vector_data01_rotate_earth2principal.nc')
        cdm = load('vector_data_imu01_rotate_earth2principal.nc')
    
        assert_allclose(td, cd, atol=1e-6)
        assert_allclose(tdm, cdm, atol=1e-6)
    
    
    def test_rotate_earth2principal_set_declination(self):
        declin = 3.875
        td = load('vector_data01_rotate_inst2earth.nc')
        td0 = td.copy(deep=True)
        
        td.attrs['principal_heading'] = calc_principal_heading(td['vel'])
        td = rotate2(td, 'principal', inplace=True)
        td = set_declination(td, declin)
        td = rotate2(td, 'earth', inplace=True)
        
        td0 = set_declination(td0, -1)
        td0 = set_declination(td0, declin)
        td0.attrs['principal_heading'] = calc_principal_heading(td0['vel'])
        td0 = rotate2(td0, 'earth')
    
        assert_allclose(td0, td, atol=1e-6)
        
    
    def test_rotate_warnings(self):
        warn1 = dat.copy(deep=True)
        warn2 = dat.copy(deep=True)
        warn2.attrs['coord_sys'] = 'flow'
        warn3 = dat.copy(deep=True)
        warn3.attrs['inst_model'] = 'ADV'
        
        with self.assertRaises(Exception):
            rotate2(warn1, 'ship')
        with self.assertRaises(Exception):
            rotate2(warn2, 'earth')
        with self.assertRaises(Exception):
            set_inst2head_rotmat(warn3, np.eye(3))
            set_inst2head_rotmat(warn3, np.eye(3))
    
    
    def test_rotate_beam2inst_adp(self):
        td_rdi = rotate2(dat_rdi, 'inst')
        td_sig = rotate2(dat_sig, 'inst')
        td_sig_i = rotate2(dat_sig_i, 'inst')
        td_sig_ieb = rotate2(dat_sig_ieb, 'inst')
        
        cd_rdi = load('RDI_test01_rotate_beam2inst.nc')
        cd_sig = load('BenchFile01_rotate_beam2inst.nc')
        cd_sig_i = load('Sig1000_IMU_rotate_beam2inst.nc')
        cd_sig_ieb = load('VelEchoBT01_rotate_beam2inst.nc')
        
        assert_allclose(td_rdi, cd_rdi, atol=1e-5)
        assert_allclose(td_sig, cd_sig, atol=1e-5)
        assert_allclose(td_sig_i, cd_sig_i, atol=1e-5)
        assert_allclose(td_sig_ieb, cd_sig_ieb, atol=1e-5)  
    
    
    def test_rotate_inst2beam_adp(self):
        td = load('RDI_test01_rotate_beam2inst.nc')
        td = rotate2(td, 'beam', inplace=True)
        td_awac = load('AWAC_test01_earth2inst.nc')
        td_awac = rotate2(td_awac, 'beam', inplace=True)
        td_sig = load('BenchFile01_rotate_beam2inst.nc')
        td_sig = rotate2(td_sig, 'beam', inplace=True)
        td_sig_i = load('Sig1000_IMU_rotate_beam2inst.nc')
        td_sig_i = rotate2(td_sig_i, 'beam', inplace=True)
        td_sig_ie = load('Sig500_Echo_earth2inst.nc')
        td_sig_ie = rotate2(td_sig_ie, 'beam')
        
        cd_td = dat_rdi.copy(deep=True)
        cd_awac = load('AWAC_test01_inst2beam.nc')
        cd_sig = dat_sig.copy(deep=True)
        cd_sig_i = dat_sig_i.copy(deep=True)
        cd_sig_ie = load('Sig500_Echo_inst2beam.nc')
    
        # # The reverse RDI rotation doesn't work b/c of NaN's in one beam
        # # that propagate to others, so we impose that here.
        cd_td['vel'].values[:, np.isnan(cd_td['vel'].values).any(0)] = np.NaN
        
        assert_allclose(td, cd_td, atol=1e-5)
        assert_allclose(td_awac, cd_awac, atol=1e-5)
        assert_allclose(td_sig, cd_sig, atol=1e-5)
        assert_allclose(td_sig_i, cd_sig_i, atol=1e-5)
        assert_allclose(td_sig_ie, cd_sig_ie, atol=1e-5)
    
    
    def test_rotate_inst2earth_adp(self):
        # AWAC & Sig500 are loaded in earth
        td_awac = dat_awac.copy(deep=True)
        td_awac = rotate2(td_awac, 'inst')
        td_sig_ie = dat_sig_ie.copy(deep=True)
        td_sig_ie = rotate2(rotate2(td_sig_ie,'earth'), 'inst')
        td_sig_o = td_sig_ie.copy(deep=True)
        
        td = rotate2(dat_rdi, 'earth')
        tdwr2 = rotate2(dat_wr2, 'earth')
        td_sig = load('BenchFile01_rotate_beam2inst.nc')
        td_sig = rotate2(td_sig, 'earth', inplace=True)
        td_sig_i = load('Sig1000_IMU_rotate_beam2inst.nc')
        td_sig_i = rotate2(td_sig_i, 'earth', inplace=True)
    
        td_awac = rotate2(td_awac, 'earth', inplace=True)
        td_sig_ie = rotate2(td_sig_ie, 'earth')
        td_sig_o = rotate2(td_sig_o.drop_vars('orientmat'), 'earth')
    
        cd = load('RDI_test01_rotate_inst2earth.nc')
        cdwr2 = load('winriver02_rotate_ship2earth.nc')
        cd_sig = load('BenchFile01_rotate_inst2earth.nc')
        cd_sig_i = load('Sig1000_IMU_rotate_inst2earth.nc')
        
        assert_allclose(td, cd, atol=1e-5)
        assert_allclose(tdwr2, cdwr2, atol=1e-5)
        assert_allclose(td_awac, dat_awac, atol=1e-5)
        assert_allclose(td_sig, cd_sig, atol=1e-5)
        assert_allclose(td_sig_i, cd_sig_i, atol=1e-5)
        assert_allclose(td_sig_ie, dat_sig_ie, atol=1e-5)
        npt.assert_allclose(td_sig_o.vel, dat_sig_ie.vel, atol=1e-5)
    
    
    def test_rotate_earth2inst_adp(self):
        td_rdi = load('RDI_test01_rotate_inst2earth.nc')
        td_rdi = rotate2(td_rdi, 'inst', inplace=True)
        tdwr2 = load('winriver02_rotate_ship2earth.nc')
        tdwr2 = rotate2(tdwr2, 'inst', inplace=True)
        
        td_awac = dat_awac.copy(deep=True)
        td_awac = rotate2(td_awac, 'inst')  # AWAC is in earth coords
        td_sig = load('BenchFile01_rotate_inst2earth.nc')
        td_sig = rotate2(td_sig, 'inst', inplace=True)
        td_sigi = load('Sig1000_IMU_rotate_inst2earth.nc')
        td_sig_i = rotate2(td_sigi, 'inst', inplace=True)
    
        cd_rdi = load('RDI_test01_rotate_beam2inst.nc')
        cd_awac = load('AWAC_test01_earth2inst.nc')
        cd_sig = load('BenchFile01_rotate_beam2inst.nc')
        cd_sig_i = load('Sig1000_IMU_rotate_beam2inst.nc')
        
        assert_allclose(td_rdi, cd_rdi, atol=1e-5)
        assert_allclose(tdwr2, dat_wr2, atol=1e-5)
        assert_allclose(td_awac, cd_awac, atol=1e-5)
        assert_allclose(td_sig, cd_sig, atol=1e-5)
        #known rounding error due to AHRS orientmat, see test_vs_nortek
        #assert_allclose(td_sig_i, cd_sig_i, atol=1e-3)
        npt.assert_allclose(td_sig_i.accel.values, cd_sig_i.accel.values, atol=1e-3)
    
    
    def test_rotate_earth2principal_adp(self):
        td_rdi = load('RDI_test01_rotate_inst2earth.nc')
        td_sig = load('BenchFile01_rotate_inst2earth.nc')
        td_awac = dat_awac.copy(deep=True)
    
        td_rdi.attrs['principal_heading'] = calc_principal_heading(td_rdi.vel.mean('range'))
        td_sig.attrs['principal_heading'] = calc_principal_heading(td_sig.vel.mean('range'))
        td_awac.attrs['principal_heading'] = calc_principal_heading(td_awac.vel.mean('range'), 
                                                                    tidal_mode=False)
        td_rdi = rotate2(td_rdi, 'principal')
        td_sig = rotate2(td_sig, 'principal')
        td_awac = rotate2(td_awac, 'principal')
    
        cd_rdi = load('RDI_test01_rotate_earth2principal.nc')
        cd_sig = load('BenchFile01_rotate_earth2principal.nc')
        cd_awac = load('AWAC_test01_earth2principal.nc')
    
        assert_allclose(td_rdi, cd_rdi, atol=1e-5)
        assert_allclose(td_awac, cd_awac, atol=1e-5)
        assert_allclose(td_sig, cd_sig, atol=1e-5)
        

class time_testcase(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        pass

    @classmethod
    def tearDownClass(self):
        pass
        
    def test_epoch2date(self):
        td = dat_imu.copy(deep=True)
        
        dt = time.epoch2date(td.time)
        dt1 = time.epoch2date(td.time[0])
        dt_utc = time.epoch2date(td.time, utc=True)
        dt_pdt = time.epoch2date(td.time, utc=True, offset_hr=-7)
        t_str = time.epoch2date(td.time, to_str=True)
        
        npt.assert_equal(dt[0], datetime(2012, 6, 12, 12, 0, 2, 687283))
        npt.assert_equal(dt1, [datetime(2012, 6, 12, 12, 0, 2, 687283)])
        npt.assert_equal(dt_utc[0], datetime(2012, 6, 12, 19, 0, 2, 687283))
        npt.assert_equal(dt_pdt[0], datetime(2012, 6, 12, 12, 0, 2, 687283))
        npt.assert_equal(t_str[0], '2012-06-12 12:00:02.687283')
        
    
    def test_datetime(self):
        td = dat_imu.copy(deep=True)
        
        dt = time.epoch2date(td.time)
        epoch = np.array(time.date2epoch(dt))
        
        npt.assert_allclose(td.time.values, epoch, atol=1e-7)
        
        
    def test_datenum(self):
        td = dat_imu.copy(deep=True)
        
        dt = time.epoch2date(td.time)
        dn = time.date2matlab(dt)
        dt2 = time.matlab2date(dn)
        epoch = np.array(time.date2epoch(dt2))
        
        npt.assert_allclose(td.time.values, epoch, atol=1e-6)
        npt.assert_equal(dn[0], 735032.5000311028)
        
        
if __name__ == '__main__':
    unittest.main() 
