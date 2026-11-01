#!/bin/bash
set -euo pipefail
P=/home/claude/opt; S=$P/src; L=$P/logs; J=2
export PATH=$P/bin:$PATH LD_LIBRARY_PATH=$P/lib:${LD_LIBRARY_PATH:-} CPATH=$P/include
step(){ echo "=== $(date +%T) $1"; }
# FFTW: system runtime library + header from the FFTW source
mkdir -p $P/include $P/lib
cp $S/fftw3/api/fftw3.h $P/include/
ln -sf /usr/lib/x86_64-linux-gnu/libfftw3.so.3 $P/lib/libfftw3.so
step MPICH
if [ ! -x $P/bin/mpicc ]; then
cd $S && tar xzf mpich-4.2.3.tar.gz && cd mpich-4.2.3
./configure --prefix=$P --disable-fortran --with-device=ch3:nemesis --disable-doc > $L/mpich.log 2>&1
make -j$J >> $L/mpich.log 2>&1 && make install >> $L/mpich.log 2>&1
fi
step HDF5
cd $S && rm -rf hdf5-1.14.6 && tar xzf hdf5-1.14.6.tar.gz && cd hdf5-1.14.6
./configure --prefix=$P --disable-fortran --disable-tests --enable-hl --with-zlib=/usr > $L/hdf5.log 2>&1
make -j$J >> $L/hdf5.log 2>&1 && make install >> $L/hdf5.log 2>&1
step netCDF-C
rm -rf $S/netcdf-c/build
cmake -S $S/netcdf-c -B $S/netcdf-c/build -DCMAKE_INSTALL_PREFIX=$P -DCMAKE_PREFIX_PATH=$P -DENABLE_DAP=OFF -DENABLE_BYTERANGE=OFF \
  -DENABLE_TESTS=OFF -DBUILD_UTILITIES=ON -DENABLE_NCZARR=OFF -DENABLE_PLUGINS=OFF -DENABLE_FILTER_TESTING=OFF > $L/netcdf.log 2>&1
cmake --build $S/netcdf-c/build -j$J >> $L/netcdf.log 2>&1 && cmake --install $S/netcdf-c/build >> $L/netcdf.log 2>&1
step netCDF-CXX4
cmake -S $S/netcdf-cxx4 -B $S/netcdf-cxx4/build -DCMAKE_INSTALL_PREFIX=$P -DCMAKE_PREFIX_PATH=$P -DNCXX_ENABLE_TESTS=OFF -DENABLE_FILTER_TESTING=OFF > $L/ncxx.log 2>&1
cmake --build $S/netcdf-cxx4/build -j$J >> $L/ncxx.log 2>&1 && cmake --install $S/netcdf-cxx4/build >> $L/ncxx.log 2>&1
step BOUT++
cmake -S $S/BOUT-dev -B $S/BOUT-dev/build -DCMAKE_INSTALL_PREFIX=$P -DCMAKE_PREFIX_PATH=$P -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=$P/bin/mpicc -DCMAKE_CXX_COMPILER=$P/bin/mpicxx \
  -DBOUT_USE_FFTW=ON -DFFTW_ROOT=$P -DBOUT_USE_NETCDF=ON -DBOUT_DOWNLOAD_NETCDF_CXX4=OFF -DBOUT_USE_PETSC=OFF -DBOUT_USE_SUNDIALS=OFF \
  -DBOUT_ENABLE_PYTHON=OFF -DBOUT_TESTS=OFF -DBOUT_BUILD_EXAMPLES=OFF -DBOUT_UPDATE_GIT_SUBMODULE=OFF > $L/bout.log 2>&1
cmake --build $S/BOUT-dev/build -j$J >> $L/bout.log 2>&1 && cmake --install $S/BOUT-dev/build >> $L/bout.log 2>&1
step DONE
