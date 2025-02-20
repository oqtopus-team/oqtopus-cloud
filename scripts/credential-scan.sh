#!/bin/bash

REPO_DIR=$(git rev-parse --show-toplevel)
CREDETIAL_SCAN_DIR=$REPO_DIR/credential-scan

mkdir -p $CREDETIAL_SCAN_DIR

docker run --platform linux/x86_64 \
-v $REPO_DIR:/repo \
-it python:3.12 /bin/bash -c "
  set -e;
  pip install --root-user-action=ignore poetry trufflehog3;
  trufflehog3 filesystem /repo;
"
SCAN_STATUS_CODE=$?
rm -r $CREDETIAL_SCAN_DIR
if [ $SCAN_STATUS_CODE -eq 0 ]; then
  echo "Scan completed successfully."
  exit 0
elif [ $SCAN_STATUS_CODE -eq 2 ]; then
  echo "Scan encountered a specific issue."
  exit 2
else
  echo "Something went wrong while scanning the repository."
  exit 1
fi
