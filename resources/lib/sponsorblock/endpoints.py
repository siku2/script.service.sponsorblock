DEFAULT_SERVER = "sponsor.ajay.app"

_BASE_URL = "https://{SERVER}"
_API_URL = _BASE_URL + "/api"

GET_SKIP_SEGMENTS = _API_URL + "/skipSegments"
VOTE_ON_SPONSOR_TIME = _API_URL + "/voteOnSponsorTime"
VIEWED_VIDEO_SPONSOR_TIME = _API_URL + "/viewedVideoSponsorTime"

# User
GET_VIEWS_FOR_USER = _API_URL + "/getViewsForUser"
GET_SAVED_TIME_FOR_USER = _API_URL + "/getSavedTimeForUser"
SET_USERNAME = _API_URL + "/setUsername"
GET_USERNAME = _API_URL + "/getUsername"
