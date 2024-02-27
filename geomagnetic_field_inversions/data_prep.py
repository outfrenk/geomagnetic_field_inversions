import numpy as np
import pandas as pd
from pathlib import Path
from warnings import warn
from typing import Union, Optional
from .tools import latrad_in_geoc


class InputData(object):
    """Class that contains geomagnetic data and locations in order to perform
    a geomagnetic field inversion

    Attributes
    ----------
    data : DataFrame
        The DataFrame containing all data.
    n_inp : int
        The number of inputs, i.e. rows of the DataFrame
    loc : array
        The unique inputs of data locations (lat, lon, radius, cd, and sd)
    loc_idx: array
        The array connecting index loc to data input
    time: array
        The array containing dated time of magnetic record
    idx_X, idx_Y, idx_Z, idx_H, idx_D, idx_I, idx_F : index
        The indices of X, Y, Z, H, dec, inc, and int records in the DataFrame.
    n_out : int
        The number of outputs, i.e. the total number of individual data points.
    outputs : array
        The outputs (order is X, Y, Z, H, dec, inc, int)
    std_out : array
        The output-errors.
    compiled : boolean
        Whether indices for data have been compiled
    """
    def __init__(self):
        self.data = pd.DataFrame(
            columns=['lat', 'lon', 'h', 't', 'X', 'dX', 'Y', 'dY', 'Z', 'dZ',
                     'H', 'dH', 'D', 'dD', 'I', 'dI', 'F', 'dats',
                     'alpha95', 'geoc', 'geoc_colat', 'geoc_rad', 'cd', 'sd'])
        self.n_inp, self.n_out = 0, 0
        self.loc = np.zeros((0, 5))
        self.loc_idx, self.time = np.zeros(0), np.zeros(0)
        self.idx_X,  self.idx_Y = np.zeros(0), np.zeros(0)
        self.idx_Z, self.idx_H = np.zeros(0), np.zeros(0)
        self.idx_D,  self.idx_I = np.zeros(0), np.zeros(0)
        self.idx_F, self.idx_out = np.zeros(0), np.zeros(0)
        self.outputs, self.std_out = np.zeros(0), np.zeros(0)
        self.compiled = False

    def read_data(self,
                  dfs: Union[list, pd.DataFrame],
                  ) -> None:
        """ Reads Pandas DataFrame(s) and stores in class

        Parameters
        ----------
        dfs
            (list with instances of) Pandas DataFrame. Contains data + error
             on either X/Y/Z/(H) component or inc/dec/int components or both.
            Header should be:
             'lat' (latitude), 'lon' (longitude), 'h' (optional: height above
              geoid in m), 't' (time), 'X'/'Y'/'Z'/'H' (x/y/z/h),
             'I'/'D'/'F' (inc/dec/int), 'dX'/'dY'/'dZ'/'dH' (x/y/z/h-error),
             'dD'/'dI'/'dF' (dec/inc/int error),
             'alpha95' (a95 error for both dec and inc error)
             'geoc' (only set to 1 if data is obtained in geocentric dataframe)

        Method updates data
        """
        # check for list -> enables processing multiple DataFrames
        if not isinstance(dfs, list):
            dfs = [dfs]

        for df in dfs:
            # this evades errors due to missing column names
            df = df.reindex(df.columns.union(self.data.columns, sort=False),
                            axis=1)
            # drop rows not containing basic information
            df.dropna(subset=['lat', 'lon', 't'], how='any', inplace=True)
            # check latitude and longitude
            llcond = (
                (abs(df['lat']) > 90)
                | ((df['lon'] > 360) | (df['lon'] < -180))
            )
            llind = df.where(llcond).dropna(how='all').index
            if llind.size != 0:
                raise Exception(f"Records with indices {llind.values} contain "
                                f"latitude or longitude out of range. \n"
                                f"Change before proceeding!")
            df['lon'] = df['lon'].where(df['lon'] <= 180, df['lon'] - 360)
            df['h'] = df['h'].where(df['h'].notna(), other=0)

            # indicate geodetic (0) or geocentric (1)
            df['geoc'] = df['geoc'].where(df['geoc'].notna(), other=0)
            df['geoc_colat'] = 90. - df['lat']
            df['geoc_rad'] = 6371.2 + df['h'] * 1e-3
            df['cd'] = 1.
            df['sd'] = 0.
            # apply geocentric correction
            temp, rad, cd, sd = latrad_in_geoc(
                np.radians(df['lat'].to_numpy()),
                df['h'].to_numpy().astype('float'))
            colat = 90 - np.degrees(temp)
            # only replace geodetic values
            gd_cond = df['geoc'] != 0
            df['geoc_colat'] = df['geoc_colat'].where(gd_cond, other=colat)
            df['geoc_rad'] = df['geoc_rad'].where(gd_cond, other=rad)
            df['cd'] = df['cd'].where(gd_cond, other=cd)
            df['sd'] = df['sd'].where(gd_cond, other=sd)

            # add dataframe to big dataframe
            # XXX: This gives a warning with new pandas version, as the initial
            # dataframe is empty.
            self.data = pd.concat([self.data, df[self.data.columns]],
                                  ignore_index=True)

            self.compiled = False

    def compile_data(self,
                     verbose: bool = False
                     ) -> None:
        """ Compiles data ready for quick use in geomagnetic field inversions

        Parameters
        ----------
        verbose
            if True, returns status report of number of data points

        Method updates data, loc_idx, loc, time, n_inp, idx_..., n_out,
        outputs, and errs
        """
        self.compiled = False
        # obtain index lists pointing to data quickly
        data = self.data
        data.reset_index(inplace=True)
        # for quick access to stations
        uniq_loc, indices = np.unique(data[['geoc_colat', 'lon', 'geoc_rad',
                                            'cd', 'sd'
                                            ]].to_numpy().astype('float'),
                                      return_inverse=True, axis=0)
        # check geodetic/geocentric discrepancies
        uniq_loc_check = np.unique(data[['lat', 'lon', 'h']
                                        ].to_numpy().astype('float'), axis=0)
        if not (len(uniq_loc) == len(uniq_loc_check)):
            raise Exception('Location has both geocentric and geodetic data!')

        # DataFrame indices for D, I and F records
        self.n_inp = len(uniq_loc)
        self.idx_X = data.query('X==X').index
        self.idx_Y = data.query('Y==Y').index
        self.idx_Z = data.query('Z==Z').index
        self.idx_H = data.query('H==H').index
        self.idx_F = data.query('F==F').index
        self.idx_I = data.query('I==I').index
        self.idx_D = data.query('D==D').index
        self.idx_out = np.concatenate((self.idx_X, self.idx_Y, self.idx_Z,
                                       self.idx_H, self.idx_F, self.idx_I,
                                       self.idx_D)).flatten()
        # indices to quickly transform forward return matrices to the same
        # form as outputs
        self.idx_res = np.cumsum(
            [
                0,
                len(self.idx_X),
                len(self.idx_Y),
                len(self.idx_Z),
                len(self.idx_H),
                len(self.idx_F),
                len(self.idx_I),
                len(self.idx_D),
            ]
        )

        self.n_out = len(self.idx_out)
        # get same order as outputs
        self.loc = uniq_loc
        self.loc_idx = indices[self.idx_out]
        self.time = data['t'].loc[self.idx_out].to_numpy()
        # vector of data
        self.outputs = np.concatenate((data['X'].loc[self.idx_X],
                                       data['Y'].loc[self.idx_Y],
                                       data['Z'].loc[self.idx_Z],
                                       data['H'].loc[self.idx_H],
                                       data['F'].loc[self.idx_F],
                                       data['I'].loc[self.idx_I],
                                       data['D'].loc[self.idx_D])
                                      ).astype(float)
        # vector of errors
        self.std_out = np.concatenate((data['dX'].loc[self.idx_X],
                                       data['dY'].loc[self.idx_Y],
                                       data['dZ'].loc[self.idx_Z],
                                       data['dH'].loc[self.idx_H],
                                       data['dF'].loc[self.idx_F],
                                       data['dI'].loc[self.idx_I],
                                       data['dD'].loc[self.idx_D])
                                      ).astype(float)
        self.compiled = True
        if verbose:
            print(self)

    def __repr__(self):
        if self.n_out:
            return (
                f'Data from t={min(self.time)} to t={max(self.time)}\n'
                f'This dataset contains {self.n_out} records from '
                f'{self.n_inp} locations.\n'
                f'It consists of {self.idx_D.size} declinations, '
                f'{self.idx_I.size} inclinations and {self.idx_F.size} '
                f'intensities, {self.idx_X.size} x-data, '
                f'{self.idx_Y.size} y-data, {self.idx_Z.size} z-data, and '
                f'{self.idx_H.size} h-data.'
            )
        else:
            return 'This object does not contain any data.'


def read_geomagia(fname: Union[str, Path],
                  drop_duplicates: bool = True,
                  default_a95: float = 4.5,
                  **kw_args,
                  ) -> Optional[InputData]:
    """ Reads geomagia csv-file(s) format

    Parameters
    ----------
    fname
        string or Path-object of geomagia formatted file to read
    drop_duplicates
        if True, drops duplicate rows, i.e. rows that are exactly the same
    a95
        default error for alpha95, only used if no error is found in the file
    kw_args
        optional keyword argument(s) used for reading DataFrame with
        Input_data.read_data()

    Returns
    -------
        Pandas DataFrame of inputted geomagia data
    """
    # Missing values are indicated by either one of
    na = ('9999', '999', '999.9', 'nan', '-999', '-9999')
    # Read data as DataFrame
    try:
        dat = pd.read_csv(
            fname,
            usecols=['Age[yr.AD]', 'Sigma-ve[yr.]', 'Sigma+ve[yr.]',
                     'Ba[microT]', 'SigmaBa[microT]', 'Dec[deg.]',
                     'Inc[deg.]', 'Alpha95[deg.]', 'SiteLat[deg.]',
                     'SiteLon[deg.]'],
            na_values={'Sigma-ve[yr.]': (-1), 'Sigma+ve[yr.]': (-1),
                       'Ba[microT]': na, 'SigmaBa[microT]': na,
                       'Dec[deg.]': na, 'Inc[deg.]': na,
                       'Alpha95[deg.]': na},
            header=1, sep=',', skipinitialspace=True)
        # Rename columns
        ren_dict = {'Age[yr.AD]': 't', 'Sigma-ve[yr.]': 'dt_lo',
                    'Sigma+ve[yr.]': 'dt_up', 'Ba[microT]': 'F',
                    'SigmaBa[microT]': 'dF', 'Dec[deg.]': 'D',
                    'Inc[deg.]': 'I', 'SiteLat[deg.]': 'lat',
                    'SiteLon[deg.]': 'lon', 'Alpha95[deg.]': 'alpha95'}
    # TODO: make better statement to differentiate between sed and volc
    except ValueError:
        dat = pd.read_csv(
            fname,
            usecols=['Age[yr.BP]', 'Lat[deg.]', 'Lon[deg.]',
                     'Dec[deg.]', 'Inc[deg.]',
                     'SigmaDec[deg.]', 'SigmaInc[deg.]'],
            na_values={'Dec[deg.]': na, 'Inc[deg.]': na,
                        'SigmaDec[deg.]': na, 'SigmaInc[deg.]': na},
            header=1, sep=',', skipinitialspace=True, index_col=False)
        dat['Age[yr.BP]'] = -1 * dat['Age[yr.BP]'] + 1950
        # Rename columns
        ren_dict = {'Age[yr.BP]': 't', 'Dec[deg.]': 'D', 'Inc[deg.]': 'I',
                    'Lat[deg.]': 'lat', 'Lon[deg.]': 'lon',
                    'SigmaDec[deg.]': 'dD', 'SigmaInc[deg.]': 'dI'}
    dat.rename(ren_dict, inplace=True, axis='columns')

    # check if data already occurs and drop duplicates if wished so:
    if drop_duplicates:
        dat.drop_duplicates(subset=['lat', 'lon', 'rad', 't'],
                            inplace=True)
    dat.dropna(subset=['lat', 'lon', 't'], inplace=True)
    dat.dropna(subset=['D', 'I', 'F'], how='all', inplace=True)
    dat.reset_index(inplace=True, drop=True)

    dat['alpha95'] = dat['alpha95'].where(
        (dat['D'].isna() & dat['I'].isna()) ^ dat['alpha95'].notna(),
        other=default_a95,
    )
    # dat['dat'] = np.clip(dat['dat'], 5, None)
    # Correct sqrt(2) error
    # dat['alpha95'] = np.clip(dat['alpha95'], np.sqrt(2) * 3.4, None)
    dat['dI'] = dat['alpha95'] * 57.3 / 140.
    cond = dat['D'].notna() & dat['I'].isna()  # fix alpha95 issues
    # Get the corresponding indices
    ind = dat.where(cond).dropna(how='all').index
    if ind.size != 0:
        warn(f"Records with indices {ind.values} contain "
             f"declination, but not inclination! No default error "
             f"(force_error_d) has been inputted.\n"
             f"To be able to use the provided data, these "
             f"records have been dropped from the output.",
             UserWarning)
        dat.drop(dat.where(cond).dropna(how='all').index,
                 inplace=True)

    dat['dD'] = dat['dI'] / np.abs(np.cos(np.deg2rad(dat['I'])))

    return dat
