import json
import logging

import xbmc

logger = logging.getLogger(__name__)


class JSONRPCError(Exception):
    def __init__(self, code, message):  # type: (int, str) -> None
        self.code = code
        self.message = message

        super(JSONRPCError, self).__init__(message)


_JSONRPC_TEMPLATE = """{{"jsonrpc":"2.0","id":0,"method":"{method}","params":{params}}}"""


def execute(method, *params):  # type: (str, *Any) -> Any
    logger.debug("calling jsonrpc method %r with params %r", method, params)
    raw_res = xbmc.executeJSONRPC(_JSONRPC_TEMPLATE.format(method=method, params=json.dumps(params)))
    res = json.loads(raw_res)
    logger.debug("got response %s", res)
    return result_from_response(res)


def result_from_response(res):  # type: (dict) -> Any
    try:
        return res["result"]
    except KeyError:
        pass

    try:
        error = res["error"]
    except KeyError:
        raise ValueError("response is neither result nor error")

    raise JSONRPCError(error["code"], error["message"])


PLAYER_MUSIC = 0
PLAYER_VIDEO = 1
PLAYER_PICTURE = 2

LIST_FIELD_ART = "art"
LIST_FIELD_UNIQUEID = "uniqueid"
