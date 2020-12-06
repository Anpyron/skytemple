#!/bin/sh

# Call with build-windows.sh [version number]
# The version from the current pip install of SkyTemple is used if no version number is set.
set -e

export XDG_DATA_DIRS="${BUILD_ROOT}/${MINGW}/share"

rm build -rf || true
rm dist -rf || true

pip install python_igraph-*-mingw.whl
pip install py_desmume-*-mingw.whl
pip install skytemple_rust-*-mingw.whl
pip install tilequant-*-mingw.whl
pip3 install -r ../requirements-mac-windows.txt
pip3 install ..

pyinstaller skytemple.spec

# Remove unnecessary things
rm dist/skytemple/share/doc/* -rf
rm dist/skytemple/share/gtk-doc/* -rf
rm dist/skytemple/share/man/* -rf

# Write the version number to files that are read at runtime
version=$1 || $(python3 -c "import pkg_resources; print(pkg_resources.get_distribution(\"skytemple\").version)")

echo $version > dist/skytemple/VERSION
echo $version > dist/skytemple/skytemple/data/VERSION
