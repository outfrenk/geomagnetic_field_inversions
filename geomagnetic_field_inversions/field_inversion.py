import numpy as np
from scipy.interpolate import BSpline, interp1d
import scipy.sparse as scs
import scipy.linalg as scl
import pandas as pd
from typing import Union, Final
from pathlib import Path
from tqdm import tqdm

from .data_prep import StationData
from .forward_modules import frechet, fwtools
from .damping_modules import damping
from .tools import geod2geoc as g2g


class FieldInversion:
    """
    Calculates geomagnetic field coefficients based on inputted data and
    damping parameters using the approach of Korte et al. (????)
    """

    def __init__(self,
                 time_array: Union[list, np.ndarray],
                 maxdegree: int = 3,
                 r_model: float = 6371.2,
                 verbose: bool = False
                 ) -> None:
        """
        Initializes the Field Inversion class
        
        Parameters
        ----------
        time_array
            Sets timearray for the inversion in yr. Should be ascending
        maxdegree
            maximum order for spherical harmonics model, default 3
        r_model
            where the magnetic field is modeled (km distance from core)
        verbose
            Verbosity flag, defaults to False
        """
        # basic parameters
        self._SPL_DEGREE: Final[int] = 3

        # input parameters
        self.t_array = np.sort(time_array)
        self.maxdegree = maxdegree
        self.r_model = r_model
        self.verbose = verbose

        # derived properties
        self._bspline = BSpline.basis_element(np.arange(self._SPL_DEGREE+2),
                                              extrapolate=False)
        self.time_array = []
        self.data_array = []
        self.error_array = []
        self.accept_matrix = np.empty(0)
        self.types = []
        self.sc = 0  # station count
        self.types_ready = False
        self.types_sorted = np.empty(0)
        self.count_type = np.zeros(7)
        self.station_coord = np.zeros((0, 3))
        self.gcgd_conv = np.zeros((0, 2))
        self.damp_matrix = np.empty(0)
        self.spat_norm = np.empty(0)
        self.temp_norm = np.empty(0)
        self.splined_gh = np.empty(0)
        self.station_frechet = np.empty(0)
        self.res_iter = np.empty(0)
        self.unsplined_iter_gh = []
        self.dcname = []  # contains name of stations
        self.rejected = np.empty(0)

    @property
    def maxdegree(self):
        return self._maxdegree

    @maxdegree.setter
    def maxdegree(self, degree: int):
        # determines the maximum number of spherical coefficients
        self._nm_total = int((degree+1)**2 - 1)
        self._maxdegree = int(degree)
        self.spat_fac = np.zeros(self._nm_total)  # contains damping factors
        self.temp_fac = np.zeros(self._nm_total)
        self.matrix_ready = False

    @property
    def t_array(self):
        return self._t_array

    @t_array.setter
    def t_array(self, array: Union[list, np.ndarray]):
        # check time array
        if len(array) == 1:
            raise Exception('t_array should consist or more than one timestep')
        self._t_step = array[1] - array[0]
        self._t_array = array
        # number of temporal splines
        self.nr_splines = len(array) + self._SPL_DEGREE - 1
        # location of timeknots with small deviation for correct splines
        self.time_knots = np.linspace(
            array[0] - self._SPL_DEGREE * self._t_step * (1 + 1e-12),
            array[-1] + self._SPL_DEGREE * self._t_step * (1 + 1e-12),
            num=len(array) + 2*self._SPL_DEGREE)
        # check for equally spaced time array
        for i in range(len(array)-1):
            step = self._t_array[i+1] - self._t_array[i]
            if abs(step - self._t_step) > self._t_step * 1e-12:
                raise Exception("Time vector has different timesteps. "
                                " Redefine vector with same timestep. "
                                f"Difference: {abs(step - self._t_step)}")
        self.times = len(array)
        self.stat_ix = [[] for _ in range(len(array))]
        self.time_ix = [[] for _ in range(len(array))]
        self.matrix_ready = False

    def add_data(self,
                 data_class: StationData,
                 ) -> None:
        """
        Adds data generated by the Station_data class

        Parameters
        ----------
        data_class
            instance of the Station_data class. Only added if it matches the
            time_array set in __init__

        Creates or modifies
        -------------------
        self.data_array
            contains the measurements per site
            size= (# datatypes, len(measurements)) (floats)
        self.error_array
            contains the error in measurements per site
            size= (# datatypes, len(measurements)) (float)
        self.types
            contains the type of all data in one long list
            size= # datatypes (integers)
        self.station_coord
            contains the colatitude, longitude, and radius of station
            size= (# datatypes, 3) (floats)
        self.gcgd_conv
            contains conversion factors for geodetic to geocentric conversion
            of magnetic components mx/dx and mz/dz
            size= (# datatypes, 2) (floats)
        self.types_ready
            boolean indicating if datatypes (self.types) are logically sorted
        """
        # translation datatypes
        typedict = {"x": 0, "y": 1, "z": 2, "hor": 3,
                    "int": 4, "inc": 5, "dec": 6}
        if isinstance(data_class, StationData):
            # set up empty arrays
            time_entry = []
            data_entry = []
            error_entry = []
            types_entry = []
            name = data_class.__name__
            for c, types in enumerate(data_class.types):
                # check if data covers any spline
                if data_class.data[c][0][-1] < self.time_knots[0]\
                        or data_class.data[c][0][0] > self.time_knots[-1]:
                    raise Exception(f'{types} of {name} does not cover'
                                    ' any timestep of timeknots')

                # Extract data from StationData-class
                if self.verbose:
                    print(f'Adding {types}-type')
                # temporary data and error storage
                temp_d = data_class.data[c][1]
                temp_e = data_class.data[c][2]
                if types == 'inc' or types == 'dec':
                    # transform incl/decl data to radians
                    temp_d = np.radians(temp_d)
                    temp_e = np.radians(temp_e)

                # add data, error, and type to arrays
                time_entry.append(data_class.data[c][0])
                data_entry.append(temp_d)
                error_entry.append(temp_e)
                # count occurrence datatype and add to list
                types_entry.append(typedict[types])

            # change coordinates from geodetic to geocentric if required
            if data_class.geodetic:
                if self.verbose:
                    print(f'Coordinates are geodetic,'
                          ' translating to geocentric coordinates.')
                lat_geoc, r_geoc, cd, sd = g2g.latrad_in_geoc(
                    np.radians(data_class.lat), data_class.height)
                station_entry = np.array([0.5*np.pi - lat_geoc,
                                          np.radians(data_class.lon),
                                          r_geoc])
            else:
                if self.verbose:
                    print(f'Coordinates are geocentric,'
                          ' no translation required.')
                cd = 1.  # this will not change dx and dz when forming frechet
                sd = 0.
                station_entry = np.array([0.5*np.pi-np.radians(data_class.lat),
                                          np.radians(data_class.lon),
                                          6371.2+data_class.height*1e-3])

            # add data to attributes of the class if all is fine
            if self.verbose:
                print(f'Data of {name} is added to class')
            self.dcname.append(name)
            self.time_array.extend(time_entry)
            self.data_array.extend(data_entry)
            self.error_array.extend(error_entry)
            self.types.append(types_entry)  # is now one long list
            self.station_coord = np.vstack((self.station_coord, station_entry))
            self.gcgd_conv = np.vstack((self.gcgd_conv, np.array([cd, sd])))
            self.types_ready = False
            # station counter
            self.sc += 1
        else:
            raise Exception('data_class is not an instance of Station_Data')

    def prepare_inversion(self,
                          spat_fac: float = 0,
                          temp_fac: float = 0,
                          spat_type: int = 3,
                          temp_type: int = 7,
                          spat_ddip: bool = False,
                          temp_ddip: bool = True
                          ) -> None:
        """
        Function to prepare matrices for the inversion

        Parameters
        ----------
        spat_fac, temp_fac
            damping factor to be applied to the total damping matrix
        spat_type, temp_type
            integer corresponding to applied damping type
            defaults, respectively, to minimize Ohmic heat and acceleration
            magnetic field, both at cmb
        spat_ddip, temp_ddip
            boolean indicating whether to damp dipole coefficients.

        Creates or modifies
        -------------------
        self.spatdamp, self.tempdamp
            saves type of damping used
        self.station_frechet
            contains frechet matrix per location
            size= ((# stations x 3), nm_total) (floats)
        self.spat_fac, self.temp_fac
            contains the damping elements dependent on degree
             size= nm_total (floats) (see damp_types.py)
        self.spat_damp_matrix
            contains symmetric spatial damping matrix
            size= (nm_total x nr_splines, nm_total x nr_splines) (floats)
        self.temp_damp_matrix
            contains symmetric temporal damping matrix
            size= (nm_total x nr_splines, nm_total x nr_splines) (floats)
        self.matrix_ready
            indicates whether all matrices have been formed (boolean)
        self.types_ready
            boolean indicating if datatypes (self.types) are logically sorted
        """
        self.damp_matrix = np.zeros(
            (2 * self._SPL_DEGREE + 1, self.nr_splines * self._nm_total))
        # order data per spline
        # loop through dataset
        for index, time_array in enumerate(self.time_array):
            # loop through individual times
            for t_index, time in enumerate(time_array):
                nleft = int((time - self._t_array[0]) // self._t_step)
                if 0 <= nleft < len(self._t_array):
                    # TODO: revise
                    # index corresponds to time, data, and error
                    # add index of station
                    self.stat_ix[nleft].append(index)
                    # add index of data per station to spline
                    self.time_ix[nleft].append(t_index)
        ########################################
        # create even array with pandas then convert to numpy
        self.data_array = pd.DataFrame(self.data_array).to_numpy()
        self.time_array = pd.DataFrame(self.time_array).to_numpy()
        self.error_array = pd.DataFrame(self.error_array).to_numpy()

        # order datatypes in a more straightforward way
        # line of types_sorted corresponds to index
        if not self.types_ready:
            self.types_sorted = []
            for nr, stat in enumerate(self.types):
                for datum in stat:  # datum is 0 to 6
                    self.types_sorted.append(7*nr + datum)
            self.types_sorted = np.array(self.types_sorted)
            self.types_ready = True

        # calculate frechet dx, dy, dz for all stations
        if self.verbose:
            print('Calculating Schmidt polynomials and Fréchet coefficients')
        self.station_frechet = frechet.frechet_basis(
            self.station_coord, self._maxdegree)
        # geocentric correction
        dx, dz = g2g.frechet_in_geoc(
            self.station_frechet[:, 0], self.station_frechet[:, 2],
            self.gcgd_conv[:, 0], self.gcgd_conv[:, 1])
        self.station_frechet[:, 0] = dx
        self.station_frechet[:, 2] = dz

        # Prepare damping matrices
        if self.verbose:
            print('Calculating spatial damping matrix')
        if spat_fac != 0 and self._t_step != 0:
            spat_damp_diag, self.spat_fac = damping.damp_matrix(
                self._maxdegree, self.nr_splines, self._t_step,
                spat_fac, spat_type, spat_ddip)
            self.damp_matrix += spat_damp_diag
        if self.verbose:
            print('Calculating temporal damping matrix')
        if temp_fac != 0 and self._t_step != 0:
            temp_damp_diag, self.temp_fac = damping.damp_matrix(
                self._maxdegree, self.nr_splines, self._t_step,
                temp_fac, temp_type, temp_ddip)
            self.damp_matrix += temp_damp_diag

        self.matrix_ready = True
        if self.verbose:
            print('Calculations finished')

    def run_inversion(self,
                      x0: np.ndarray,
                      max_iter: int = 10,
                      path: Path = None,
                      ) -> None:
        """
        Runs the iterative inversion

        Parameters
        ----------
        x0
            starting model gaussian coefficients, should have length:
            (spherical_order + 1)^2 - 1 or
            (spherical_order + 1)^2 - 1 X nr_splines if changing through time
        max_iter
            maximum amount of iterations
        path
            path to location where to save normal_eq_splined and damp_matrix
            for calculating optional covariance and resolution matrix.
            If not provided, matrices are not solved. See tools/stdev.py

        Creates or modifies
        -------------------
        self.res_iter
             contains the RMS per datatype and the sum of all types
             size= 8 (floats)
        self.unsplined_iter_gh
            contains the BSpline function to unspline Gauss coeffs at any
            requested time (within range) for every iteration
            size= # iterations (BSpline functions)
        self.splined_gh
            contains the splined Gauss coeffs at all times of current iteration
            size= (len(nr_splines), nm_total) (floats)
        """
        # TODO: add uncertainty and data rejection
        if not self.matrix_ready:
            raise Exception('Matrices have not been prepared. '
                            'Please run prepare_inversion first.')
        # initiate array counting residual per type
        self.res_iter = np.zeros((max_iter+1, 8))
        # initiate splined values with starting model
        if self.verbose:
            print('Setting up starting model')
        self.splined_gh = np.zeros((self.nr_splines, self._nm_total))
        if x0.ndim == 1 and len(x0) == self._nm_total:
            self.splined_gh[:] = x0
        elif x0.shape == (self.nr_splines, self._nm_total):
            self.splined_gh = x0
        else:
            raise Exception(f'x0 has incorrect shape: {x0.shape}. \n'
                            f'It should have shape ({self._nm_total},) or'
                            f' ({self.nr_splines}, {self._nm_total})')

        spacing = self._nm_total * self._SPL_DEGREE
        sparse_damp = scs.dia_matrix(
            (self.damp_matrix,
             np.linspace(spacing, -spacing, 2*self._SPL_DEGREE+1)),
            shape=(len(self.damp_matrix[0]), len(self.damp_matrix[0])))
        for it in range(max_iter):  # start outer iteration loop
            if self.verbose:
                print(f'Start iteration {it+1}')
            rhs_array = np.zeros(self.nr_splines * self._nm_total)
            normal_eq_splined = np.zeros((self._nm_total * self.nr_splines,
                                          self._nm_total * self.nr_splines))

            rhs_damp = -sparse_damp.dot(self.splined_gh.flatten())

            gh_splfunc = BSpline(c=self.splined_gh, t=self.time_knots,
                                 k=self._SPL_DEGREE, axis=0, extrapolate=False)

            # Calculate frechet and residual matrix for all times
            for tix in range(len(self._t_array)):
                # use stations to make frechet for spline
                datapoints = self.types_sorted[self.stat_ix[tix]]
                station_nr = (datapoints // 7).astype(int)
                # contains all observational data in 7 rows
                forwobs_matrix = fwtools.forward_obs(gh_splfunc(self.time_array[self.stat_ix[tix], self.time_ix[tix]]), self.station_frechet[station_nr])
                # contains location per row
                frech_matrix = frechet.frechet_types(self.station_frechet[station_nr], datapoints, forwobs_matrix)
                # contains one row with all residuals
                res_matrix = fwtools.residual_obs(forwobs_matrix.flatten()[datapoints], self.data_array[self.stat_ix[tix], self.time_ix[tix]], datapoints)
                res_weight = res_matrix / self.error_array[self.stat_ix[tix], self.time_ix[tix]]

                # TODO: implement calculation weighted residual per datatype
            # res_weight = res_matrix / self.error_array
            # # sum residuals
            # self.count_type = np.zeros(7)
            # type06 = self.types_sorted % 7
            # for i in range(7):
            #     self.count_type[i] = np.sum(len(np.where(type06 == i)[0]))
            # self.res_iter[it] = fwtools.residual_type(
            #     res_weight, self.types_sorted, self.count_type)
            #
                # create rhs vector

                for spl1 in range(tix, min(tix+self._SPL_DEGREE+1, self.nr_splines)):
                    # create bspline factor using times
                    bspline1 = BSpline.basis_element(self.time_knots[spl1:spl1 + self._SPL_DEGREE + 2], extrapolate=False)(self.time_array[self.stat_ix[tix], self.time_ix[tix]])
                    bspline1[np.isnan(bspline1)] = 0
                    rhs_array[spl1 * self._nm_total:(spl1 + 1) * self._nm_total] += np.matmul(frech_matrix.T / self.error_array[self.stat_ix[tix], self.time_ix[tix]], res_weight * bspline1)
                    for spl2 in range(tix, min(tix+self._SPL_DEGREE+1, self.nr_splines)):
                        bspline2 = BSpline.basis_element(self.time_knots[spl2:spl2 + self._SPL_DEGREE + 2], extrapolate=False)(self.time_array[self.stat_ix[tix], self.time_ix[tix]])
                        bspline2[np.isnan(bspline2)] = 0
                        normal_eq_splined[spl1*self._nm_total:(spl1+1)*self._nm_total, spl2*self._nm_total:(spl2+1)*self._nm_total] += np.matmul(frech_matrix.T * bspline1 / self.error_array[self.stat_ix[tix], self.time_ix[tix]]**2, frech_matrix * bspline2[:, np.newaxis])

            # solve the equations
            if self.verbose:
                print('Prepare and solve equations')
            if np.all(normal_eq_splined[spl1*self._nm_total:(spl1+1)*self._nm_total, spl2*self._nm_total:(spl2+1)*self._nm_total] == 0):
                raise Exception('No data in last spline, shorten time_array')
            # create diagonals for quick inversion
            diag = np.zeros(((self._SPL_DEGREE + 1) * self._nm_total * 2 - 1,
                             len(normal_eq_splined)))
            # number of upper diagonals
            hdiags = int((self._SPL_DEGREE + 1) * self._nm_total - 1)
            diag[hdiags] = np.diag(normal_eq_splined)
            # upper to lower diagonal
            for i in range(hdiags):
                diag[i, hdiags-i:] = np.diagonal(normal_eq_splined, hdiags-i)
                diag[-(i+1), :-(hdiags-i)] = np.diagonal(
                    normal_eq_splined, -(hdiags-i))
            # add damping to required diagonals
            damp_diags = np.linspace(hdiags-spacing, hdiags+spacing,
                                     2*self._SPL_DEGREE + 1, dtype=int)
            diag[damp_diags] += self.damp_matrix
            # add damping to the vector
            rhs_array += rhs_damp
            # solve banded system
            update = scl.solve_banded((hdiags, hdiags), diag, rhs_array)

            self.splined_gh = (self.splined_gh.flatten() + update).reshape(
                self.nr_splines, self._nm_total)
            # despline Gauss coefficients and form function
            spline = BSpline(t=self.time_knots, c=self.splined_gh,
                             k=3, axis=0, extrapolate=False)
            self.unsplined_iter_gh.append(spline)

            # if self.verbose:
            #     print('Residual is %.2f' % self.res_iter[it, 7])
            # # residual after last iteration
            if it == max_iter - 1:
                if self.verbose:
                    print('Calculate residual last iteration')
                gh_splfunc = BSpline(c=self.splined_gh, t=self.time_knots,
                                     k=self._SPL_DEGREE, axis=0,
                                     extrapolate=False)(self._t_array)
                for tix in range(len(self._t_array)):
                    # use stations to make frechet for spline
                    datapoints = self.types_sorted[self.stat_ix[tix]]
                    station_nr = datapoints // 7
                    # contains all observational data in 7 rows
                    forwobs_matrix = fwtools.forward_obs(gh_splfunc(
                        self.time_array[self.stat_ix[tix], self.time_ix[tix]]),
                                                         self.station_frechet[
                                                             station_nr])
                    # contains one row with all residuals
                    res_matrix = fwtools.residual_obs(forwobs_matrix.flatten()[datapoints],
                        self.data_array[self.stat_ix[tix], self.time_ix[tix]], datapoints)
                    res_weight = res_matrix / self.error_array[self.stat_ix[tix], self.time_ix[tix]]
                    # TODO: make inversion quicker by combining into 4x4 matrix
                    # TODO: Fix residuals, final iteration, and saving
                # sum residuals
            #     self.res_iter[it+1] = fwtools.residual_type(
            #         res_weight, self.types_sorted, self.count_type)
            #     if self.verbose:
            #         print('Residual is %.2f' % self.res_iter[it+1, 7])
            #         print('Calculating spatial and temporal norms')
            #     if np.any(self.spat_fac != 0):
            #         self.spat_norm = damping.damp_norm(
            #             self.spat_fac, self.splined_gh, self.spat_ddt,
            #             self._t_step)
            #     if np.any(self.temp_fac != 0):
            #         self.temp_norm = damping.damp_norm(
            #             self.temp_fac, self.splined_gh, self.temp_ddt,
            #             self._t_step)
            #     if path is not None:
            #         if self.verbose:
            #             print('Saving matrices')
            #         save_diag = np.zeros(
            #             ((self._SPL_DEGREE + 1) * self._nm_total * 2 - 1,
            #              len(normal_eq_splined)))
            #         save_diag[hdiags] = np.diag(normal_eq_splined)
            #         # upper to lower diagonal
            #         for i in range(hdiags):
            #             save_diag[i, hdiags - i:] = np.diagonal(
            #                 normal_eq_splined, hdiags - i)
            #             save_diag[-(i + 1), :-(hdiags - i)] = np.diagonal(
            #                 normal_eq_splined, -(hdiags - i))
            #         dia_matrix = scs.dia_matrix(
            #             (save_diag, np.linspace(hdiags, -hdiags, 2*hdiags + 1)
            #              ), shape=(len(self.damp_matrix[0]),
            #                        len(self.damp_matrix[0])))
            #         scs.save_npz(path / 'forward_matrix', dia_matrix)
            #         scs.save_npz(path / 'damp_matrix', sparse_damp)
            #
                if self.verbose:
                    print('Finished inversion')

    def save_coefficients(self,
                          basedir: Union[Path, str] = '.',
                          file_name: str = 'coeff',
                          save_iterations: bool = True,
                          save_residual: bool = False,
                          ) -> None:
        """
        Save the Gauss coefficients at every timestep

        Parameters
        ----------
        basedir
            path where files will be saved
        file_name
            optional name to add to files
        save_iterations
            boolean indicating whether to save coefficients after
            each iteration. Is saved with the following shape:
             (# iterations, len(time vector), nm_total)
        save_residual
            boolean indicating whether to save the residuals of each timestep
        """
        # save residual
        if save_residual:
            residual_frame = pd.DataFrame(
                self.res_iter, columns=['res x', 'res y', 'res z', 'res hor',
                                        'res int', 'res incl', 'res decl',
                                        'res total'])
            residual_frame.to_csv(basedir / f'{file_name}_residual.csv',
                                  sep=';')

        if save_iterations:
            all_coeff = np.zeros((
                len(self.unsplined_iter_gh), self.times, self._nm_total))
            for i in range(len(self.unsplined_iter_gh)):
                all_coeff[i] = self.unsplined_iter_gh[i](self._t_array)
            np.save(basedir / f'{file_name}_all.npy', all_coeff)
        else:
            gh_time = self.unsplined_iter_gh[-1](self._t_array)
            np.save(basedir / f'{file_name}_final.npy', gh_time)

    def sweep_damping(self,
                      x0: Union[list, np.ndarray],
                      spatial_range: Union[list, np.ndarray],
                      temporal_range: Union[list, np.ndarray],
                      spat_dict: dict = None,
                      temp_dict: dict = None,
                      max_iter: int = 10,
                      basedir: Path = Path().absolute(),
                      overwrite: bool = True
                      ) -> None:
        """ Sweep through damping parameters to find ideal set

        Parameters
        ----------
        x0
            starting model gaussian coefficients, should be a float or
            as long as (spherical_order + 1)^2 - 1
        spatial_range
            array or list to vary spatial damping parameters. Can be None if
            temporal_range is inputted
        temporal_range
            array or list to vary temporal damping parameters.  Can be None if
            spatial_range is inputted
        spat_dict, temp_dict
            dictionary for spatial, temporal damping
            see prepare_inversion for more info
        max_iter
            maximum number of iterations. defaults to 5 iterations
        basedir
            path where files will be saved
        overwrite
            boolean indicating whether to overwrite existing files with
            exactly the same damping parameters. otherwise set of damping
            parameters is skipped over in the calculations.
        """
        if spat_dict is None:
            spat_dict = {"damp_type": 'Gubbins', "ddt": 0,
                         "damp_dipole": False}
        if temp_dict is None:
            temp_dict = {"damp_type": 'Br2cmb', "ddt": 2, "damp_dipole": True}

        for spatial_df in tqdm(spatial_range):
            spat_dict['df'] = spatial_df
            for temporal_df in temporal_range:
                temp_dict['df'] = temporal_df
                if overwrite or not (basedir / f'{spatial_df:.2e}s+'
                                               f'{temporal_df:.2e}t_final.npy'
                                     ).is_file():
                    self.prepare_inversion(spat_dict, temp_dict)
                    self.run_inversion(x0, max_iter)
                    self.save_coefficients(
                        file_name=f'{spatial_df:.2e}s+{temporal_df:.2e}t',
                        basedir=basedir, save_iterations=False,
                        save_residual=True)
