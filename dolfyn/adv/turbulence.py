import numpy as np
from ..velocity import VelBinner
import warnings
from ..tools.misc import slice1d_along_axis, _nans_like
from scipy.special import cbrt
import xarray as xr


class ADVBinner(VelBinner):
    """
    A class that builds upon `VelBinner` for calculating turbulence 
    statistics and velocity spectra from ADV data
    Parameters
    ----------
    n_bin : int
      The length of each `bin`, in number of points, for this averaging
      operator.
    fs : int
      Instrument sampling frequency in Hz
    n_fft : int (optional, default: n_fft = n_bin)
      The length of the FFT for computing spectra (must be <= n_bin)
    n_fft_coh : int
      Number of data points to use for coherence and cross-spectra ffts
      Default: `n_fft_coh`=`n_fft`
    noise : float, list or numpy.ndarray
      Instrument's doppler noise in same units as velocity
    """

    def __call__(self, ds, freq_units='rad/s', window='hann'):
        out = type(ds)()
        out = self.do_avg(ds, out)

        noise = ds.get('doppler_noise', [0, 0, 0])
        out['tke_vec'] = self.calc_tke(ds['vel'], noise=noise)
        out['stress_vec'] = self.calc_stress(ds['vel'])

        out['psd'] = self.calc_psd(ds['vel'],
                                   window=window,
                                   freq_units=freq_units,
                                   noise=noise)
        for key in list(ds.attrs.keys()):
            if 'config' in key:
                ds.attrs.pop(key)
        out.attrs = ds.attrs
        out.attrs['n_bin'] = self.n_bin
        out.attrs['n_fft'] = self.n_fft
        out.attrs['n_fft_coh'] = self.n_fft_coh

        return out

    def calc_stress(self, veldat, detrend=True):
        """
        Calculate the stresses (covariances of u,v,w)
        Parameters
        ----------
        veldat : xr.DataArray
            Velocity data array from ADV data. The last dimension is 
            assumed to be time.
        detrend : bool (default: True)
            detrend the velocity data (True), or simply de-mean it
            (False), prior to computing stress. Note: the psd routines
            use detrend, so if you want to have the same amount of
            variance here as there use ``detrend=True``.
        Returns
        -------
        out : xarray.DataArray
        """
        time = self.mean(veldat.time.values)
        vel = veldat.values

        # Will error for ADCP 4-beam
        out = np.empty(self._outshape(vel.shape)[:-1],
                       dtype=np.float32)

        if detrend:
            vel = self.detrend(vel)
        else:
            vel = self.demean(vel)

        for idx, p in enumerate(self._cross_pairs):
            out[idx] = np.nanmean(vel[p[0]] * vel[p[1]],
                                  -1, dtype=np.float64
                                  ).astype(np.float32)

        da = xr.DataArray(out, name='stress_vec',
                          dims=veldat.dims,
                          attrs={'units': 'm^2/^2'})
        da = da.rename({'dir': 'tau'})
        da = da.assign_coords({'tau': ["upvp_", "upwp_", "vpwp_"],
                               'time': time})
        return da

    def calc_csd(self, veldat,
                 freq_units='rad/s',
                 fs=None,
                 window='hann',
                 n_bin=None,
                 n_fft_coh=None):
        """
        Calculate the cross-spectral density of velocity components.
        Parameters
        ----------
        veldat   : xarray.DataArray
          The raw 3D velocity data.
        freq_units : string
          Frequency units of the returned spectra in either Hz or rad/s 
          (`f` or :math:`\\omega`)
        fs : float (optional)
          The sample rate (default: from the binner).
        window : string or array
          Specify the window function.
        n_bin : int (optional)
          The bin-size (default: from the binner).
        n_fft_coh : int (optional)
          The fft size (default: n_fft_coh from the binner).
        Returns
        -------
        csd : xarray.DataArray (3, M, N_FFT)
          The first-dimension of the cross-spectrum is the three
          different cross-spectra: 'uv', 'uw', 'vw'.
        """
        fs = self._parse_fs(fs)
        n_fft = self._parse_nfft_coh(n_fft_coh)
        time = self.mean(veldat.time.values)
        veldat = veldat.values

        out = np.empty(self._outshape_fft(veldat[:3].shape, n_fft=n_fft),
                       dtype='complex')

        # Create frequency vector, also checks whether using f or omega
        coh_freq = self.calc_freq(units=freq_units, coh=True)
        if 'rad' in freq_units:
            fs = 2*np.pi*fs
            freq_units = 'rad/s'
            units = 'm^2/s/rad'
        else:
            freq_units = 'Hz'
            units = 'm^2/s^2/Hz'

        for ip, ipair in enumerate(self._cross_pairs):
            out[ip] = self.calc_csd_base(veldat[ipair[0]],
                                         veldat[ipair[1]],
                                         n_bin=n_bin,
                                         n_fft=n_fft,
                                         window=window)

        csd = xr.DataArray(out, name='csd',
                           coords={'C': ['Cxy', 'Cxz', 'Cyz'],
                                   'time': time,
                                   'freq': coh_freq},
                           dims=['C', 'time', 'freq'],
                           attrs={'units': units, 'n_fft_coh': n_fft})
        csd['freq'].attrs['units'] = freq_units

        return csd

    def calc_epsilon_LT83(self, psd, U_mag, freq_range=[6.28, 12.57]):
        """
        Calculate the dissipation rate from the PSD
        Parameters
        ----------
        psd : xarray.DataArray (...,time,f)
          The power spectral density
        U_mag : xarray.DataArray (...,time)
          The bin-averaged horizontal velocity [m/s] (from dataset shortcut)
        freq_range : iterable(2)
          The range over which to integrate/average the spectrum, in units 
          of the psd frequency vector (Hz or rad/s)
        Returns
        -------
        epsilon : xarray.DataArray (...,n_time)
          dataArray of the dissipation rate
        Notes
        -----
        This uses the `standard` formula for dissipation:
        .. math:: S(k) = \\alpha \\epsilon^{2/3} k^{-5/3} + N
        where :math:`\\alpha = 0.5` (1.5 for all three velocity
        components), `k` is wavenumber, `S(k)` is the turbulent
        kinetic energy spectrum, and `N' is the doppler noise level
        associated with the TKE spectrum.
        With :math:`k \\rightarrow \\omega / U`, then -- to preserve variance --
        :math:`S(k) = U S(\\omega)`, and so this becomes:
        .. math:: S(\\omega) = \\alpha \\epsilon^{2/3} \\omega^{-5/3} U^{2/3} + N
        With :math:`k \\rightarrow (2\\pi f) / U`, then
        .. math:: S(\\omega) = \\alpha \\epsilon^{2/3} f^{-5/3} (U/(2\\pi))^{2/3} + N
        LT83 : Lumley and Terray, "Kinematics of turbulence convected
        by a random wave field". JPO, 1983, vol13, pp2000-2007.
        """
        freq = psd.freq

        idx = np.where((freq_range[0] < freq) & (freq < freq_range[1]))
        idx = idx[0]

        if freq.units == 'Hz':
            U = U_mag/(2*np.pi)
        else:
            U = U_mag

        a = 0.5
        out = (psd.isel(freq=idx) *
               freq.isel(freq=idx)**(5/3) / a).mean(axis=-1)**(3/2) / U

        out = xr.DataArray(out, name='dissipation_rate',
                           attrs={'units': 'm^2/s^3',
                                  'method': 'LT83'})
        return out

    def calc_epsilon_SF(self, vel_raw, U_mag, fs=None, freq_range=[2., 4.]):
        """
        Calculate dissipation rate using the "structure function" (SF) method
        Parameters
        ----------
        vel_raw : xarray.DataArray
          The raw velocity data (1D dimension time) upon 
          which to perform the SF technique. 
        U_mag : xarray.DataArray
          The bin-averaged horizontal velocity (from dataset shortcut)
        fs : float
          The sample rate of `vel_raw` [Hz]
        freq_range : iterable(2)
          The frequency range over which to compute the SF [Hz]
          (i.e. the frequency range within which the isotropic 
          turbulence cascade falls)
        Returns
        -------
        epsilon : xarray.DataArray
          dataArray of the dissipation rate
        """
        veldat = vel_raw.values
        if len(veldat.shape) > 1:
            raise Exception("Function input should be a 1D velocity vector")

        fs = self._parse_fs(fs)
        if freq_range[1] > fs:
            warnings.warn('Max freq_range cannot be greater than fs')

        dt = self.reshape(veldat)
        out = np.empty(dt.shape[:-1], dtype=dt.dtype)
        for slc in slice1d_along_axis(dt.shape, -1):
            up = dt[slc]
            lag = U_mag.values[slc[:-1]] / fs * np.arange(up.shape[0])
            DAA = _nans_like(lag)
            for L in range(int(fs / freq_range[1]), int(fs / freq_range[0])):
                DAA[L] = np.nanmean((up[L:] - up[:-L]) ** 2, dtype=np.float64)
            cv2 = DAA / (lag ** (2 / 3))
            cv2m = np.median(cv2[np.logical_not(np.isnan(cv2))])
            out[slc[:-1]] = (cv2m / 2.1) ** (3 / 2)

        return xr.DataArray(out, name='dissipation_rate',
                            coords=U_mag.coords,
                            dims=U_mag.dims,
                            attrs={'units': 'm^2/s^3',
                                   'method': 'structure function'})

    def _up_angle(self, U_complex):
        """
        Calculate the angle of the turbulence fluctuations.
        Parameters
        ----------
        U_complex  : |np.ndarray| (..., n_time * n_bin)
          The complex, raw horizontal velocity (non-binned)
        Returns
        -------
        theta : |np.ndarray| (..., n_time)
          The angle of the turbulence [rad]
        """
        dt = self.demean(U_complex)
        fx = dt.imag <= 0
        dt[fx] = dt[fx] * np.exp(1j * np.pi)

        return np.angle(np.mean(dt, -1, dtype=np.complex128))

    def _calc_epsTE01_int(self, I_tke, theta):
        """
        The integral, equation A13, in [TE01].
        Parameters
        ----------
        I_tke : |np.ndarray|
          (beta in TE01) is the turbulence intensity ratio:
          \\sigma_u / V
        theta : |np.ndarray|
          is the angle between the mean flow and the primary axis of
          velocity fluctuations
        """
        x = np.arange(-20, 20, 1e-2)  # I think this is a long enough range.
        out = np.empty_like(I_tke.flatten())
        for i, (b, t) in enumerate(zip(I_tke.flatten(), theta.flatten())):
            out[i] = np.trapz(
                cbrt(x**2 - 2/b*np.cos(t)*x + b**(-2)) *
                np.exp(-0.5 * x ** 2), x)

        return out.reshape(I_tke.shape) * \
            (2 * np.pi) ** (-0.5) * I_tke ** (2 / 3)

    def calc_epsilon_TE01(self, dat_raw, dat_avg, freq_range=[6.28, 12.57]):
        """
        Calculate the dissipation rate according to TE01.
        Parameters
        ----------
        dat_raw : xarray.Dataset
          The raw (off the instrument) adv dataset
        dat_avg : xarray.Dataset
          The bin-averaged adv dataset (calc'd from 'calc_turbulence' or
          'do_avg'). The spectra (psd) and basic turbulence statistics 
          ('tke_vec' and 'stress_vec') must already be computed.
        freq_range : iterable(2)
          The range over which to integrate/average the spectrum, in units 
          of the psd frequency vector (Hz or rad/s)
        Notes
        -----
        TE01 : Trowbridge, J and Elgar, S, "Turbulence measurements in
        the Surf Zone". JPO, 2001, vol31, pp2403-2417.
        """

        # Assign local names
        U_mag = dat_avg.velds.U_mag.values
        I_tke = dat_avg.velds.I_tke.values
        theta = np.angle(dat_avg.velds.U.values) - \
            self._up_angle(dat_raw.velds.U.values)
        freq = dat_avg['psd'].freq.values

        # Calculate constants
        alpha = 1.5
        intgrl = self._calc_epsTE01_int(I_tke, theta)

        # Index data to be used
        inds = (freq_range[0] < freq) & (freq < freq_range[1])
        psd = dat_avg.psd[..., inds].values
        freq = freq[inds].reshape([1] * (dat_avg.psd.ndim - 2) + [sum(inds)])

        # Estimate values
        # u & v components (equation 6)
        out = (np.nanmean((psd[0] + psd[1]) * freq**(5/3), -1) /
               (21/55 * alpha * intgrl))**(3/2) / U_mag

        # Add w component
        out += (np.nanmean(psd[2] * freq**(5/3), -1) /
                (12/55 * alpha * intgrl))**(3/2) / U_mag

        # Average the two estimates
        out *= 0.5

        return xr.DataArray(out, name='dissipation_rate',
                            coords={'time': dat_avg.psd.time},
                            dims='time',
                            attrs={'units': 'm^2/s^3',
                                   'method': 'TE01'})

    def calc_L_int(self, a_cov, U_mag, fs=None):
        """
        Calculate integral length scales.
        Parameters
        ----------
        a_cov : xarray.DataArray
          The auto-covariance array (i.e. computed using `calc_acov`).
        U_mag : xarray.DataArray
          The bin-averaged horizontal velocity (from dataset shortcut)
        fs : float
          The raw sample rate
        Returns
        -------
        L_int : |np.ndarray| (..., n_time)
          The integral length scale (T_int*U_mag).
        Notes
        ----
        The integral time scale (T_int) is the lag-time at which the
        auto-covariance falls to 1/e.
        If T_int is not reached, L_int will default to '0'.
        """
        acov = a_cov.values
        fs = self._parse_fs(fs)

        scale = np.argmin((acov/acov[..., :1]) > (1/np.e), axis=-1)
        L_int = U_mag.values / fs * scale

        return xr.DataArray(L_int, name='L_int',
                            coords={'dir': a_cov.dir, 'time': a_cov.time},
                            attrs={'units': 'm'})


def calc_turbulence(ds_raw, n_bin, fs, n_fft=None, freq_units='rad/s', window='hann'):
    """
    Functional version of `ADVBinner` that computes a suite of turbulence 
    statistics for the input dataset, and returns a `binned` data object.
    Parameters
    ----------
    ds_raw : xarray.Dataset
      The raw adv datset to `bin`, average and compute
      turbulence statistics of.
    freq_units : string
      Frequency units of the returned spectra in either Hz or rad/s 
      (`f` or :math:`\\omega`)
    window : 1, None, 'hann'
      The window to use for calculating power spectral densities
    Returns
    -------
    ds : xarray.Dataset
      Returns an 'binned' (i.e. 'averaged') data object. All
      fields (variables) of the input data object are averaged in n_bin
      chunks. This object also computes the following items over
      those chunks:
      - tke_vec : The energy in each component, each components is
        alternatively accessible as:
        :attr:`upup_ <dolfyn.velocity.Velocity.upup_>`,
        :attr:`vpvp_ <dolfyn.velocity.Velocity.vpvp_>`,
        :attr:`wpwp_ <dolfyn.velocity.Velocity.wpwp_>`)
      - stress_vec : The Reynolds stresses, each component is
        alternatively accessible as:
        :attr:`upwp_ <dolfyn.data.velocity.Velocity.upwp_>`,
        :attr:`vpwp_ <dolfyn.data.velocity.Velocity.vpwp_>`,
        :attr:`upvp_ <dolfyn.data.velocity.Velocity.upvp_>`)
      - U_std : The standard deviation of the horizontal
        velocity `U_mag`.
      - psd : DataArray containing the spectra of the velocity
        in radial frequency units. The data-array contains:
        - vel : the velocity spectra array (m^2/s/rad))
        - omega : the radial frequncy (rad/s)
    """
    calculator = ADVBinner(n_bin, fs, n_fft=n_fft)

    return calculator(ds_raw, freq_units=freq_units, window=window)
    