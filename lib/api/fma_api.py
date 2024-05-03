import re
import requests


class FindMyAnime:
    base_url = "https://find-my-anime.dtimur.de/api"

    def get_anime_data(self, anime_id, anime_id_provider):
        params = {"id": anime_id, "provider": anime_id_provider, "includeAdult": "true"}
        return self.make_request(params=params)

    def make_request(self, params):
        res = requests.get(
            self.base_url,
            params=params,
        )
        if res.status_code == 200:
            return res.json()
        else:
            raise Exception(f"FMA error::{res.text}")


def extract_season(res):
    regexes = [
        r"season\s(\d+)",
        r"\s(\d+)st\sseason(?:\s|$)",
        r"\s(\d+)nd\sseason(?:\s|$)",
        r"\s(\d+)rd\sseason(?:\s|$)",
        r"\s(\d+)th\sseason(?:\s|$)",
    ]
    s_ids = []
    for regex in regexes:
        if isinstance(res.get("title"), dict):
            s_ids += [
                re.findall(regex, name, re.IGNORECASE)
                for lang, name in res.get("title").items()
                if name is not None
            ]
        else:
            s_ids += [
                re.findall(regex, name, re.IGNORECASE) for name in res.get("title")
            ]

        s_ids += [
            re.findall(regex, name, re.IGNORECASE) for name in res.get("synonyms")
        ]

    s_ids = [s[0] for s in s_ids if s]

    if not s_ids:
        regex = r"\s(\d+)$"
        cour = False
        if isinstance(res.get("title"), dict):
            for lang, name in res.get("title").items():
                if name is not None and (
                    " part " in name.lower() or " cour " in name.lower()
                ):
                    cour = True
                    break
            if not cour:
                s_ids += [
                    re.findall(regex, name, re.IGNORECASE)
                    for lang, name in res.get("title").items()
                    if name is not None
                ]
                s_ids += [
                    re.findall(regex, name, re.IGNORECASE)
                    for name in res.get("synonyms")
                ]
        else:
            for name in res.get("title"):
                if " part " in name.lower() or " cour " in name.lower():
                    cour = True
                    break
            if not cour:
                s_ids += [
                    re.findall(regex, name, re.IGNORECASE) for name in res.get("title")
                ]
                s_ids += [
                    re.findall(regex, name, re.IGNORECASE)
                    for name in res.get("synonyms")
                ]
        s_ids = [s[0] for s in s_ids if s and int(s[0]) < 20]

    return s_ids
