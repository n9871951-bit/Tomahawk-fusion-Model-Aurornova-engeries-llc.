#!/bin/bash
# Build BOUT++ 5.1.1 + elm-pb on Kaggle (same sources and options as the tested workspace build, plus CHECK=0 for speed).
set -euo pipefail
P=/tmp/bout; S=$P/src; L=$P/logs; J=$(nproc)
mkdir -p $S $L $P/include $P/lib
export PATH=$P/bin:$PATH LD_LIBRARY_PATH=$P/lib:${LD_LIBRARY_PATH:-}
step(){ echo "=== $(date +%T) $1"; }
step "system packages (FFTW, zlib)"
if ! (apt-get update -qq && apt-get install -y -qq libfftw3-dev zlib1g-dev) > $L/apt.log 2>&1; then
  echo "apt failed; building FFTW from source"
  cd $S && curl -sSLO https://www.fftw.org/fftw-3.3.10.tar.gz && tar xzf fftw-3.3.10.tar.gz && cd fftw-3.3.10
  ./configure --prefix=$P --enable-shared > $L/fftw.log 2>&1 && make -j$J >> $L/fftw.log 2>&1 && make install >> $L/fftw.log 2>&1
fi
cd $S
curl -sSLO https://github.com/pmodels/mpich/releases/download/v4.2.3/mpich-4.2.3.tar.gz
curl -sSLO https://github.com/HDFGroup/hdf5/releases/download/hdf5_1.14.6/hdf5-1.14.6.tar.gz
git clone -q --depth 1 -b v4.9.2 https://github.com/Unidata/netcdf-c.git 2>/dev/null
git clone -q --depth 1 -b v4.3.1 https://github.com/Unidata/netcdf-cxx4.git 2>/dev/null
git clone -q --depth 1 -b v5.1.1 --recurse-submodules --shallow-submodules https://github.com/boutproject/BOUT-dev.git 2>/dev/null
step MPICH
tar xzf mpich-4.2.3.tar.gz && cd mpich-4.2.3
./configure --prefix=$P --disable-fortran --with-device=ch3:nemesis --disable-doc > $L/mpich.log 2>&1
make -j$J >> $L/mpich.log 2>&1 && make install >> $L/mpich.log 2>&1
step HDF5
cd $S && tar xzf hdf5-1.14.6.tar.gz && cd hdf5-1.14.6
./configure --prefix=$P --disable-fortran --disable-tests --enable-hl --with-zlib=/usr > $L/hdf5.log 2>&1
make -j$J >> $L/hdf5.log 2>&1 && make install >> $L/hdf5.log 2>&1
step netCDF-C
cmake -S $S/netcdf-c -B $S/netcdf-c/build -DCMAKE_INSTALL_PREFIX=$P -DCMAKE_PREFIX_PATH=$P -DENABLE_DAP=OFF -DENABLE_BYTERANGE=OFF \
  -DENABLE_TESTS=OFF -DBUILD_UTILITIES=ON -DENABLE_NCZARR=OFF -DENABLE_PLUGINS=OFF -DENABLE_FILTER_TESTING=OFF > $L/netcdf.log 2>&1
cmake --build $S/netcdf-c/build -j$J >> $L/netcdf.log 2>&1 && cmake --install $S/netcdf-c/build >> $L/netcdf.log 2>&1
step netCDF-CXX4
cmake -S $S/netcdf-cxx4 -B $S/netcdf-cxx4/build -DCMAKE_INSTALL_PREFIX=$P -DCMAKE_PREFIX_PATH=$P -DNCXX_ENABLE_TESTS=OFF -DENABLE_FILTER_TESTING=OFF > $L/ncxx.log 2>&1
cmake --build $S/netcdf-cxx4/build -j$J >> $L/ncxx.log 2>&1 && cmake --install $S/netcdf-cxx4/build >> $L/ncxx.log 2>&1
step BOUT++
cmake -S $S/BOUT-dev -B $S/BOUT-dev/build -DCMAKE_INSTALL_PREFIX=$P -DCMAKE_PREFIX_PATH=$P -DCMAKE_BUILD_TYPE=Release -DCHECK=0 \
  -DCMAKE_C_COMPILER=$P/bin/mpicc -DCMAKE_CXX_COMPILER=$P/bin/mpicxx \
  -DBOUT_USE_FFTW=ON -DBOUT_USE_NETCDF=ON -DBOUT_DOWNLOAD_NETCDF_CXX4=OFF -DBOUT_USE_PETSC=OFF -DBOUT_USE_SUNDIALS=OFF \
  -DBOUT_ENABLE_PYTHON=OFF -DBOUT_TESTS=OFF -DBOUT_BUILD_EXAMPLES=OFF -DBOUT_UPDATE_GIT_SUBMODULE=OFF > $L/bout.log 2>&1
cmake --build $S/BOUT-dev/build -j$J >> $L/bout.log 2>&1 && cmake --install $S/BOUT-dev/build >> $L/bout.log 2>&1
step elm-pb
mkdir -p $P/elmpb && cp $S/BOUT-dev/examples/elm-pb/elm_pb.cxx $P/elmpb/
cat > $P/elmpb/CMakeLists.txt <<'EOC'
cmake_minimum_required(VERSION 3.13)
project(elm_pb LANGUAGES CXX)
find_package(bout++ REQUIRED)
add_executable(elm_pb elm_pb.cxx)
target_link_libraries(elm_pb PRIVATE bout++::bout++)
EOC
cmake -S $P/elmpb -B $P/elmpb/build -DCMAKE_PREFIX_PATH=$P -DCMAKE_CXX_COMPILER=$P/bin/mpicxx -DCMAKE_BUILD_TYPE=Release > $L/elmpb.log 2>&1
cmake --build $P/elmpb/build -j$J >> $L/elmpb.log 2>&1
test -x $P/elmpb/build/elm_pb
step BUILD_OK
