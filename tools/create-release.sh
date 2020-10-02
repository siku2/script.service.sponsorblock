#!/usr/bin/env bash
set -eE

function exit_with_error() {
  echo "ERROR: $1" 1>&2
  exit 1
}

if [[ ! -f addon.xml ]]; then
  exit_with_error "no addon.xml found, are you in the correct directory?"
fi

ADDON_VERSION=$(grep -Ei '<addon.* version="[0-9.]+"' addon.xml | grep -oEi "[0-9]\.[0-9]\.[0-9]")
if [[ -z $ADDON_VERSION ]]; then
  exit_with_error "couldn't determine addon version"
fi

ADDON_ID=$(basename "$(pwd)")

echo "creating release version $ADDON_VERSION for addon $ADDON_ID"

function create_tempdir() {
  local work_dir
  work_dir=$(mktemp --directory)
  if [[ ! "$work_dir" || ! -d "$work_dir" ]]; then
    exit_with_error "could not create temp dir"
    exit 1
  fi

  echo "$work_dir"
}

WORK_DIR=$(create_tempdir)

function cleanup() {
  rm -rf "$WORK_DIR"
}

trap cleanup EXIT

echo "moving addon to temp directory"

dir="$WORK_DIR/$ADDON_ID"
mkdir "$dir"
cp -rt "$dir" addon.xml ./*.py resources

echo "zipping addon"

ZIP_NAME="$ADDON_ID-$ADDON_VERSION.zip"
pushd "$WORK_DIR" >/dev/null
zip -qr "$ZIP_NAME" "$ADDON_ID"
popd >/dev/null

mv "$WORK_DIR/$ZIP_NAME" ./
