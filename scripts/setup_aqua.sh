#!/usr/bin/env bash

set -eu
set -o pipefail

if command -v aqua > /dev/null 2>&1; then
  exit 0
fi

tempdir=$(mktemp -d)
cd "$tempdir"
curl -sSfL -O https://raw.githubusercontent.com/aquaproj/aqua-installer/v3.0.1/aqua-installer
if command -v sha256sum > /dev/null 2>&1; then
  echo "fb4b3b7d026e5aba1fc478c268e8fbd653e01404c8a8c6284fdba88ae62eda6a  aqua-installer" | sha256sum -c
elif command -v shasum > /dev/null 2>&1; then
  echo "fb4b3b7d026e5aba1fc478c268e8fbd653e01404c8a8c6284fdba88ae62eda6a  aqua-installer" | shasum -a 256 -c
else
  echo "Error: Neither sha256sum nor shasum is available."
  exit 1
fi
chmod +x aqua-installer

./aqua-installer
cd -

rm -R "$tempdir"

aqua i -l
