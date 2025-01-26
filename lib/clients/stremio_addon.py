from lib.utils.utils import USER_AGENT_HEADER
from lib.stremio.addons_manager import Addon
from lib.stremio.stream import Stream

from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import convert_size_to_bytes
import requests
import re
from lib.utils.countries import find_language_by_unicode, _countries

langsSet = {'bosnian', 'ro', 'swedish', 'mac', 'tr', 'rw', 'ind', 'czech', 'nl', 'he', 'lithuanian', 'sāmo', 'nor', 'རྫོང', 'ger', 'azə', 'shq', 'cze', 'hu', 'danish', 'hy', 'mag', 'ms', 'tajik', 'پښت', 'kaz', 'mk', 'vietnamese', 'sk', 'бъл', 'ps', 'lt', 'cs', 'mongolian', 'jap', 'geo', 'ko', 'dan', 'dzongkha', 'th', 'norwegian', 'az', 'mt', 'por', 'kala', 'sin', 'ja', 'pol', 'is', 'nepali', 'việt', 'тоҷ', 'amh', 'irish', 'chinese', 'pl', 'қаз', 'maltese', 'tg', 'arabic', 'ລາວ', 'khm', 'ukr', 'hin', 'am', 'ne', 'føroy', 'et', 'macedonian', 'polish', 'ita', 'tur', 'ქართული', 'gre', 'spa', 'বেঙ্গ', 'عرب', 'kyr', 'rus', 'bs', 'si', 'sr', 'belarusian', 'kl', 'my', 'bel', "o'zb", 'бел', 'नेप', 'sam', 'albanian', 'faroese', 'turkish', 'spanish', 'da', 'georgian', 'malay', 'km', 'divehi', 'greek', 'فارسی', 'iri', 'bengali', 'melay', 'ben', 'mn', 'id', 'монгол', 'kin', 'portuguese', 'dutch', 'ar', 'de', 'icelandic', 'bg', 'slov', 'hi', 'norsk', 'est', 'viet', 'dz', 'rom', 'kyrgyz', 'fran', 'chi', 'ka', 'malaysian', 'fa', 'vi', 'catalan', 'ser', 'ru', 'indo', 'fo', 'pt', 'mal', 'burmese', 'kor', 'ga', 'korean', 'fin', 'lit', 'amharic', 'nep', 'dzo', 'italian', 'heb', 'be', 'bulgarian', 'eest', 'укр', 'አማ', 'ísl', 'el', 'lv', 'turkmen', '日', 'bur', 'हिं', 'עבר', 'tha', 'taj', 'мак', 'sq', 'uk', 'bos', 'sven', 'slo', 'japanese', 'hun', 'french', 'esp', 'serbian', 'croatian', 'türkmen', 'alb', 'kal', 'uz', 'mla', 'eng', 'german', 'ខ្មែរ', 'hebrew', 'ice', 'cro', 'mon', 'ελλ', 'sinhalese', 'рус', 'lo', 'fr', 'ca', 'sv', 'uzbek', 'aze', 'հայ', 'ara', 'hindi', 'မြန်', 'kalaallisut', 'es', 'it', 'kazakh', 'kk', 'slovak', 'per', 'sl', 'suom', 'češ', 'hungarian', 'finnish', 'thai', 'zh', 'hr', 'ky', 'arm', 'slovene', 'persian', 'cat', 'bn', 'ukrainian', 'ދިވެ', 'sve', 'div', 'fre', 'кыргыз', 'uzb', 'estonian', 'kinyarwanda', 'hrv', 'no', 'pashto', 'azerbaijani', 'gae', 'latvian', 'du', 'en', 'ned', 'срп', 'samoan', '中', 'tk', 'lao', 'indonesian', 'sm', '한', 'khmer', 'bul', 'pas', 'far', 'armenian', 'ไทย', 'fi', 'english', 'liet', 'romanian', 'russian', 'tür', 'සිං'}
language_codes = {
    'bosnian': 'bs', 'ro': 'ro', 'swedish': 'sv', 'mac': 'mk', 'tr': 'tr', 'rw': 'rw', 'ind': 'id', 'czech': 'cs', 
    'nl': 'nl', 'he': 'he', 'lithuanian': 'lt', 'sāmo': 'sm', 'nor': 'no', 'རྫོང': 'dz', 'ger': 'de', 'azə': 'az', 
    'shq': 'sq', 'lat': 'lv', 'cze': 'cs', 'hu': 'hu', 'danish': 'da', 'hy': 'hy', 'mag': 'mk', 'ms': 'ms', 'tajik': 'tg', 
    'پښت': 'ps', 'kaz': 'kk', 'mk': 'mk', 'vietnamese': 'vi', 'sk': 'sk', 'бъл': 'bg', 'ps': 'ps', 'lt': 'lt', 'cs': 'cs', 
    'mongolian': 'mn', 'jap': 'ja', 'geo': 'ka', 'ko': 'ko', 'dan': 'da', 'dzongkha': 'dz', 'th': 'th', 'norwegian': 'no', 
    'az': 'az', 'mt': 'mt', 'por': 'pt', 'kala': 'kl', 'sin': 'si', 'ja': 'ja', 'pol': 'pl', 'is': 'is', 'nepali': 'ne', 
    'việt': 'vi', 'тоҷ': 'tj', 'amh': 'am', 'irish': 'ga', 'chinese': 'zh', 'pl': 'pl', 'қаз': 'kk', 'maltese': 'mt', 
    'tg': 'tg', 'arabic': 'ar', 'ລາວ': 'lo', 'khm': 'km', 'ukr': 'uk', 'hin': 'hi', 'am': 'am', 'ne': 'ne', 'føroy': 'fo', 
    'et': 'et', 'macedonian': 'mk', 'polish': 'pl', 'ita': 'it', 'tur': 'tr', 'ქართული': 'ka', 'gre': 'el', 'spa': 'es', 
    'বেঙ্গ': 'bn', 'عرب': 'ar', 'kyr': 'ky', 'rus': 'ru', 'bs': 'bs', 'si': 'si', 'sr': 'sr', 'belarusian': 'be', 'kl': 'kl', 
    'my': 'my', 'bel': 'be', "o'zb": 'uz', 'бел': 'be', 'नेप': 'ne', 'sam': 'sm', 'albanian': 'sq', 'faroese': 'fo', 
    'turkish': 'tr', 'spanish': 'es', 'da': 'da', 'georgian': 'ka', 'malay': 'ms', 'km': 'km', 'divehi': 'dv', 'greek': 'el', 
    'فارسی': 'fa', 'iri': 'fa', 'bengali': 'bn', 'melay': 'ms', 'ben': 'bn', 'mn': 'mn', 'id': 'id', 'монгол': 'mn', 'kin': 'rw', 
    'portuguese': 'pt', 'dutch': 'nl', 'ar': 'ar', 'de': 'de', 'icelandic': 'is', 'bg': 'bg', 'slov': 'sk', 'hi': 'hi', 'norsk': 'no', 
    'est': 'et', 'viet': 'vi', 'dz': 'dz', 'rom': 'ro', 'kyrgyz': 'ky', 'fran': 'fr', 'chi': 'zh', 'ka': 'ka', 'malaysian': 'ms', 
    'fa': 'fa', 'vi': 'vi', 'catalan': 'ca', 'ser': 'sr', 'ru': 'ru', 'indo': 'id', 'fo': 'fo', 'pt': 'pt', 'mal': 'ms', 'burmese': 'my', 
    'kor': 'ko', 'ga': 'ga', 'korean': 'ko', 'fin': 'fi', 'lit': 'lt', 'amharic': 'am', 'nep': 'ne', 'dzo': 'dz', 'italian': 'it', 
    'heb': 'he', 'be': 'be', 'bulgarian': 'bg', 'eest': 'et', 'укр': 'uk', 'አማ': 'am', 'ísl': 'is', 'el': 'el', 'lv': 'lv', 
    'turkmen': 'tk', '日': 'ja', 'bur': 'my', 'हिं': 'hi', 'עבר': 'he', 'tha': 'th', 'taj': 'tg', 'мак': 'mk', 'sq': 'sq', 'uk': 'uk', 
    'bos': 'bs', 'sven': 'sv', 'slo': 'sk', 'japanese': 'ja', 'hun': 'hu', 'french': 'fr', 'esp': 'es', 'serbian': 'sr', 
    'croatian': 'hr', 'türkmen': 'tk', 'alb': 'sq', 'kal': 'kl', 'uz': 'uz', 'mla': 'ms', 'eng': 'en', 'german': 'de', 
    'ខ្មែរ': 'km', 'hebrew': 'he', 'ice': 'is', 'cro': 'hr', 'mon': 'mn', 'ελλ': 'el', 'sinhalese': 'si', 'рус': 'ru', 
    'lo': 'lo', 'fr': 'fr', 'ca': 'ca', 'sv': 'sv', 'uzbek': 'uz', 'aze': 'az', 'հայ': 'hy', 'ara': 'ar', 'hindi': 'hi', 
    'မြန်': 'my', 'kalaallisut': 'kl', 'es': 'es', 'it': 'it', 'kazakh': 'kk', 'kk': 'kk', 'slovak': 'sk', 'per': 'fa', 
    'sl': 'sl', 'suom': 'fi', 'češ': 'cs', 'hungarian': 'hu', 'finnish': 'fi', 'thai': 'th', 'zh': 'zh', 'hr': 'hr', 
    'ky': 'ky', 'arm': 'hy', 'slovene': 'sl', 'persian': 'fa', 'cat': 'ca', 'bn': 'bn', 'ukrainian': 'uk', 'ދިވެ': 'dv', 
    'sve': 'sv', 'div': 'dv', 'fre': 'fr', 'кыргыз': 'ky', 'uzb': 'uz', 'estonian': 'et', 'kinyarwanda': 'rw', 'hrv': 'hr', 
    'no': 'no', 'pashto': 'ps', 'azerbaijani': 'az', 'gae': 'ga', 'latvian': 'lv', 'du': 'nl', 'en': 'en', 'ned': 'nl', 
    'срп': 'sr', 'samoan': 'sm', '中': 'zh', 'tk': 'tk', 'dv': 'dv', 'lao': 'lo', 'indonesian': 'id', 'sm': 'sm', '한': 'ko', 
    'khmer': 'km', 'bul': 'bg', 'pas': 'ps', 'far': 'fa', 'armenian': 'hy', 'ไทย': 'th', 'fi': 'fi', 'english': 'en', 
    'liet': 'lt', 'romanian': 'ro', 'russian': 'ru', 'tür': 'tr', 'සිං': 'si'
}


class StremioAddonClient:
    def __init__(self, addon: Addon):
        self.addon = addon

    def search(self, imdb_id, mode, media_type, season, episode):
        try:
            if mode == "tv" or media_type == "tv":
                if not self.addon.isSupported("stream", "series", "tt"):
                    return []
                url = f"{self.addon.url()}/stream/series/{imdb_id}:{season}:{episode}.json"
            elif mode == "movies" or media_type == "movies":
                if not self.addon.isSupported("stream", "movie", "tt"):
                    return []
                url = f"{self.addon.url()}/stream/movie/{imdb_id}.json"
            res = requests.get(url, headers=USER_AGENT_HEADER, timeout=10)
            if res.status_code != 200:
                return
            return self.parse_response(res)
        except Exception as e:
            kodilog(f"Error in {self.addon.manifest.name}: {str(e)}")

    def parse_response(self, res):
        res = res.json()
        results = []
        for item in res["streams"]:
            stream = Stream(item)
            parsed = self.parse_torrent_description(stream.description)
            
            results.append(
                {
                    "title": stream.get_parsed_title(),
                    "type": "Torrent",
                    "indexer": self.addon.manifest.name.split(" ")[0],
                    "guid": stream.infoHash,
                    "infoHash": stream.infoHash,
                    "size":stream.get_parsed_size() or parsed['size'],
                    "seeders": item.get("seed", 0) or parsed["seeders"],
                    "languages": parsed['languages'], #[item.get("language", "")],
                    "fullLanguages": parsed['languages'], # [item.get("language", "")],
                    "provider": parsed["provider"],
                    "publishDate": "",
                    "peers": 0,
                }
            )
        return results

    def find_languages_in_string(self, s: str) -> set:
        pattern = r'\b(?:' + '|'.join(re.escape(word) for word in langsSet) + r')\b'
        matches = re.findall(pattern, s.lower())  # Convert string to lowercase to make it case insensitive
        matches = [language_codes.get(match) for match in matches]
        return set(matches)

    def parse_torrent_description(self, desc: str) -> dict:
        # Extract size
        size_pattern = r"💾 ([\d.]+ (?:GB|MB))"
        size_match = re.search(size_pattern, desc)
        size = size_match.group(1) if size_match else None
        if size:
            size = convert_size_to_bytes(size)
        
        # Extract seeders
        seeders_pattern = r"👤 (\d+)"
        seeders_match = re.search(seeders_pattern, desc)
        seeders = int(seeders_match.group(1)) if seeders_match else None
        
        # Extract provider        
        provider_pattern = r'([🌐🔗⚙️])\s*([^🌐🔗⚙️]+)'
        provider_match = re.findall(provider_pattern, desc)

        words = [match[1].strip() for match in provider_match]
        if words:
            words = words[-1].splitlines()[0]

        provider = words
        
        desc_with_langs = desc + ' ' + ' '.join([find_language_by_unicode(flag) for flag in self.extract_unicode_flags(desc)])
        return {
            "size": size or 0,
            "seeders": seeders or 0,
            "provider": provider or '',
            'languages': self.find_languages_in_string(desc_with_langs),
        }
        
    def extract_unicode_flags(self, text):
        flag_pattern = re.compile(r'[\U0001F1E6-\U0001F1FF]{2}')
        flags = flag_pattern.findall(text)
        return flags