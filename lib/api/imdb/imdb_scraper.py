import requests
import re
import html
from lib.utils.kodi.utils import kodilog
from lib.db.cached import cache
from datetime import timedelta


def clean_html(text):
    if not text:
        return ""
    # Remove all HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Unescape HTML entities
    text = html.unescape(text)
    # Cleanup whitespace
    text = " ".join(text.split())
    return text.strip()


def get_imdb_trivia(imdb_id):
    """
    Scrapes the IMDb trivia page for a given IMDb ID.
    Returns a list of trivia strings.
    """
    if not imdb_id:
        return []

    cache_key = f"imdb_trivia_regex_v1_{imdb_id}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    url = f"https://www.imdb.com/title/{imdb_id}/trivia/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []

        # Find all trivia content divs using regex
        # Pattern: class="ipc-html-content-inner-div" ... > Content </div>
        matches = re.findall(
            r"class=\"ipc-html-content-inner-div\"[^>]*>(.*?)</div>",
            response.text,
            re.DOTALL,
        )

        trivia_list = []
        for m in matches:
            text = clean_html(m)
            if text:
                trivia_list.append(text)

        kodilog(f"Scraped {len(trivia_list)} IMDb trivia items (regex) for {imdb_id}")
        cache.set(cache_key, trivia_list, timedelta(hours=24))
        return trivia_list

    except Exception as e:
        kodilog(f"Error scraping IMDb trivia for {imdb_id}: {str(e)}")
        return []


def get_imdb_goofs(imdb_id):
    """
    Scrapes the IMDb goofs page for a given IMDb ID.
    Returns a list of goof strings.
    """
    if not imdb_id:
        return []

    cache_key = f"imdb_goofs_regex_v1_{imdb_id}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    url = f"https://www.imdb.com/title/{imdb_id}/goofs/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []

        matches = re.findall(
            r"class=\"ipc-html-content-inner-div\"[^>]*>(.*?)</div>",
            response.text,
            re.DOTALL,
        )

        goofs_list = []
        for m in matches:
            text = clean_html(m)
            if text:
                goofs_list.append(text)

        kodilog(f"Scraped {len(goofs_list)} IMDb goofs (regex) for {imdb_id}")
        cache.set(cache_key, goofs_list, timedelta(hours=24))
        return goofs_list

    except Exception as e:
        kodilog(f"Error scraping IMDb goofs for {imdb_id}: {str(e)}")
        return []


def get_imdb_parentsguide(imdb_id):
    """
    Scrapes the IMDb parents guide page for a given IMDb ID.
    Returns a list of parental guide strings grouped by category.
    """
    if not imdb_id:
        return []

    cache_key = f"imdb_parentsguide_regex_v1_{imdb_id}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    url = f"https://www.imdb.com/title/{imdb_id}/parentalguide/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []

        # Map internal IDs to user-friendly titles
        categories = {
            "nudity": "Sex & Nudity",
            "violence": "Violence & Gore",
            "profanity": "Profanity",
            "alcohol": "Alcohol, Drugs & Smoking",
            "frightening": "Frightening & Intense Scenes",
        }

        guide_list = []
        text = response.text

        # Split page by category IDs
        segments = re.split(
            r"id=\"(nudity|violence|profanity|alcohol|frightening)\"", text
        )

        # segments[0] is header
        # segments[1] is id, segments[2] is content, etc
        for i in range(1, len(segments), 2):
            cat_id = segments[i]
            content = segments[i + 1]
            cat_name = categories.get(cat_id, cat_id.capitalize())

            # Extract severity
            severity = ""
            sev_match = re.search(
                r"class=\"ipc-signpost__text\"[^>]*>(.*?)</div>", content, re.DOTALL
            )
            if sev_match:
                severity = clean_html(sev_match.group(1))

            header = f"[B]{cat_name}[/B]"
            if severity:
                header += f" — {severity}"

            # Extract individual items in this section
            items = re.findall(
                r"class=\"ipc-html-content-inner-div\"[^>]*>(.*?)</div>",
                content,
                re.DOTALL,
            )

            if items:
                for item in items:
                    item_text = clean_html(item)
                    if item_text:
                        guide_list.append(f"{header}\n{item_text}")
            else:
                guide_list.append(header)

        kodilog(
            f"Scraped {len(guide_list)} IMDb parental guide items (regex) for {imdb_id}"
        )
        cache.set(cache_key, guide_list, timedelta(hours=24))
        return guide_list

    except Exception as e:
        kodilog(f"Error scraping IMDb parental guide for {imdb_id}: {str(e)}")
        return []
