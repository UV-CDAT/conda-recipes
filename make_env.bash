#!/usr/bin/env bash

export RELEASE="v82"
export PREPEND_CHANNEL="-c cdat/label/test"
export PREPEND_CHANNEL=""
export APPEND_CHANNEL=""

#export ACTIVATE_COMMAND="conda"
export ACTIVATE_COMMAND="source"
export CREATE="y"

echo "ACTIVATE COMMAND: ${ACTIVATE_COMMAND}"

#export CONDA_BASE=$(conda info --base)
#echo "CONDA_BASE: $CONDA_BASE"


${ACTIVATE_COMMAND} deactivate
${ACTIVATE_COMMAND} activate base
conda config --add channels conda-forge
conda config --set channel_priority strict

#source $CONDA_BASE/etc/profile.d/conda.sh

for PYVER in 2.7 3.6 3.7
    do
        if [ $PYVER == "2.7" ]; then
	    PYVER_STR = "python<3"
	elif [ $PYVER == "3.6" ]; then
            PYVER_STR = "python>=3.6,<3.7"
	else
            PYVER_STR = "python>=3.7"
	fi
        for MESA in y n
        do
            if [ $MESA == "y" ]; then
                export MESA_NAME="-nox"
                export MESA_PKG="mesalib"
            else
                export MESA_NAME=""
                export MESA_PKG=""
            fi
            echo "Doing version $PYVER with mesalib set to $MESA"
            if [ ${CREATE} == "y" ]; then
                conda create -y -n cdat-${RELEASE}${MESA_NAME}_py$PYVER ${PREPEND_CHANNEL} -c conda-forge -c cdat/label/${RELEASE} ${APPEND_CHANNEL} cdat python=$PYVER ${MESA_PKG}
            fi
            ${ACTIVATE_COMMAND} activate cdat-${RELEASE}${MESA_NAME}_py$PYVER
            echo $(conda list vtk)
            conda env export --no-builds > cdat-${RELEASE}${MESA_NAME}_py$PYVER.$(uname).yaml 
            ${ACTIVATE_COMMAND} deactivate
            ${ACTIVATE_COMMAND} activate base
        done
    done

