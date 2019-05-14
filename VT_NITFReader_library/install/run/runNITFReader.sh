#!/bin/sh

export NITRO_PREFIX=/usr/local

export LD_LIBRARY_PATH=../lib:${NITRO_PREFIX}/lib:${LD_LIBRARY_PATH}
export NITF_PLUGIN_PATH=${NITRO_PREFIX}/share/nitf/plugins

#../bin/VT_NITFReader -file ${1}
install/bin/VT_NITFReader -file ${1}
