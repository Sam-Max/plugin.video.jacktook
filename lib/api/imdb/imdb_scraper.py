import re
import json
import requests
import html
from datetime import timedelta
from lib.utils.kodi.utils import kodilog
from lib.db.cached import cache


GQL_URL = "https://graphql.imdb.com/"
GQL_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://www.imdb.com",
    "Referer": "https://www.imdb.com/",
    "x-imdb-client-name": "imdb-web-next-localized",
    "x-imdb-user-language": "en-US",
    "x-imdb-user-country": "US",
}


def _clean(text):
    if not text:
        return ""
    text = text.replace("<br/><br/>", "\n").replace("<br/>", "\n").replace("<br>", "\n")
    text = re.sub(r"<a[^>]*>", "", text).replace("</a>", "")
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()


def get_imdb_extras(imdb_id):
    """
    Fetch IMDb extras (reviews, trivia, goofs, parental guide) via GraphQL.
    Returns a dict with keys: reviews, trivia, blunders, parentsguide.
    """
    if not imdb_id:
        return {"reviews": [], "trivia": [], "blunders": [], "parentsguide": []}

    cache_key = f"imdb_extras_gql_{imdb_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        payload = {"query": IMDB_EXTRAS_QUERY % imdb_id}
        response = requests.post(GQL_URL, json=payload, headers=GQL_HEADERS, timeout=10)
        data = response.json().get("data", {}).get("title", {})

        reviews, trivia, blunders, parentsguide = [], [], [], []

        # Reviews
        try:
            count = 1
            for edge in sorted(
                data["reviews"]["edges"],
                key=lambda k: k["node"]["submissionDate"],
                reverse=True,
            ):
                try:
                    content = html.unescape(
                        _clean(edge["node"]["text"]["originalText"]["plaidHtml"])
                    )
                    if not content:
                        continue
                    spoiler = edge["node"].get("spoiler", False)
                    rating = edge["node"].get("authorRating")
                    rating_str = str(rating) if rating is not None else "-"
                    title = (
                        edge["node"].get("summary", {}).get("originalText", "-----")
                    )
                    date = edge["node"].get("submissionDate", "-----")
                    review_text = f"[B]%02d. [I]%s/10 - %s - %s[/I][/B][CR][CR]%s" % (
                        count,
                        rating_str,
                        date,
                        title,
                        content,
                    )
                    if spoiler:
                        review_text = (
                            "[B][COLOR red][CONTAINS SPOILERS][/COLOR][CR][/B]"
                            + review_text
                        )
                    count += 1
                    reviews.append(review_text)
                except Exception:
                    pass
        except Exception:
            pass

        # Trivia
        try:
            count = 1
            for edge in sorted(
                data["trivia"]["edges"],
                key=lambda k: k["node"]["interestScore"]["usersVoted"],
                reverse=True,
            ):
                try:
                    content = html.unescape(
                        _clean(
                            edge["node"]["displayableArticle"]["body"]["plaidHtml"]
                        )
                    )
                    trivia.append(f"[B]TRIVIA %02d.[/B][CR][CR]%s" % (count, content))
                    count += 1
                except Exception:
                    pass
        except Exception:
            pass

        # Goofs / Blunders
        try:
            count = 1
            for edge in sorted(
                data["goofs"]["edges"],
                key=lambda k: k["node"]["interestScore"]["usersVoted"],
                reverse=True,
            ):
                try:
                    content = html.unescape(
                        _clean(
                            edge["node"]["displayableArticle"]["body"]["plaidHtml"]
                        )
                    )
                    blunders.append(
                        f"[B]BLUNDERS %02d.[/B][CR][CR]%s" % (count, content)
                    )
                    count += 1
                except Exception:
                    pass
        except Exception:
            pass

        # Parents Guide
        try:
            title_converter = {
                "nudity": "Sex & Nudity",
                "violence": "Violence & Gore",
                "profanity": "Profanity",
                "alcohol": "Alcohol, Drugs & Smoking",
                "frightening": "Frightening & Intense Scenes",
            }
            for category in data["parentsGuide"]["categories"]:
                try:
                    cat_id = category["category"]["id"].lower()
                    title = title_converter.get(cat_id, cat_id.capitalize())
                    ranking = category["severity"]["id"].replace("Votes", "")
                    try:
                        listings = [
                            html.unescape(_clean(x["node"]["text"]["plaidHtml"]))
                            for x in category["guideItems"]["edges"]
                        ]
                        content = "\n\n".join(
                            ["%02d. %s" % (c, i) for c, i in enumerate(listings, 1)]
                        )
                    except Exception:
                        listings = []
                        content = ""
                    total_count = len(listings)
                    parentsguide.append(
                        {
                            "title": title,
                            "ranking": ranking,
                            "content": content,
                            "total_count": total_count,
                        }
                    )
                except Exception:
                    pass
        except Exception:
            pass

        result = {
            "reviews": reviews,
            "trivia": trivia,
            "blunders": blunders,
            "parentsguide": parentsguide,
        }
        cache.set(cache_key, result, timedelta(hours=168))
        return result

    except Exception as e:
        kodilog(f"Error fetching IMDb GraphQL extras for {imdb_id}: {e}")
        return {"reviews": [], "trivia": [], "blunders": [], "parentsguide": []}


def get_imdb_more_like_this(imdb_id):
    """
    Fetch "More Like This" titles from IMDb via GraphQL.
    Returns a list of IMDb IDs (tt...).
    """
    if not imdb_id:
        return []

    cache_key = f"imdb_more_like_this_{imdb_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        payload = {
            "query": 'query($id:ID!){title(id:$id){moreLikeThisTitles(first:12){edges{node{id}}}}}',
            "variables": {"id": imdb_id},
        }
        response = requests.post(GQL_URL, json=payload, headers=GQL_HEADERS, timeout=10)
        edges = response.json()["data"]["title"]["moreLikeThisTitles"]["edges"]
        result = [edge["node"]["id"] for edge in edges if edge["node"]["id"].startswith("tt")]
        # Deduplicate
        seen = set()
        result = [x for x in result if not (x in seen or seen.add(x))]
        cache.set(cache_key, result, timedelta(hours=168))
        return result
    except Exception as e:
        kodilog(f"Error fetching IMDb More Like This for {imdb_id}: {e}")
        return []


# Keep legacy functions for backward compatibility until fully migrated
def get_imdb_trivia(imdb_id):
    """Legacy wrapper. Use get_imdb_extras() for new code."""
    return get_imdb_extras(imdb_id).get("trivia", [])


def get_imdb_goofs(imdb_id):
    """Legacy wrapper. Use get_imdb_extras() for new code."""
    return get_imdb_extras(imdb_id).get("blunders", [])


def get_imdb_parentsguide(imdb_id):
    """Legacy wrapper. Use get_imdb_extras() for new code."""
    extras = get_imdb_extras(imdb_id)
    guide = extras.get("parentsguide", [])
    # Convert to legacy text format for compatibility
    result = []
    for item in guide:
        header = f"[B]{item['title']}[/B]"
        if item.get("ranking"):
            header += f" — {item['ranking']}"
        if item.get("content"):
            result.append(f"{header}\n{item['content']}")
        else:
            result.append(header)
    return result


IMDB_EXTRAS_QUERY = """\
query {
  title(id: "%s") {
    id
    titleText {
      text
    }
    trivia(first: 20) {
      edges {
        node {
          displayableArticle {
            body {
              plaidHtml
            }
          }
          interestScore {
            usersVoted
          }
        }
      }
    }
    goofs(first: 20) {
      edges {
        node {
          displayableArticle {
            body {
              plaidHtml
            }
          }
          interestScore {
            usersVoted
          }
        }
      }
    }
    reviews(first: 50) {
      edges {
        node {
          spoiler
          author {
            nickName
          }
          authorRating
          summary {
            originalText
          }
          text {
            originalText {
              plaidHtml
            }
          }
          submissionDate
        }
      }
    }
    parentsGuide {
      categories {
        category {
          id
        }
        guideItems(first: 10) {
          edges {
            node {
              isSpoiler
              text {
                plaidHtml
              }
            }
          }
        }
        severity {
          id
          votedFor
        }
      }
    }
  }
}"""
