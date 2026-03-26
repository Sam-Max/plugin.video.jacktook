import re
from urllib.parse import quote
from lib.clients.base import BaseClient, TorrentStream
from lib.utils.kodi.utils import kodilog
from lib.utils.general.utils import IndexerType, Indexer
from typing import List, Optional, Any, Callable, Tuple

VIDEO_EXTENSIONS = (
    "m4v,3g2,3gp,nsv,tp,ts,ty,pls,rm,rmvb,mpd,ifo,mov,qt,divx,xvid,bivx,vob,nrg,img,iso,udf,pva,wmv,asf,asx,ogm,m2v,avi,bin,dat,mpg,mpeg,mp4,mkv,"
    "mk3d,avc,vp3,svq3,nuv,viv,dv,fli,flv,wpl,xspf,vdr,dvr-ms,xsp,mts,m2t,m2ts,evo,ogv,sdp,avs,rec,url,pxml,vc1,h264,rcv,rss,mpls,mpl,webm,bdmv,bdm,wtv,trp,f4v,pvr,disc"
)

SEARCH_PARAMS = {
    "st": "adv",
    "sb": 1,
    "fex": VIDEO_EXTENSIONS,
    "fty[]": "VIDEO",
    "spamf": 1,
    "u": "1",
    "gx": 1,
    "pno": 1,
    "sS": 3,
    "s1": "relevance",
    "s1d": "-",
    "s2": "dsize",
    "s2d": "-",
    "s3": "dtime",
    "s3d": "-",
    "pby": 150,
}


class Easynews(BaseClient):
    def __init__(
        self, user: str, password: str, timeout: int, notification: Callable
    ) -> None:
        super().__init__("https://members.easynews.com", notification)
        self.user = user
        self.password = password
        self.timeout = timeout
        self.base_url = f"{self.host}/2.0/search/solr-search/advanced"

    def search(
        self,
        query: str,
        mode: str,
        media_type: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
    ) -> List[TorrentStream]:
        search_query = query
        if mode == "tv" and season:
            if episode:
                search_query = f"{query} S{season:02d}E{episode:02d}"
            else:
                # Season search or pack search
                search_query = f"{query} S{season:02d}"

        params = SEARCH_PARAMS.copy()
        params["gps"] = search_query

        try:
            response = self.session.get(
                self.base_url,
                params=params,
                auth=(self.user, self.password),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return self.parse_response(response)
        except Exception as e:
            kodilog(f"EasyNews search error: {e}")
            return []

    def parse_response(self, res: Any) -> List[TorrentStream]:
        results = []
        try:
            response_json = res.json()
        except Exception:
            return results

        if not response_json or "data" not in response_json:
            return results

        down_url = response_json.get("downURL")
        dl_farm = response_json.get("dlFarm")
        dl_port = response_json.get("dlPort")

        for item in response_json.get("data", []):
            try:
                post_hash = item.get("0")
                size_val = item.get("4")
                try:
                    size = int(size_val)
                except (ValueError, TypeError):
                    from lib.utils.kodi.utils import convert_size_to_bytes

                    size = convert_size_to_bytes(str(size_val))
                post_title = item.get("10")
                ext = item.get("11")
                duration = item.get("14", "")

                if item.get("type", "").upper() != "VIDEO":
                    continue
                if item.get("virus"):
                    continue
                if re.match(r"^\d+s", duration) or re.match(r"^[0-5]m", duration):
                    continue

                url = down_url + quote(
                    f"/{dl_farm}/{dl_port}/{post_hash}{ext}/{post_title}{ext}"
                )
                title = post_title

                results.append(
                    TorrentStream(
                        title=title,
                        type=IndexerType.DIRECT,
                        indexer=Indexer.EASYNEWS,
                        provider=Indexer.EASYNEWS,
                        size=size,
                        url=url,
                        quality=self._guess_quality(title),
                        isCached=True,
                    )
                )
            except Exception as e:
                kodilog(f"Easynews parse item error: {e}")

        return results

    def resolve_url(self, url: str) -> Optional[str]:
        try:
            response = self.session.get(
                url,
                auth=(self.user, self.password),
                stream=True,
                timeout=self.timeout * 3,
            )
            if not response.ok:
                return None
            chunk = next(response.iter_content(chunk_size=1048576), b"")
            if len(chunk):
                resolved_link = response.url
            else:
                resolved_link = None
            return resolved_link
        except Exception as e:
            kodilog(f"Easynews resolve URL error: {e}")
            return None

    def account(self) -> Tuple[Optional[List], Optional[List]]:
        account_info, usage_info = None, None
        try:
            account_html = self.session.get(
                "https://account.easynews.com/editinfo.php",
                auth=(self.user, self.password),
                timeout=self.timeout,
            ).text
            # Basic regex to extract account info fields
            account_info = re.findall(r"<td[^>]*>([^<]+)</td>", account_html)
            if account_info and len(account_info) >= 11:
                account_info = account_info[0:11][1::3]
        except Exception as e:
            kodilog(f"Easynews account info error: {e}")

        try:
            usage_html = self.session.get(
                "https://account.easynews.com/usageview.php",
                auth=(self.user, self.password),
                timeout=self.timeout,
            ).text
            usage_info = re.findall(r"<td[^>]*>(.*?)</td>", usage_html, re.DOTALL)
            if usage_info and len(usage_info) >= 11:
                usage_info = usage_info[0:11][1::3]
                if len(usage_info) > 1:
                    usage_info[1] = re.sub(r"[</].+?>", "", usage_info[1]).strip()
        except Exception as e:
            kodilog(f"Easynews usage info error: {e}")

        return account_info, usage_info

    def get_info(self) -> None:
        from datetime import datetime
        from lib.utils.kodi.utils import dialog_text, kodilog

        try:
            acc_info, usage_info = self.account()

            if not acc_info or not usage_info:
                if self.notification:
                    self.notification("Easynews Account Error")
                return

            try:
                expires = datetime.strptime(acc_info[2], "%Y-%m-%d")
                days_remaining = (expires - datetime.now()).days
                expires_str = expires.strftime("%Y-%m-%d")
            except ValueError:
                expires_str = acc_info[2]
                days_remaining = "Unknown"

            body = [
                f"Account Status: {acc_info[1]}",
                f"Account Type: {acc_info[0]}",
                f"Features: {acc_info[3]}",
                f"Expires: {expires_str}",
                f"Days Remaining: {days_remaining}",
                f"Usage Limits: {usage_info[2]}",
                f"Gigs Allowed: {usage_info[0]}",
                f"Gigs Remaining: {usage_info[1]}",
            ]

            dialog_text(translation(90651), "\n\n".join(body))
        except Exception as e:
            import traceback

            kodilog(f"Error fetching Easynews info: {e}\n{traceback.format_exc()}")
            if self.notification:
                self.notification("Error fetching Easynews info")

    def _guess_quality(self, title: str) -> str:
        t = title.upper().replace(" ", ".").split(".")
        if any(x in t for x in ["2160P", "4K", "UHD", "2160"]):
            return "4K"
        if any(x in t for x in ["1080P", "1080I", "1080"]):
            return "1080p"
        if any(x in t for x in ["720P", "720I", "720"]):
            return "720p"
        if any(x in t for x in ["480P", "480I", "480", "SD", "DVD", "DVDRIP"]):
            return "SD"

        # Fallback to simple string search if dots/spaces don't catch it
        t = title.upper()
        if "2160" in t or "4K" in t:
            return "4K"
        if "1080" in t:
            return "1080p"
        if "720" in t:
            return "720p"
        if "480" in t or "SD" in t or "DVD" in t:
            return "SD"

        return "N/A"
