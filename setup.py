# The setup script for installing DOLfYN.
# from distutils.core import setup
from setuptools import setup, find_packages
import os
import shutil

# Change this to True if you want to include the tests and test data
# in the distribution.
include_tests = False

try:
    # This deals with a bug where the tests aren't excluded due to not
    # rebuilding the files in this folder.
    shutil.rmtree('dolfyn.egg-info')
except OSError:
    pass

# Get the version info We do this to avoid importing __init__, which
# depends on other packages that may not yet be installed.
base_dir = os.path.abspath(os.path.dirname(__file__))
version = {}
with open(base_dir + "/dolfyn/_version.py") as fp:
    exec(fp.read(), version)


config = dict(
    name='dolfyn',
    version=version['__version__'],
    description='Doppler Ocean Library for pYthoN.',
    author='DOLfYN Developers',
    author_email='levi.kilcher@nrel.gov',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        #'Topic :: Scientific/Engineering :: Earth Science',
    ],
    url='http://github.com/jmcvey3/dolfyn',
    packages=find_packages(exclude=['dolfyn.test']),
    # ['dolfyn', 'dolfyn.adv', 'dolfyn.io', 'dolfyn.data',
    #           'dolfyn.rotate', 'dolfyn.tools', 'dolfyn.adp', ],
    package_data={},
    install_requires=['numpy', 'scipy', 'xarray', 'h5netcdf'],
    #extras_require={'save':['h5netcdf']},
    provides=['dolfyn', ],
    scripts=['scripts/motcorrect_vector.py', 'scripts/vec2mat.py'], 
)


if include_tests:
    config['packages'].append('dolfyn.test')
    config['package_data'].update({'dolfyn.test': ['data/*']},)

setup(**config)
