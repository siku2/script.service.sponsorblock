import logging

from .abstract_api import AbstractApi
from .invidious_api import InvidiousApi
from .piped_api import PipedApi
from .youtube_api import YouTubeApi


logger = logging.getLogger(__name__)


API_MAP = {
    "plugin.video.youtube": YouTubeApi,
    "plugin.video.invidious": InvidiousApi,
    "plugin.video.piped": PipedApi
}


singletons = {}
"""
Map that persists singletons of each service at runtime.
"""


def get_api(addon_id): # type: (str) -> AbstractApi | None
    """
    Factory that returns the respective API implementation for a given
    addon ID.
    """
    if addon_id not in API_MAP:
        return None

    if addon_id not in singletons:
        constructor = API_MAP[addon_id]
        singletons[addon_id] = constructor()

    return singletons[addon_id]
