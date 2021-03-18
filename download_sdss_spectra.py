#! /usr/bin/env python3.9
from time import time

import numpy as np
import pandas as pd

from constants_sdss import spectra_path
from lib_processing_sdss import DownloadData
################################################################################
ti = time.time()
################################################################################
# Sort by SNR
gs = pd.read_csv(f'{spectra_path}/gals_DR16.csv')

# Use z_noqso if possible
gs.z = np.where(gs.z_noqso.ne(0), gs.z_noqso, gs.z)
#gs['z'] = [row['z_noqso'] if row['z_noqso']!=0 else row['z'] for i, row in gs.iterrows()]
#gs['test'] = [row['z_noqso'] if row['z_noqso']!=0 else row['z'] for i, row in gs.iterrows()]
#n = np.count_nonzero(np.where(gs.z==gs.test, True, False))
# Remove galaxies with redshift z<=0.01
gs = gs[gs.z > 0.01]
gs.index = np.arange(len(gs))
#
# # Choose the top n_obs median SNR objects
n_obs = -1

if n_obs != -1:
    gs = gs[:n_obs]

# Data Download

download_spectra = DownloadData(
    files_data_frame=gs, download_path=spectra_path, n_processes=60)

download_spectra.get_files()

################################################################################
tf = time.time()

print(f'Running time: {tf-ti:.2f} [seg]')
