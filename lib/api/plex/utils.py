
class PlexUnauthorizedError(BaseException):
    pass


class HTTPException(BaseException):
    def __init__(
        self,
        status_code: int,
        detail: str,
    ):
        self.status_code = status_code
        self.detail = detail



