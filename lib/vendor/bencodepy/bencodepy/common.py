"""bencode.py - common."""


class Bencached:
    __slots__ = ["bencoded"]

    def __init__(self, s):
        self.bencoded = s
