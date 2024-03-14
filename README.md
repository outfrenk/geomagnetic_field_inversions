# geomagnetic_field_inversions
Library for the numerical inversion of geomagnetic field data. This code is based on Fortran Code provided by Monica Korte and two papers:
- Korte, M., & Constable, C. (2003). [Continuous global geomagnetic field models for the past 3000 years.](https://www.sciencedirect.com/science/article/pii/S0031920103001651) Physics of the Earth and Planetary Interiors, 140(1-3), 73-89. [10.1016/j.pepi.2003.07.013](https://doi.org/10.1016/j.pepi.2003.07.013)
- Korte, M., Donadini, F., & Constable, C. G. (2009). [Geomagnetic field for 0–3 ka: 2. A new series of time‐varying global models.](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2008GC002297) Geochemistry, Geophysics, Geosystems, 10(6). [10.1029/2008GC002297](https://doi.org/10.1029/2008GC002297)

## Library
The library consists of two main modules:
- `geomagnetic_field_inversions/data_prep.py`: contains methods for correctly preparing data for the `FieldInversion`-class. This method stores all required parameters per station into one class, which can then be imported directly into `FieldInversion`. The class takes a csv-file of declination, inclination, intensity, x, y, z, and/or h-component magnetic data + accompanying data errors.
- `geomagnetic_field_inversions/field_inversion.py`: contains the `FieldInversion`-class that performs the actual inversion of geomagnetic field data. It requires, besides the time vector over which the inversion will take place, an instance of `InputData` as minimum input.

## Installation
In order to get the inversion code running, you need to have the Clang compiler and the OpenMP libraries installed.
The easiest way to get a working set up is using the conda dependency manager, e.g. from [here](https://github.com/conda-forge/miniforge).
Replacing <env-name> with a name of your choice, you can create a conda environment with all dependencies provided using:
```
conda create --name <env-name> clang cython llvm-openmp "python<=3.11"
```
Then you can run
```
pip install . -U
```
in the root directory of the repository, to install the package.

Uninstallation is possible by typing in the terminal (possibly in the specific virtual environment):
```
pip uninstall geomagnetic_field_inversions
```
## Tutorial
We have provided four tutorials to make the library easier to use and understand. You can find the jupyter notebooks containing the tutorials in the `doc`-folder.
The tutorials are:
1. Tutorial 1: loading data and running a model. In this Tutorial we show how to load data into the `InputData`-class, and teach you the basics of the `FieldInversion`-class (including several damping types).
2. Tutorial 2: plotting results. We show some basic plotting tools allowing a better understanding of the created geomagnetic model. Examples consist of residual plots, gauss coefficients, powerspectra, and global magnetic field maps. 
3. Tutorial 3: sweeping through models. We show how to loop through models with different damping parameters to find a optimal model with the help of the elbow-plot and powerspectra.
4. Tutorial 4: loading geomagia dataset. We show how to load a geomagia dataset with our `InputData`-class.

All files required for the tutorials are also found in the `doc`-folder.

## Testing
All tests for this library can be found in the `test`-folder. To run the tests you need to have pytest installed.
After installation of pytest, you can test the code by typing `pytest`.

## Accompanying Article
The Article describing this library can be found at:

## Acknowledgements
This Library is based on years of geomagnetic code development by:
- many people
