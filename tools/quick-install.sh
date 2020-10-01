#!/usr/bin/env bash
set -eE

function exit_with_error() {
  echo "ERROR: $1" 1>&2
  exit 1
}

KODI_PATH="$HOME/.kodi"
if [[ ! -d $KODI_PATH ]]; then
  exit_with_error "kodi not found at $KODI_PATH"
fi

if [[ ! -f addon.xml ]]; then
  exit_with_error "no addon.xml found, are you in the correct directory?"
fi

ADDON_ID=$(basename "$(pwd)")
ADDON_PATH="$KODI_PATH/addons/$ADDON_ID"

KODI_PROCESS=kodi

function kodi_running() {
  pkill -0 "$KODI_PROCESS"
}

function kill_kodi() {
  if kodi_running; then
    echo "terminating previous kodi"
    pkill $KODI_PROCESS

    echo "waiting for kodi to stop"
    local waited=0
    while kodi_running; do
      if ((waited >= 5)); then
        echo "kodi hasn't stopped after $waited seconds, killing process"
        pkill -SIGKILL $KODI_PROCESS
        waited=0
      fi

      sleep 1

      waited=$((waited + 1))
    done
  fi
}

function reinstall_addon() {
  if [[ -d $ADDON_PATH ]]; then
    echo "removing previous version"
    rm --recursive "${ADDON_PATH}"
  fi

  echo "adding addon"
  mkdir "$ADDON_PATH"
  cp --recursive {resources,addon.xml,*.py} "$ADDON_PATH"
}

function start_kodi() {
  echo "starting kodi"
  kodi &>/dev/null &
}

function tail_log() {
  echo "showing kodi log"
  tail --follow=name --retry --lines 200 "$KODI_PATH/temp/kodi.log" | grep --color -E "$ADDON_ID|$"
}

function main() {
  kill_kodi
  reinstall_addon
  start_kodi
  tail_log
}

main
