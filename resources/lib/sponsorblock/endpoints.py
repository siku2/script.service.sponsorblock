DEFAULT_SERVER = "api.sponsor.ajay.app"

_BASE_URL = "https://{SERVER}"
_API_URL = _BASE_URL + "/api"

GET_VIDEO_SPONSOR_TIMES = _API_URL + "/getVideoSponsorTimes"
POST_VIDEO_SPONSOR_TIMES = _API_URL + "/postVideoSponsorTimes"
VOTE_ON_SPONSOR_TIME = _API_URL = "/voteOnSponsorTime"
VIEWED_VIDEO_SPONSOR_TIME = _API_URL + "/viewedVideoSponsorTime"

# User
GET_VIEWS_FOR_USER = _API_URL + "/getViewsForUser"
GET_SAVED_TIME_FOR_USER = _API_URL + "/getSavedTimeForUser"
SET_USERNAME = _API_URL + "/setUsername"
GET_USERNAME = _API_URL + "/getUsername"

# Stats
GET_TOP_USERS = _API_URL + "/getTopUsers"
GET_TOTAL_STATS = _API_URL + "/getTotalStats"
GET_DAYS_SAVED_FORMATTED = _API_URL + "/getDaysSavedFormatted"

# Admin
# TODO