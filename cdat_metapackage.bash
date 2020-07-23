#!/bin/bash -x
export VERSION=8.2.1.rc1
export CDAT_VERSION=8.2.1.rc1
export CDAT_INFO_VERSION=8.2.1.rc1
export CDTIME_VERSION=3.1.4.rc1
export CDMS_VERSION=3.1.5.rc3
export GENUTIL_VERSION=8.2.1.rc2
export CDUTIL_VERSION=8.2.1.rc1
export VTK_CDAT_VERSION=8.2.0.8.2.1.rc1
#export LIBNETCDF_VERSION=
export BUILD=0
export OP="=="
export CHANNELS="-c conda-forge/label/cdat_dev -c conda-forge -c cdat/label/cdat_dev"
conda metapackage cdat ${CDAT_VERSION} \
    ${CHANNELS} \
    --build-number ${BUILD} --dependencies \
    "cdat_info ${OP}${CDAT_INFO_VERSION}" \
    "cdtime ${OP}${CDTIME_VERSION}" \
    "cdms2 ${OP}${CDMS_VERSION}" \
    "genutil ${OP}${GENUTIL_VERSION}" \
    "vtk-cdat ${OP}${VTK_CDAT_VERSION}" \
    "dv3d ${OP}${VERSION}" \
    "vcs ${OP}${VERSION}" \
    "wk ${OP}${VERSION}" \
    "vcsaddons ${OP}${VERSION}" \
    matplotlib basemap jupyter cdp output_viewer esmpy scipy ipywidgets notebook


