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

echo "killing previous kodi"
while pkill -0 kodi; do
  sleep 1
done

if [[ -d $ADDON_PATH ]]; then
  echo "removing previous version"
  rm --recursive "${ADDON_PATH}"
fi

echo "adding addon"
mkdir "$ADDON_PATH"
cp --recursive {resources,addon.xml,service.py} "$ADDON_PATH"

echo "starting kodi"
kodi &>/dev/null &

echo "showing kodi log"
tail --follow=name --retry --lines 200 "$KODI_PATH/temp/kodi.log"
