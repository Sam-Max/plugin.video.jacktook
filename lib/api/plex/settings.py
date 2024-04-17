from uuid import uuid4


class Settings():
    identifier: str = str(uuid4())
    product_name: str = 'Jacktook'
    plex_requests_timeout: int = 30
    plex_matching_token: str


settings = Settings()
