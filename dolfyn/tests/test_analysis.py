from dolfyn.tests import test_read_adp as tr, test_read_adv as tv
from dolfyn.tests.base import load_netcdf as load, save_netcdf as save, assert_allclose
from dolfyn import VelBinner, read_example
import dolfyn.adv.api as avm
import dolfyn.adp.api as apm
from xarray.testing import assert_identical
import pytest
import numpy as np


class adv_setup():
    def __init__(self, tv):
        self.dat1 = tv.dat.copy(deep=True)
        self.dat2 = read_example('vector_burst_mode01.VEC', nens=90)
        fs = self.dat1.fs
        self.avg_tool = VelBinner(n_bin=fs, fs=fs)


class adp_setup():
    def __init__(self, tr):
        self.dat = tr.dat_sig.copy(deep=True)
        fs = self.dat.fs
        with pytest.warns(UserWarning):
            self.avg_tool = VelBinner(n_bin=fs*20, fs=fs, n_fft=fs*40)


def test_do_func(make_data=False):
    adv_tool = adv_setup(tv).avg_tool
    ds1 = adv_setup(tv).dat1
    ds_vec = adv_tool.do_avg(ds1)
    ds_vec = adv_tool.do_var(ds1, out_ds=ds_vec)

    # test non-integer bin sizes
    mean_test = adv_tool.mean(ds1['vel'].values, n_bin=ds1.fs*1.01)

    adp_tool = adp_setup(tr).avg_tool
    ds2 = adp_setup(tr).dat
    ds_sig = adp_tool.do_avg(ds2)
    ds_sig = adp_tool.do_var(ds2, out_ds=ds_sig)

    if make_data:
        save(ds_vec, 'vector_data01_avg.nc')
        save(ds_sig, 'BenchFile01_avg.nc')
        return

    assert np.sum(mean_test-ds_vec.vel.values) == 0, "Mean test failed"
    assert_allclose(ds_vec, load('vector_data01_avg.nc'), atol=1e-6)
    assert_allclose(ds_sig, load('BenchFile01_avg.nc'), atol=1e-6)


def test_calc_func(make_data=False):
    bnr1 = adv_setup(tv).avg_tool
    ds1 = adv_setup(tv).dat1
    ds2 = adv_setup(tv).dat2

    bnr = adp_setup(tr).avg_tool
    ds = adp_setup(tr).dat

    ds_adv = type(ds1)()
    ds_adv_dif = type(ds1)()
    ds_adp = type(ds)()

    ds_adv['coh'] = bnr1.calc_coh(
        ds1['vel'][0], ds1['vel'][1], n_fft_coh=ds1.fs)
    ds_adv['pang'] = bnr1.calc_phase_angle(
        ds1['vel'][0], ds1['vel'][1], n_fft_coh=ds1.fs)
    ds_adv['xcov'] = bnr1.calc_xcov(ds1['vel'][0], ds1['vel'][1])
    ds_adv['acov'] = bnr1.calc_acov(ds1['vel'])
    ds_adv['tke_vec_detrend'] = bnr1.calc_tke(ds1['vel'], detrend=True)
    ds_adv['tke_vec_demean'] = bnr1.calc_tke(ds1['vel'], detrend=False)
    ds_adv['psd'] = bnr1.calc_psd(ds1['vel'], freq_units='Hz')

    # Different lengths
    ds_adv_dif['coh_dif'] = bnr1.calc_coh(
        ds1['vel'], ds2.vel)
    ds_adv_dif['pang_dif'] = bnr1.calc_phase_angle(
        ds1['vel'], ds2.vel)

    # Test ADCP single vector spectra, cross-spectra to test radians code
    ds_adp['psd_b5'] = bnr.calc_psd(ds['vel_b5'].isel(
        range_b5=5), freq_units='rad', window='hamm')
    ds_adp['tke_b5'] = bnr.calc_tke(ds['vel_b5'])

    if make_data:
        save(ds_adv, 'vector_data01_func.nc')
        save(ds_adv_dif, 'vector_data01_funcdif.nc')
        save(ds_adp, 'BenchFile01_func.nc')
        return

    assert_allclose(ds_adv, load('vector_data01_func.nc'), atol=1e-6)
    assert_allclose(ds_adv_dif, load('vector_data01_funcdif.nc'), atol=1e-6)
    assert_allclose(ds_adp, load('BenchFile01_func.nc'), atol=1e-6)


def test_calc_freq():
    dat_vec = adv_setup(tv)

    f = dat_vec.avg_tool.calc_freq(units='Hz')
    omega = dat_vec.avg_tool.calc_freq(units='rad/s')

    np.testing.assert_equal(f, np.arange(1, 17, 1, dtype='float'))
    np.testing.assert_equal(omega, np.arange(
        1, 17, 1, dtype='float')*(2*np.pi))


def test_adv_turbulence(make_data=False):
    # Checks that code is functioning
    dat = tv.dat.copy(deep=True)
    bnr = avm.ADVBinner(n_bin=20.0, fs=dat.fs)
    tdat = bnr(dat)
    acov = bnr.calc_acov(dat['vel'])

    assert_identical(tdat, avm.calc_turbulence(dat, n_bin=20.0, fs=dat.fs))

    tdat['stress_detrend'] = bnr.calc_stress(dat['vel'])
    tdat['stress_demean'] = bnr.calc_stress(dat['vel'], detrend=False)
    tdat['csd'] = bnr.calc_csd(dat['vel'], freq_units='rad', window='hamm', n_fft_coh=10)
    tdat['LT83'] = bnr.calc_epsilon_LT83(tdat['psd'], tdat.velds.U_mag)
    tdat['noise'] = bnr.calc_doppler_noise(tdat['psd'], pct_fN=0.8)
    tdat['LT83_noise'] = bnr.calc_epsilon_LT83(tdat['psd'], tdat.velds.U_mag, noise=tdat['noise'])
    tdat['SF'] = bnr.calc_epsilon_SF(dat['vel'][0], tdat.velds.U_mag)
    tdat['TE01'] = bnr.calc_epsilon_TE01(dat, tdat)
    tdat['L'] = bnr.calc_L_int(acov, tdat.velds.U_mag)
    slope_check = bnr.check_turbulence_cascade_slope(
        tdat['psd'][-1].mean('time'), freq_range=[10, 100])
    tdat['psd_noise'] = bnr.calc_psd(dat['vel'], freq_units='rad', noise=[0.06, 0.04, 0.01])

    if make_data:
        save(tdat, 'vector_data01_bin.nc')
        return

    assert np.round(slope_check[0].values, 4), 0.1713
    assert_allclose(tdat, load('vector_data01_bin.nc'), atol=1e-6)


def test_adcp_turbulence(make_data=False):
    dat = tr.dat_sig_tide.copy(deep=True)
    dat.velds.rotate2('earth')
    dat.attrs['principal_heading'] = apm.calc_principal_heading(dat.vel.mean('range'))
    bnr = apm.ADPBinner(n_bin=20.0, fs=dat.fs, diff_style='centered')
    U_mag = dat.velds.U_mag
    dat["U_mag"] = U_mag
    tdat = bnr.do_avg(dat)

    tdat['dudz'] = bnr.calc_dudz(tdat["vel"])
    tdat['dvdz'] = bnr.calc_dvdz(tdat["vel"])
    tdat['dwdz'] = bnr.calc_dwdz(tdat["vel"])
    tdat['tau2'] = bnr.calc_shear2(tdat["vel"])
    tdat['I'] = tdat.velds.I
    tdat['ti'] = bnr.calc_ti(U_mag, detrend=False)
    dat.velds.rotate2('beam')

    tdat['psd'] = bnr.calc_psd(dat['vel'].isel(
        dir=2, range=len(dat["range"])//2), freq_units='Hz')
    tdat['noise'] = bnr.calc_doppler_noise(tdat['psd'], pct_fN=0.8)
    tdat['stress_vec4'] = bnr.calc_stress_4beam(
        dat, noise=tdat['noise'], orientation='up', beam_angle=25)
    tdat['tke_vec5'], tdat['stress_vec5'] = bnr.calc_stress_5beam(
        dat, noise=tdat['noise'], orientation='up', beam_angle=25, tke_only=False)
    # Back in "inst" coordinate frame now
    dat.velds.rotate2("beam")

    tdat['ti_noise'] = bnr.calc_ti(U_mag, detrend=False, noise=tdat['noise'])
    # This is "negative" for this code check
    tdat['wpwp'] = bnr.calc_tke(dat['vel_b5'], noise=tdat['noise'])
    tdat['dissipation_rate_LT83'] = bnr.calc_dissipation_LT83(
        tdat['psd'], tdat["U_mag"].isel(range=len(dat["range"])//2), freq_range=[0.2, 0.4])
    tdat['dissipation_rate_LT83_noise'] = bnr.calc_dissipation_LT83(
        tdat['psd'], tdat["U_mag"].isel(range=len(dat["range"])//2), freq_range=[0.2, 0.4], noise=tdat['noise'])
    tdat['dissipation_rate_SF'], tdat['noise_SF'], tdat['D_SF'] = bnr.calc_dissipation_SF(
        dat.vel.isel(dir=2), r_range=[1, 5])

    slope_check = bnr.check_turbulence_cascade_slope(
        tdat['psd'].mean('time'), freq_range=[0.4, 4])
    # Check noise subtraction in psd function
    tdat['psd_noise'] = bnr.calc_psd(dat['vel'].isel(
        dir=2, range=len(dat["range"])//2), freq_units='Hz', noise=0.01)

    tdat['friction_vel'] = bnr.calc_ustar_fit(
        tdat, upwp_=tdat['stress_vec5'].sel(tau='upwp_'), z_inds=slice(1, 5), H=50)

    if make_data:
        save(tdat, 'Sig1000_tidal_bin.nc')
        return

    with pytest.raises(Exception):
        bnr.calc_psd(dat['vel'], freq_units='Hz', noise=0.01)

    with pytest.raises(Exception):
        bnr.calc_psd(dat['vel'][0], freq_units='Hz', noise=0.01)

    assert np.round(slope_check[0].values, 4), -1.0682

    assert_allclose(tdat, load('Sig1000_tidal_bin.nc'), atol=1e-6)
