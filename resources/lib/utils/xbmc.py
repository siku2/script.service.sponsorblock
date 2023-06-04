import xbmc

from six.moves.urllib import parse as urlparse

from .const import VAR_PLAYER_FILE_AND_PATH


def get_playing_file_path():  # type: () -> str
    return xbmc.getInfoLabel(VAR_PLAYER_FILE_AND_PATH)


def get_playing_addon():
    """
    Return which addon is currently playing media.
    """
    path = get_playing_file_path()
    return urlparse.urlsplit(path).netloc
