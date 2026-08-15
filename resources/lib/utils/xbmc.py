import xbmc

from urllib import parse as urlparse

from .const import VAR_PLAYER_FILE_AND_PATH


def get_playing_file_path():  # type: () -> str
    return xbmc.getInfoLabel(VAR_PLAYER_FILE_AND_PATH)


def get_playing_addon():
    """
    Return which addon is currently playing media.
    """
    path = get_playing_file_path()
    try:
        parsed = urlparse.urlsplit(path)
    except (TypeError, ValueError):
        return ""

    hostname = (parsed.hostname or "").lower()
    if hostname == "googlevideo.com" or hostname.endswith(".googlevideo.com"):
        # The YouTube add-on resolves plugin:// URLs to googlevideo streams.
        # Newer Kodi versions can expose that resolved URL in
        # Player.FilenameAndPath when onPlayBackStarted is delivered.
        return "plugin.video.youtube"

    return parsed.netloc
