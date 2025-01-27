import json


class Stream:
    def __init__(self, json_string):
        if isinstance(json_string, str):
            try:
                data = json.loads(json_string)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON string: {e}")
        elif isinstance(json_string, dict):
            data = json_string
        else:
            raise ValueError("Input must be a JSON string or a dictionary.")

        # Initialize required attributes
        self.url = data.get("url")
        self.ytId = data.get("ytId")
        self.infoHash = data.get("infoHash")
        self.fileIdx = data.get("fileIdx")
        self.externalUrl = data.get("externalUrl")

        # Initialize optional attributes
        self.name = data.get("name")
        self.title = data.get("title")  # deprecated
        self.description = data.get(
            "description", self.title
        )  # Use `title` as fallback
        self.subtitles = data.get("subtitles", [])
        self.sources = data.get("sources", [])

        # Initialize behavior hints
        behavior_hints = data.get("behaviorHints", {})
        self.countryWhitelist = behavior_hints.get("countryWhitelist", [])
        self.notWebReady = behavior_hints.get("notWebReady", False)
        self.bingeGroup = behavior_hints.get("bingeGroup")
        self.proxyHeaders = behavior_hints.get("proxyHeaders", {})
        self.videoHash = behavior_hints.get("videoHash")
        self.videoSize = behavior_hints.get("videoSize")
        self.filename = behavior_hints.get("filename")

        # Validation for at least one stream identifier
        if not (self.url or self.ytId or self.infoHash or self.externalUrl):
            raise ValueError(
                "At least one of 'url', 'ytId', 'infoHash', or 'externalUrl' must be specified."
            )

    def get_parsed_title(self) -> str:
        title = self.filename or self.description or self.title
        return title.splitlines()[0] if title else ""

    def get_parsed_size(self) -> int:
        return self.videoSize or 0

    def __repr__(self):
        return f"Stream(name={self.name}, url={self.url}, ytId={self.ytId}, infoHash={self.infoHash}, externalUrl={self.externalUrl})"
