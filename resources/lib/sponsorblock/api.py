import logging

import requests
from six.moves import zip

from .endpoints import DEFAULT_SERVER, GET_VIDEO_SPONSOR_TIMES, VIEWED_VIDEO_SPONSOR_TIME, VOTE_ON_SPONSOR_TIME
from .errors import error_from_response
from .models import SponsorSegment
from .utils import new_user_id

logger = logging.getLogger(__name__)

_USER_AGENT = "kodi-sponsorblock/{version} (https://github.com/siku2/script.service.sponsorblock)"


def get_user_agent():  # type: () -> str
    from . import __version__
    return _USER_AGENT.format(version=__version__)


def get_segment_uuid(segment):  # type: (Union[str, SponsorSegment])
    if isinstance(segment, SponsorSegment):
        return segment.uuid

    return segment


class SponsorBlockAPI:
    def __init__(self, user_id=None, api_server=None):
        self._user_id = user_id or new_user_id()
        self._session = requests.Session()
        self._session.headers["User-Agent"] = get_user_agent()

        self._api_server = api_server or DEFAULT_SERVER
        self._request_timeout = 10

    def set_api_server(self, api_server):  # type: (Optional[str]) -> None
        if not api_server:
            api_server = DEFAULT_SERVER

        self._api_server = api_server

    def set_user_id(self, user_id):  # type: (Optional[str]) -> None
        if not user_id:
            logger.info("generating new user id")
            user_id = new_user_id()

        self._user_id = user_id

    def _request(self, method, url, params):
        req_cm = self._session.request(
            method, url.format(SERVER=self._api_server),
            params,
            timeout=self._request_timeout
        )
        with req_cm as resp:
            if resp.status_code != 200:
                raise error_from_response(resp)

            return resp.json()

    def get_video_sponsor_times(self, video_id):  # type: (str) -> List[SponsorSegment]
        data = self._request("GET", GET_VIDEO_SPONSOR_TIMES, {"videoID": video_id})

        uuids = data["UUIDs"]
        sponsor_times = data["sponsorTimes"]

        return [SponsorSegment(uuid, start, end)
                for uuid, (start, end) in zip(uuids, sponsor_times)]

    def vote_sponsor_segment(self, segment, upvote=False):  # type: (Union[str, SponsorSegment], bool) -> None
        self._request("POST", VOTE_ON_SPONSOR_TIME, {
            "UUID": get_segment_uuid(segment),
            "userID": self._user_id,
            "type": int(upvote)
        })

    def viewed_sponsor_segment(self, segment):  # type: (Union[str, SponsorSegment]) -> None
        self._request("POST", VIEWED_VIDEO_SPONSOR_TIME, {
            "UUID": get_segment_uuid(segment),
        })
