#!/bin/sh
# Installs the latest skytemple-rust version for the current platform.
# If dev build: Latest is master. Otherwise latest is taken from "release" branch
# which MUST point to the latest release.
set -xe

branch="master"
wheel_name="skytemple_rust-*-cp311-cp311-win_amd64.whl"
url="https://nightly.link/SkyTemple/skytemple-rust/workflows/build-test-publish/$branch/wheels-windows-2019-AMD64.zip"

if [ -n "$IS_MACOS" ]; then
  # Check if we're running on Apple Silicon
  if [ "$(uname -m)" = "arm64" ]; then
    wheel_name="skytemple_rust-*-cp312-cp312-macosx_*_arm64.whl"
    url="https://nightly.link/SkyTemple/skytemple-rust/workflows/build-test-publish/$branch/wheels-macos-13-arm64.zip"
  else
    wheel_name="skytemple_rust-*-cp312-cp312-macosx_*_x86_64.whl"
    url="https://nightly.link/SkyTemple/skytemple-rust/workflows/build-test-publish/$branch/wheels-macos-13-x86_64.zip"
  fi
fi

rm -rf tmp_rust || true

mkdir tmp_rust
cd tmp_rust
curl -LO $url
unzip wheels*.zip
eval pip3 install $wheel_name

rm -rf tmp_rust || true
