#!/bin/bash -x
export VERSION=8.2.1
export CDAT_VERSION=8.2.1
export CDAT_INFO_VERSION=8.2.1
export CDTIME_VERSION=3.1.4
export CDMS_VERSION=3.1.5
export GENUTIL_VERSION=8.2.1
export CDUTIL_VERSION=8.2.1
export VTK_CDAT_VERSION=8.2.0.8.2.1
export BUILD=0
export OP="=="
export CHANNELS="-c conda-forge -c cdat/label/v8.2.1"
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
    matplotlib jupyter cdp output_viewer esmpy scipy ipywidgets notebook


