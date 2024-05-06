from typing import Optional


class BaseOauth(object):

    __slots__ = [
        'code',
        'id',
        'username',
        'first_name',
        'data',
        'profile',
    ]

    def __init__(self, code: str) -> None:
        self.code = code
        self.id: Optional[int] = None
        self.username: Optional[str] = None
        self.first_name: Optional[str] = None
        self.data: Optional[dict] = None
        self.profile: Optional[dict] = None
