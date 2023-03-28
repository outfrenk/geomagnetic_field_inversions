from matplotlib import cm
import numpy as np
from pathlib import Path
from typing import Union
import pandas as pd
import pyshtools as pysh


def plot_residuals(ax,
                   invmodel):
    """ Plots the residuals of the geomagnetic field inversion per iteration

    Parameters
    ----------
    ax
        Matplotlib axis object
    invmodel
        An instance of the `geomagnetic_field_inversion` class. This function
        only uses the res_iter attribute.
    """
    im = invmodel
    for i in range(8):
        if im.res_iter[0, i] > 0:
            if i == 0:
                ax.plot(np.arange(len(im.res_iter)),
                        im.res_iter[:, i] / im.res_iter[0, i],
                        color='black', label='rms_X',
                        linestyle='dotted')
            if i == 1:
                ax.plot(np.arange(len(im.res_iter)),
                        im.res_iter[:, i] / im.res_iter[0, i],
                        color='black', label='rms_Y',
                        linestyle='dashdot')
            if i == 2:
                ax.plot(np.arange(len(im.res_iter)),
                        im.res_iter[:, i] / im.res_iter[0, i],
                        color='black', label='rms_Z',
                        linestyle='dashed')
            if i == 3:
                ax.plot(np.arange(len(im.res_iter)),
                        im.res_iter[:, i] / im.res_iter[0, i],
                        color='black', label='rms_H')
            if i == 4:
                ax.plot(np.arange(len(im.res_iter)),
                        im.res_iter[:, i] / im.res_iter[0, i],
                        color='black', label='rms_int',
                        linestyle='dotted')
            if i == 5:
                ax.plot(np.arange(len(im.res_iter)),
                        im.res_iter[:, i] / im.res_iter[0, i],
                        color='black', label='rms_incl',
                        linestyle='dashdot')
            if i == 6:
                ax.plot(np.arange(len(im.res_iter)),
                        im.res_iter[:, i] / im.res_iter[0, i],
                        color='black', label='rms_decl',
                        linestyle='dashed')
            if i == 7:
                ax.plot(np.arange(len(im.res_iter)),
                        im.res_iter[:, i] / im.res_iter[0, i],
                        color='red', label='rms_all')
    return ax


def plot_gaussian(ax,
                  invmodel,
                  plot_degree: int = None,
                  degree: Union[list, np.ndarray] = None,
                  order: Union[list, np.ndarray] = None,
                  h_bool: Union[list, np.ndarray] = None,
                  plot_iter: int = -1):
    """ Plots Gaussian coefficients through time

    Parameters
    ----------
    ax
        Matplotlib axis object
    invmodel
        An instance of the `geomagnetic_field_inversion` class. This function
        uses the unsplined_iter, t_array, and _nm_total attributes.
    plot_degree
        integer of degree of all g's and h's to print.
        If given you do not have to use degree, order, and h_bool keywords.
    degree
        List containing the degrees of the gaussian coefficients to plot.
        should only include integers
    order
        List containing the order of the gaussian coefficients to plot.
        should only include integers
    h_bool
        Boolean list containing if gaussian coefficients is h (True)
        or g (False).
    plot_iter
        Determines which iteration is used to plot powerspectrum. Defaults to
        final iteration.
    """
    # TODO: add uncertainty bars
    if plot_degree is None:
        assert len(degree) == len(order) == len(h_bool),\
            'degree, order, and g_bool should have same length'
    else:
        degree = np.ones(2*plot_degree+1, dtype=int) * plot_degree
        order = np.zeros(len(degree), dtype=int)
        h_bool = np.zeros(len(degree), dtype=int)
        for i in range(1, plot_degree+1):
            order[2*i-1:2*i+1] = i
            h_bool[2*i] = True
    linestyles = ['solid', 'dotted', 'dashed', 'dashdot',
                  (0, (3, 5, 1, 5, 1, 5)), (0, (3, 10, 1, 10)), (0, (1, 10)),
                  (0, (3, 10, 1, 10, 1, 10))]
    markerstyles = ['o', 's', '*', 'D', 'x']
    colorstyles = ['black', 'grey', 'lightgrey']
    im = invmodel
    ordermap = np.arange(-1, 2*max(order), step=2, dtype=int)
    ordermap[0] = 0
    for i in range(len(degree)):
        coeff = degree[i] ** 2 - 1 + ordermap[order[i]] + h_bool[i]
        if h_bool[i]:
            ax.plot(im.t_array,
                    im.unsplined_iter[plot_iter, coeff::im._nm_total],
                    linestyle=linestyles[i % len(linestyles)],
                    marker=markerstyles[i % len(markerstyles)],
                    color=colorstyles[i % len(colorstyles)],
                    label=f'h$_{int(degree[i])}^{order[i]}$')
        else:
            ax.plot(im.t_array,
                    im.unsplined_iter[plot_iter, coeff::im._nm_total],
                    linestyle=linestyles[i % len(linestyles)],
                    marker=markerstyles[i % len(markerstyles)],
                    color=colorstyles[i % len(colorstyles)],
                    label=f'g$_{int(degree[i])}^{order[i]}$')
    return ax


def plot_powerspectrum(ax,
                       invmodel,
                       power: bool = True,
                       plot_time: Union[list, np.ndarray] = [-1],
                       plot_iter: int = -1):
    """ Plots the powerspectrum of gaussian coefficients and its variance

    Parameters
    ----------
    ax
        Matplotlib axis object
    invmodel
        An instance of the `geomagnetic_field_inversion` class. This function
        uses the unsplined_iter, t_array, _nm_total, and maxdegree attributes.
    power
        If True, plots powerspectrum of spherical orders.
        If False, plots average gaussian coefficient per order and mode.
    plot_time
        Determines which timestep is used to plot powerspectrum
        (list of indices). Defaults to averaging over all timesteps,
        which will also plot variance or std.
    plot_iter
        Determines which iteration is used to plot powerspectrum. Defaults to
        final iteration.
    """
    im = invmodel
    coeff_std = np.zeros(im._nm_total)
    coeff = im.unsplined_iter[plot_iter, :].reshape(im._nm_total, -1)
    if len(plot_time) > 1:
        coeff_gem = np.sum(coeff[:, plot_time],
                           axis=1) / len(im.t_array[plot_time])
        coeff_std = np.sqrt(np.sum((coeff[:, plot_time]
                                    - coeff_gem[:, np.newaxis])**2,
                                   axis=1) / len(im.t_array[plot_time]))
    else:
        if plot_time[0] == -1:
            coeff_gem = np.sum(coeff, axis=1) / len(im.t_array)
            coeff_std = np.sqrt(np.sum((coeff - coeff_gem) ** 2,
                                       axis=1) / len(im.t_array))
        else:
            coeff_gem = coeff[:, plot_time]
    if power:
        counter = 0
        sum_coeff_gem = np.zeros(im.maxdegree)
        sum_coeff_var = np.zeros(im.maxdegree)
        for l in range(im.maxdegree):
            for m in range(l+1):
                sum_coeff_gem[l] += coeff_gem[counter]**2
                sum_coeff_var[l] += coeff_std[counter]**2
                counter += 1
        ax.plot(np.arange(1, im.maxdegree+1), sum_coeff_gem,
                marker='o', label='power')
        if any(coeff_std != np.zeros(im._nm_total)):
            ax.plot(np.arange(1, im.maxdegree+1), sum_coeff_var,
                    marker='s', label='variance')
    else:
        if any(coeff_std != np.zeros(im._nm_total)):
            ax.errorbar(np.arange(1, im._nm_total+1), coeff_gem,
                        yerr=coeff_std, capsize=4, marker='o')
        else:
            ax.plot(np.arange(1, im._nm_total + 1), coeff_gem, marker='o')
    return ax


def plot_world(axes,
               invmodel,
               projection,
               plot_time: int,
               plot_iter: int = -1,
               plot_kw: dict = None):
    """ Plots the magnetic field on Earth given gaussian coefficients

    Parameters
    ----------
    axes
        3 Matplotlib axes objects with appropriate projection
    invmodel
        An instance of the `geomagnetic_field_inversion` class. This function
        uses the unsplined_iter, r_earth, t_array, _nm_total,
        and maxdegree attributes.
    projection
        Projection used for plotting on a world map. Should be an instance of
        cartopy.crs
    plot_time
        Determines which timestep is used to plot.
    plot_iter
        Determines which iteration is used to plot powerspectrum. Defaults to
        final iteration.
    plot_kw
        optional plotting parameters
    """
    default_kw = {'levelf_inc': np.arange(-90, 100, 10),
                  'level_inc': np.arange(-90, 100, 10),
                  'cmap_inc': 'RdBu_r',
                  'levelf_dec': np.arange(-180, 190, 10),
                  'level_dec': np.arange(-180, 190, 10),
                  'cmap_dec': 'RdBu_r',
                  'levelf_int': np.arange(0, 60000, 1000),
                  'level_int': np.arange(0, 60000, 1000),
                  'cmap_int': 'RdBu_r'}
    if plot_kw is None:
        plot_kw = default_kw
    else:
        for i in default_kw:
            if i not in plot_kw:
                plot_kw[i] = default_kw[i]

    im = invmodel
    # make a grid of coordinates and apply forward model
    forwlat = np.arange(-89, 90, 1)
    forwlon = np.arange(0, 360, 1)
    longrid, latgrid = np.meshgrid(forwlon, forwlat)
    latgrid = latgrid.flatten()
    longrid = longrid.flatten()
    world_coord = np.zeros((len(latgrid), 3))
    world_coord[:, 0] = (90 - latgrid) * np.pi/180
    world_coord[:, 1] = longrid * np.pi/180
    world_coord[:, 2] = im.r_earth
    X, Y, Z = create_forward(im, world_coord,
                             im.unsplined_iter[plot_iter,
                                               plot_time * im._nm_total:
                                               (plot_time + 1) * im._nm_total])
    H = np.sqrt(X ** 2 + Y ** 2)
    forward_int = (np.sqrt(X ** 2 + Y ** 2 + Z ** 2)).reshape(179, 360)
    forward_inc = (np.arctan2(Z, H) * 180 / np.pi).reshape(179, 360)
    forward_dec = (np.arctan2(Y, X) * 180 / np.pi).reshape(179, 360)

    axes[0].set_global()
    axes[0].contourf(forwlon, forwlat, forward_inc,
                     levels=plot_kw['levelf_inc'], cmap=plot_kw['cmap_inc'],
                     transform=projection)
    c = axes[0].contour(forwlon, forwlat, forward_inc,
                        levels=plot_kw['level_inc'], colors='k',
                        transform=projection)
    axes[0].coastlines()
    axes[0].gridlines()
    axes[0].clabel(c, fontsize=12, inline=True, fmt='%i')
    axes[0].set_title('Inclination')

    axes[1].set_global()
    axes[1].contourf(forwlon, forwlat, forward_dec,
                     levels=plot_kw['levelf_dec'], cmap=plot_kw['cmap_dec'],
                     transform=projection)
    c = axes[1].contour(forwlon, forwlat, forward_dec,
                        levels=plot_kw['level_dec'], colors='k',
                        transform=projection)
    axes[1].coastlines()
    axes[1].gridlines()
    axes[1].clabel(c, fontsize=12, inline=True, fmt='%i')
    axes[1].set_title('Declination')

    axes[2].set_global()
    axes[2].contourf(forwlon, forwlat, forward_int,
                     levels=plot_kw['levelf_int'], cmap=plot_kw['cmap_int'],
                     transform=projection)
    c = axes[2].contour(forwlon, forwlat, forward_int,
                        levels=plot_kw['level_int'], colors='k',
                        transform=projection)
    axes[2].coastlines()
    axes[2].gridlines()
    axes[2].clabel(c, fontsize=12, inline=True, fmt='%i')
    axes[2].set_title('Intensity')
    return axes


def plot_place(ax,
               invmodel,
               input_coord: Union[list, np.ndarray],
               incdecint: bool = True,
               plot_iter: int = -1):
    """ Plots the magnetic field on Earth given gaussian coefficients

    Parameters
    ----------
    ax
        Matplotlib axis objects
    invmodel
        An instance of the `geomagnetic_field_inversion` class. This function
        uses the unsplined_iter, t_array, _nm_total, and maxdegree attributes.
    input_coord
        Array of coordinates containing latitude, longitude, and radius.
    incdecint
        If True, inclination, declination, and intensity is plotted. If False,
        X, Y, and Z-components are plotted
    plot_iter
        Determines which iteration is used to plot powerspectrum. Defaults to
        final iteration.
    """
    im = invmodel
    X = np.zeros(len(im.t_array))
    Y = np.zeros(len(im.t_array))
    Z = np.zeros(len(im.t_array))
    coord = np.zeros((1, 3))
    coord[0, 0] = 0.5 * np.pi - np.radians(input_coord[0])
    coord[0, 1] = np.radians(input_coord[1])
    if len(input_coord) == 2:
        coord[0, 2] = im.r_earth
    else:
        coord[0, 2] = input_coord[2]
    for time in range(len(im.t_array)):
        X[time], Y[time], Z[time] = create_forward(
            im, coord, im.unsplined_iter[plot_iter,
                                         time * im._nm_total:
                                         (time + 1) * im._nm_total])
    if incdecint:
        H = np.sqrt(X ** 2 + Y ** 2)
        inty = (np.sqrt(X ** 2 + Y ** 2 + Z ** 2))
        inc = (np.arctan2(Z, H) * 180 / np.pi)
        dec = (np.arctan2(Y, X) * 180 / np.pi)
        ax2 = ax.twinx()
        ax.plot(im.t_array, inc, color='black', label='inc', marker='o')
        ax.plot(im.t_array, dec, color='black', label='dec',
                linestyle='dashed', marker='^')
        ax2.plot(im.t_array, inty, color='red', label='int',
                 linestyle='dashdot', marker='s')
        return ax, ax2
    else:
        ax.plot(im.t_array, X, color='black', label='X', marker='o')
        ax.plot(im.t_array, Y, color='black', label='Y', linestyle='dashed',
                marker='^')
        ax.plot(im.t_array, Z, color='black', label='Z', linestyle='dashdot',
                marker='s')
        return ax


def plot_sweep(ax,
               spatial_range: Union[list, np.ndarray],
               temporal_range: Union[list, np.ndarray],
               plot_spatial: bool = True,
               basedir: Union[str, Path] = '.',
               cmap: str = 'RdYlBu'):
    """ Produces a residual-modelsize plot to determine optimal damp parameters
    This function only works after running field_inversion.sweep_damping

    Parameters
    ----------
    ax
        Matplotlib axis object
    spatial_range
        range of spatial damping parameters
    temporal_range
        range of temporal damping parameters
    plot_spatial
        if True, plot spatial damping while temporal damping is static
        if False, plot temporal damping while spatial damping is static
    basedir
        path to coefficients and residuals after each iteration as produced by
        field_inversion.sweep_damping
    cmap
        matplotlib colormap used for plotting

    """
    basedir = Path(basedir)
    basedir.mkdir(exist_ok=True)

    modelsize = np.zeros((len(spatial_range), len(temporal_range)))
    res = np.zeros((len(spatial_range), len(temporal_range)))
    for j, temporal_df in enumerate(temporal_range):
        for i, spatial_df in enumerate(spatial_range):
            if (basedir / f'{spatial_df:.2e}s+{temporal_df:.2e}t_all_coeff.npy'
            ).is_file():
                coef = np.load(basedir / f'{spatial_df:.2e}s+{temporal_df:.2e}'
                                         't_all_coeff.npy')[-1]
            elif (basedir / f'{spatial_df:.2e}s+{temporal_df:.2e}t_final_'
                            'coeff.npy').is_file():
                coef = np.load(basedir / f'{spatial_df:.2e}s+'
                                         '{temporal_df:.2e}t_final_coeff.npy')
            else:
                raise Exception('Could not find file for spatial_df='
                                f'{spatial_df:.2e} and temporal_df='
                                f'{temporal_df:.2e} in {basedir}')
            modelsize[i, j] = np.linalg.norm(coef)
            res[i, j] = pd.read_csv(basedir / f'{spatial_df:.2e}s+'
                                              f'{temporal_df:.2e}t_'
                                              'residual.csv', delimiter=';'
                                    ).to_numpy()[-1, -1]
    if plot_spatial:
        colors = cm.get_cmap(cmap, len(temporal_range))
        for j in range(len(temporal_range)):
            ax.plot(modelsize[:, j], res[:, j], marker='o',
                    color=colors(j / len(temporal_range)))
    else:
        colors = cm.get_cmap(cmap, len(spatial_range))
        for i in range(len(spatial_range)):
            ax.plot(modelsize[i, :], res[i, :], marker='o',
                    color=colors(i / len(spatial_range)))

    return ax


def create_forward(invmodel,
                   coord: Union[np.ndarray, list],
                   coeff: Union[np.ndarray, list]):
    """

    Parameters
    ----------
    invmodel
        An instance of the `geomagnetic_field_inversion` class. This function
        uses the maxdegree, r_earth, _nm_total, and  attributes.
    coord
        An array of length N x 3 with colatitude (radians!),
        longitude (radians!), and radius.
    coeff
        gaussian coefficients used to calculate forward field.
    Returns
    -------
    X, Y, Z
        Geomagnetic field components
    """
    im = invmodel
    frechet_matrix = forward_operator(im, coord)
    forward_result = np.matmul(frechet_matrix, coeff)
    X = forward_result[:len(coord)]
    Y = forward_result[len(coord):2*len(coord)]
    Z = forward_result[2*len(coord):]
    return X, Y, Z


def forward_operator(invmodel,
                     station_coord: Union[np.ndarray, list]):
    """Calculates the field at a given point

    Parameters
    ----------
    invmodel
        An instance of the `geomagnetic_field_inversion` class. This function
        uses the maxdegree, r_earth, _nm_total, and unsplined_iter attributes.
    station_coord
        List of coordinates (phi, theta) of stations

    Returns
    -------
    frechet_matrix
        frechet matrix (G)
    """
    im = invmodel
    schmidt_P = np.zeros((len(station_coord), int((im.maxdegree + 1)
                                                  * (im.maxdegree + 2) / 2)))
    schmidt_dP = np.zeros((len(station_coord), int((im.maxdegree + 1)
                                                   * (im.maxdegree + 2) / 2)))
    for i, coord in enumerate(station_coord):
        schmidt_P[i], schmidt_dP[i] = pysh.legendre.PlmSchmidt_d1(
            im.maxdegree, np.cos(coord[0]))
        schmidt_dP[i] *= -np.sin(coord[0])
    frechet_matrix = np.zeros((len(station_coord) * 3, im._nm_total))
    counter = 0
    for n in range(1, im.maxdegree + 1):
        index = int(n * (n + 1) / 2)
        mult_factor = (im.r_earth / station_coord[:, 2]) ** (n + 1)
        frechet_matrix[:len(station_coord), counter] =\
            mult_factor * schmidt_dP[:, index]
        frechet_matrix[len(station_coord):2*len(station_coord), counter] = 0
        frechet_matrix[2*len(station_coord):, counter] = \
            -mult_factor * (n + 1) * schmidt_P[:, index]
        counter += 1
        for m in range(1, n + 1):
            # First the g-elements
            frechet_matrix[:len(station_coord), counter] = \
                mult_factor * schmidt_dP[:, index + m] \
                * np.cos(m * station_coord[:, 1])
            frechet_matrix[len(station_coord):2*len(station_coord), counter] =\
                m / np.sin(station_coord[:, 0]) * mult_factor \
                * np.sin(m * station_coord[:, 1]) \
                * schmidt_P[:, index + m]
            frechet_matrix[2*len(station_coord):, counter] = \
                -mult_factor * (n + 1) * schmidt_P[:, index + m] \
                * np.cos(m * station_coord[:, 1])
            counter += 1
            # Now the h-elements
            frechet_matrix[:len(station_coord), counter] = \
                mult_factor * schmidt_dP[:, index + m] \
                * np.sin(m * station_coord[:, 1])
            frechet_matrix[len(station_coord):2*len(station_coord), counter] =\
                -m / np.sin(station_coord[:, 0]) * mult_factor \
                * np.cos(m * station_coord[:, 1]) \
                * schmidt_P[:, index + m]
            frechet_matrix[2*len(station_coord):, counter] = \
                -mult_factor * (n + 1) * schmidt_P[:, index + m] \
                * np.sin(m * station_coord[:, 1])
            counter += 1
    return frechet_matrix