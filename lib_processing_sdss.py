import os
import glob
import time
import urllib


import astropy.io.fits as pyfits
from functools import partial
import matplotlib
import matplotlib.pyplot as plt
import multiprocessing as mp
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

from constants_sdss import n_waves, wave_master
from constants_sdss import working_dir, science_arxive_server_path
from constants_sdss import processed_spectra_path, spectra_path
################################################################################
class DataProcessing:

    def __init__(self, galaxies_df, n_processes): #fnames: list, SN_threshold: float):

        self.galaxies_df = galaxies_df
        self.n_processes = n_processes
        self.spectra = None

        self.raw_spectra_path = f'{spectra_path}/raw_spectra'
        if not os.path.exists(self.raw_spectra_path):
            os.makedirs(self.raw_spectra_path, exist_ok=True)

        self.interpolated_spectra_path = f'{spectra_path}/interpolated_spectra'
        if not os.path.exists(self.interpolated_spectra_path):
            os.makedirs(self.interpolated_spectra_path, exist_ok=True)

        self.processed_spectra_path = f'{spectra_path}/processed_spectra'
        if not os.path.exists(self.processed_spectra_path):
            os.makedirs(self.processed_spectra_path, exist_ok=True)

    def indefinite_values_handler(self, spectra: 'np.array',
        discard_fraction: 'float'=0.1):
        #global wave_master

        print(f'spectra shape before keep_spec_mask: {spectra.shape}')

        n_indef = np.count_nonzero(~np.isfinite(spectra), axis=0)
        print(n_indef[:10])
        print(f'Indefinite vals in the input array: {np.sum(n_indef)}')

        keep_flux_mask =  n_indef < spectra.shape[0]*discard_fraction

        self.spectra = spectra[:, keep_flux_mask]
        print(f'spectra shape after keep_spec_mask: {spectra.shape}')

        wave = wave_master[keep_flux_mask]

        n_indef = np.count_nonzero(~np.isfinite(spectra), axis=0)
        print(f'[New] Indefinite vals in the input array: {np.sum(n_indef)}')

    # # Replacing indefinite values in a spectrum with its nan median
    #     for flx in spec.T:
    #         flx[np.where(~np.isfinite(flx))] = np.nanmedian(flx)
    #
    #     print(f'indf vals: {np.count_nonzero(~np.isfinite(spec))}')
        return self.spectra, wave_master

    def sort_spec_SN(self, spectra: 'array'):

        SN_arg_sort = np.argsort(spectra[:, -1])
        self.spectra = spectra[SN_arg_sort]

        return self.spectra

    def spec_to_single_array(self, fnames: 'list'):

        n_spec = len(fnames)
        self.spectra = np.empty((n_spec, n_waves))

        for idx, fname in enumerate(fnames):

            print(f'Processing spectra N° {idx} --> {fname}', end='\r')
            self.spectra[idx, :] = np.load(fname)

        return self.spectra


    def get_fluxes_SN(self):

        print(f'Saving fluxes, spec-ID and SN to {self.raw_spectra_path}')

        params = range(len(self.galaxies_df))

        with mp.Pool(processes=self.n_processes) as pool:
            res = pool.map(self._get_flux_SN, params)
            n_failed = sum(res)

        print(f'Fluxes and SN saved in {self.raw_spectra_path}')
        print(f'Failed to save {n_failed}')

    def _get_flux_SN(self, idx_galaxy: int):

        galaxy_fits_path, fname = self._galaxy_fits_path(idx_galaxy)
        fname = fname.split('.')[0]
        [plate, mjd, fiberid] = fname.split('-')[1:]

        if not os.path.exists(galaxy_fits_path):
            print(f'{fname} not found')
            return 1

        wave, flux, z_SN = self._rest_frame(idx_galaxy, galaxy_fits_path)

        flux_interpolated = np.interp(wave_master, wave, flux, left=np.nan, right=np.nan)

        np.save(f'{self.raw_spectra_path}/{fname}.npy',
            np.hstack(
                (flux, int(plate), int(mjd), int(fiberid), z_SN)
            )
        )

        np.save(f'{self.interpolated_spectra_path}/{fname}_interpolated.npy',
            np.hstack(
                (flux_interpolated, int(plate), int(mjd), int(fiberid), z_SN)
            )
        )

        return 0

    def _rest_frame(self, idx_galaxy, galaxy_fits_path):
        """De-redshifting"""

        with pyfits.open(galaxy_fits_path) as hdul:
            wave = 10. ** (hdul[1].data['loglam'])
            flux = hdul[1].data['flux']


        z = self.galaxies_df.iloc[idx_galaxy]['z']
        z_factor = 1./(1. + z)
        wave *= z_factor

        SN = self.galaxies_df.iloc[idx_galaxy]['snMedian']

        return wave, flux, np.array([z, SN])

    def _galaxy_fits_path(self, idx_galaxy: int):

        galaxy = self.galaxies_df.iloc[idx_galaxy]
        plate, mjd, fiberid, run2d = self._galaxy_identifiers(galaxy)

        fname = f'spec-{plate}-{mjd}-{fiberid}.fits'

        SDSSpath = f'sas/dr16/sdss/spectro/redux/{run2d}/spectra/lite/{plate}'
        retrieve_path = f'{spectra_path}/{SDSSpath}'

        return f'{retrieve_path}/{fname}', fname

    def _galaxy_identifiers(self, galaxy):

        plate = f"{galaxy['plate']:04}"
        mjd = f"{galaxy['mjd']}"
        fiberid = f"{galaxy['fiberid']:04}"
        run2d = f"{galaxy['run2d']}"

        return plate, mjd, fiberid, run2d

    # def processing_spectra(self):
    #
    #     for idx, fname in enumerate(self.fnames[:self.SN_threshold]):
    #
    #         SN = fname.split('SN_')[-1].split('.')[0]
    #         SN = float(SN)
    #         self.SN_array[idx] = SN
    #
    #         print(f'Processing spectra N° {idx} --> {fname}', end='\r')
    #         self.spectra[idx, :] = np.load(fname)
    #
    #     self._sort_SN()
    #
    #     return self.spectra
    #
    #
    # def _sort_SN(self):
    #
    #     ids_sort_SN = np.argsort(self.SN_array)
    #
    #     self.spectra[:, :] = self.spectra[ids_sort_SN, :]
    #
    #
    # def _indefinite_values_handler(self):
    #     pass
################################################################################
# def proc_spec(fnames):
#
#     print('Processing all spectra')
#
#     N = len(fnames)
#     spec = np.empty((N, wave_master.size))
#
#     for idx, fname in enumerate(fnames[:N]):
#         print(f'Processing spectra N° {idx+1} --> {fname}', end='\r')
#         spec[idx, :] = np.load(fname)
#
#     print(f'indf vals: {np.count_nonzero(~np.isfinite(spec))}')
#
# # Discarding spectrum with more than 10% of indefininte
# # valunes in a given wl for al training set
#     wkeep = np.where(np.count_nonzero(~np.isfinite(spec), axis=0) < spec.shape[0] / 10)
# # Removing one dimensional axis since wkeep is a tuple
#     spec = np.squeeze(spec[:, wkeep])
#     wave_master = np.squeeze(spec[:, wkeep])
#
#     print(f'indf vals: {np.count_nonzero(~np.isfinite(spec))}')
#
# # Replacing indefinite values in a spectrum with its nan median
#     for flx in spec.T:
#         flx[np.where(~np.isfinite(flx))] = np.nanmedian(flx)
#
#     print(f'indf vals: {np.count_nonzero(~np.isfinite(spec))}')
#
# # Nomalize by the median and reduce noise with the standar deviation
#     spec *= 1/np.median(spec, axis=1).reshape((spec.shape[0], 1))
# #    spec *= 1/np.std(spec, axis=1).reshape((spec.shape[0], 1))
#
#
#     np.save(f'spec_{N}.npy', spec)
#     np.save(f'wave_master.npy', wave_master)
#
# def get_spectra(gs, dbPath):
#     """
#     Computes the spectra interpolating over a master grid of wavelengths
#     Parameters
#     ----------
#     gs : Pandas DataFrame with info of the galaxies
#     dbPath : String : Path to data base
#
#     Returns
#     -------
#     wave_master_grid : numpy array 1-D : The master wavelength grid
#     flxs :  numpy array 2-D : Interpolated spectra over the grid
#     """
#
#     print(f'Getting grid of wavelengths and spectra from {len(gs)} .fits files')
#     # http://python.omics.wiki/multiprocessing_map/multiprocessing_partial_function_multiple_arguments
#     f = partial(flx_rest_frame_i, gs, dbPath)
#
#     # close the pool (with) & do partial before
#     with mp.Pool() as pool:
#         pool.map(f, range(len(gs)))
#
#
# #
#     print('Job finished')
#
#
# def flx_rest_frame_i(gs, dbPath, i):
#     """
#     Computes the min and max value in the wavelenght grid for the ith spectrum.
#     Computes the interpolation functtion for the ith spectrum.
#     Parameters
#     ----------
#     gs : Pandas DataFrame with info of the galaxies
#     dbPath : String : Path to data base
#     i : int : Index of .fits file in the DataFrame
#     Returns
#     -------
#     min : float : minimum value if the wavelength grid for the ith spectrum
#     max : float : maximun value if the wavelength grid for the ith spectrum
#     flx_intp :  interp1d object : Interpolation function for the ith spectrum
#     """
#
#     obj = gs.iloc[i]
#     plate = obj['plate']
#     mjd = obj['mjd']
#     fiberid = obj['fiberid']
#     run2d = obj['run2d']
#     z = obj['z']
#
#     print(f'Processing spectrun N° {i}', end='\r')
#     flx_rest_frame(plate, mjd, fiberid, run2d, z, dbPath)
#
#
# def flx_rest_frame(plate, mjd, fiberid, run2d, z, dbPath):
#     """
#     Computes the min and max value in the wavelenght grid for the spectrum.
#     Computes the interpolation functtion for the spectrum.
#     Parameters
#     ----------
#     plate : int : plate number
#     mjd : int : mjd of observation (days)
#     fiberid : int : Fiber ID
#     run2d : str : 2D Reduction version of spectrum
#     z : float : redshift, replaced by z_noqso when available.
#     (z_nqso --> Best redshift when excluding QSO fit in BOSS spectra (right redshift to use for galaxy targets))
#     dbPath : String : Path to data base
#     Returns
#     -------
#     wl_min : float : minimum value of the wavelength grid for the spectrum
#     wl_max : float : maximun value of the wavelength grid for the spectrum
#     flx_intp :  interp1d object : Interpolation function for the spectrum
#
#     """
#     # Path to the .fits file of the target spectrum
#     fname = f'spec-{plate:04}-{mjd}-{fiberid:04}.fits'
#     SDSSpath = f'{science_arxive_server_path}\
#         dr16/sdss/spectro/redux/{run2d}/spectra/lite/{plate:04}'
#     dest = f'{SDSSpath}/{fname}'
#
#
#     if not(os.path.exists(dest)):
#         print(f'File {fname} not found!')
#         return None
#
#     with pyfits.open(dest) as hdul:
#         wl_rg = 10. ** (hdul[1].data['loglam'])
#         flx = hdul[1].data['flux']
#
#
#     # Deredshifting & min & max
#     z_factor = 1./(1. + z)
#     wl_rg *= z_factor
#     flx = np.interp(wave_master, wl_rg, flx, left=np.nan, right=np.nan)
#
#     np.save(
#         f'{spectra_path}/{fname.split(".")[0]}_wave_master.npy',
#         flx)
################################################################################
class DownloadData:

    def __init__(self, files_data_frame, download_path, n_processes):
        """
        files_data_frame: Pandas DataFrame with all the imformation of the sdss
        galaxies

        download_path: (string) Path where the data will be downloaded
        """
        self.data_frame = files_data_frame
        self.download_path = download_path
        self.n_processes = n_processes

    def get_files(self):

        print(f'*** Getting {len(self.data_frame)} fits files ****')
        start_time_download = time.time()

        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

        params = range(len(self.data_frame))

        with mp.Pool(processes=self.n_processes) as pool:
            res = pool.map(self._get_file, params)
            n_failed = sum(res)

        finish_time_download = time.time()

        print(f'Done! Finished downloading .fits files...')
        print(f'Failed to download {n_failed} files' )
        print(
            f'Download took {finish_time_download-start_time_download:.2f}[s]')


    def _get_file(self, idx_data_frame):

        object = self.data_frame.iloc[idx_data_frame]
        plate, mjd, fiberid, run2d = self._file_identifier(object)

        fname = f'spec-{plate}-{mjd}-{fiberid}.fits'

        SDSSpath = f'sas/dr16/sdss/spectro/redux/{run2d}/spectra/lite/{plate}'
        folder_path = f'{self.download_path}/{SDSSpath}'

        url =\
        f'https://data.sdss.org/{SDSSpath}/{fname}'

        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)

        # Try & Except a failed Download

        try:
            self._retrieve_url(url, folder_path, fname)
            print(f'returning 0')
            return 0

        except Exception as e:

            print(f'Failed : {url}')

            print(f'returning 1')
            print(f'{e}')
            return 1

    def _retrieve_url(self, url, folder_path, fname):

        if not(os.path.isfile(f'{folder_path}/{fname}')):

            print(f'Downloading {fname}')

            urllib.request.urlretrieve(url, f'{folder_path}/{fname}')

            file_size = os.path.getsize(f'{folder_path}/{fname}')

            j = 0

            while j < 10 and (file_size < 60000):

                os.remove(f'{folder_path}/{fname}')
                urllib.request.urlretrieve(url, f'{folder_path}/{fname}')
                j += 1
                time.sleep(1)

            file_size = os.path.getsize(f'{folder_path}/{fname}')

            if file_size < 60000:
                print(f"Size of {fname}: {file_size}... Removing file!!")
                os.remove(f'{folder_path}/{fname}')
                raise Exception('Spectra wasn\'t found')

        else:
            print(f'{fname} already downloaded!!')


    def _file_identifier(self, object):

        plate = f"{object['plate']:04}"
        mjd = f"{object['mjd']}"
        fiberid = f"{object['fiberid']:04}"
        run2d = f"{object['run2d']}"

        return plate, mjd, fiberid, run2d
