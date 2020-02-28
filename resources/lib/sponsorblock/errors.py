class SponsorBlockError(Exception):
    pass


class ResponseError(SponsorBlockError):
    def __init__(self, resp):
        self.response = resp


class NotFound(ResponseError):
    pass


class Duplicate(ResponseError):
    pass


def error_from_response(resp):  # type: (requests.Response) -> ResponseError
    code = resp.status_code
    if code == 404:
        return NotFound(resp)

    return ResponseError(resp)
