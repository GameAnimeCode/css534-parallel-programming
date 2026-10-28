#!/usr/bin/env bash
# Build and install MPICH2 1.2.1p1, the MPI the CSS 534 cssmpi cluster uses
# (its ~css534 binaries link against /usr/apps/mpich121-x86_64/lib), at the
# same prefix. Used by .devcontainer/Dockerfile and the cluster node image.
#
# Differences from the cluster install: the process manager is hydra (and
# gforker) instead of the Python 2 mpd ring, since Python 2 no longer exists
# on Fedora. The compiler wrappers, headers, and libraries are the same.
# `mpirun -np N prog` works as on cssmpi; CSSmpdboot/mpdallexit have no
# local equivalent and are not needed with hydra.
set -euo pipefail

version="1.2.1p1"
prefix="/usr/apps/mpich121-$(uname -m)"
url="https://www.mpich.org/static/downloads/${version}/mpich2-${version}.tar.gz"
sha256="a55d1682ee0b5ebbacc047f60620ed291e0a9b3ded3eaeb6a2c81a1598c4c964"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work"

curl -fsSL -o mpich2.tar.gz "$url"
echo "${sha256}  mpich2.tar.gz" | sha256sum -c -
tar xzf mpich2.tar.gz
mkdir build && cd build

# 2009-era C: GCC 14+ turns implicit declarations and loose pointer
# conversions into errors, so they are demoted to warnings here. The
# MPICH2LIB_* variables apply to the library build only; plain CFLAGS and
# CXXFLAGS would be baked into mpicc and mpicxx and applied to every user
# program, which cssmpi's wrappers do not do. The build is not parallel-safe
# (two ar runs race on libmpich.a), so no -j.
CC=gcc CXX=g++ \
MPICH2LIB_CFLAGS="-O2 -std=gnu89 -fcommon -Wno-implicit-function-declaration -Wno-implicit-int -Wno-int-conversion -Wno-incompatible-pointer-types -Wno-return-mismatch" \
MPICH2LIB_CXXFLAGS="-O2 -std=gnu++98 -fpermissive" \
"../mpich2-${version}/configure" \
  --prefix="$prefix" \
  --enable-sharedlibs=gcc \
  --enable-cxx \
  --with-pm=hydra:gforker \
  --disable-f77 --disable-fc \
  > configure.log 2>&1 || { tail -40 configure.log; exit 1; }
make > make.log 2>&1 || { tail -60 make.log; exit 1; }
make install > install.log 2>&1 || { tail -20 install.log; exit 1; }

# On cssmpi, mpirun is a symlink to mpiexec that the mpd process manager
# installs. hydra does not install one, so add it for `mpirun -np N`.
[[ -e "$prefix/bin/mpirun" ]] || ln -s mpiexec "$prefix/bin/mpirun"

# Login shells on cssmpi put the same bin directory first on PATH
# (mpi_setup.txt). Non-interactive shells, such as those SSH opens for
# hydra, get it from here too.
cat > /etc/profile.d/mpich121.sh <<EOF
export PATH="${prefix}/bin:\${PATH}"
export LD_LIBRARY_PATH="${prefix}/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
EOF

"$prefix/bin/mpich2version"
