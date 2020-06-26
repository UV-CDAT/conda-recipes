# conda-recipes

This repository contains tools for:
- CDAT developers to build their conda packages, create a test environment, and upload the built package to conda channel. The tools are under *build_tools*, the main script is *build_tools/conda_build.py*. *conda_build.py* can be called from project's *Makefile* which can then be called from project's *.circleci/config.yml*.

# Notes for CDAT developers

In order to use *build_tools/conda_build.py*, create a conda environment and activate the *base* environment. 

## Clone conda-recipes repository.

Clone conda-recipes repository to a work directory (referred as $WORKDIR in this documentation).

```
export WORKDIR=<some_work_directory>
git clone https://github.com/CDAT/conda-recipes $WORKDIR/conda-recipes
export BUILD_SCRIPT=$WORKDIR/conda-recipes/build_tools/conda_build.py
```
Run *build_tools/conda_build.py --help* to get information about this script.

Clone the CDAT project you want to build. For example, to clone *cdms* project:

```
git clone https://github.com/CDAT/cdms
cd cdms
```

Set the following environment variables.
```bash  
  export **PKG_NAME**=<package_name>
  export **REPO_NAME**=<repo_name>
  export **LAST_STABLE**=<last_stable_version>
  export **BRANCH**=<project_branch>
  export **CONDA_ACTIVATE**=<conda_path>/bin/activate
  export **CONDA_ENV**=<test_environment_name>
```

For example:
```
export PKG_NAME=cdms2
export REPO_NAME=cdms
export LAST_STABLE=3.1.4
export BRANCH=fix_flake8
export CONDA_ACTIVATE=/home/username/miniconda3/bin/activate
export PYTHON_VERSION=3.7
export CONDA_ENV=test_cdms
```

## Rerender


First step in building a conda package is to do a rerendering which will pick up latest conda-forge update so that we get latest pinned dependencies. You will need *recipe/meta.yaml.in* in the project repo

```bash
$ python $BUILD_SCRIPT --workdir $WORKDIR --last_stable $LAST_STABLE \
		       --build 0 --package_name $PKG_NAME --repo_name $REPO_NAME \
		       --branch $BRANCH --do_rerender 
```

## Build

```bash
$ export EXTRA_CHANNELS=cdat/label/nightly
$ python $BUILD_SCRIPT --workdir $WORKDIR --package_name $PKG_NAME \
  	 --repo_name $REPO_NAME --build_version $PYTHON_VERSION \
	 --extra_channels $EXTRA_CHANNELS \
	 --conda_activate $CONDA_ACTIVATE --do_build
```

## Setup an environment with the built package
```bash
conda create -y -n $CONDA_ENV --use-local -c $EXTRA_CHANNEL $PKG_NAME 
```

For example, to create a test environment for running cdms test cases:
```bash
conda create -y -n $CONDA_ENV --use-local -c $EXTRA_CHANNELS $PKG_NAME testsrunner pytest
```




