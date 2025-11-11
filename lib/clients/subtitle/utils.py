import re
import unicodedata


def slugify_title(title):
    title = re.sub(r"\.[^.]+$", "", title)  # Remove extension
    title = re.sub(r"[^\w\s.-]", "", title)  # Remove unwanted characters
    return title.strip()


def slugify(value):
    # 1. Normaliza el texto para separar letras acentuadas (ñ → n, á → a, etc.)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()

    # 3. Reemplaza espacios y guiones múltiples con un solo guion bajo
    return re.sub(r"[-\s]+", "_", value)


def get_deepl_language_code(language_name):
    language_mapping = {
        "None": "None",
        "العربية": "ar",
        "Български": "bg",
        "中文": "zh",
        "繁體中文": "zh-Hant",
        "简体中文": "zh-Hans",
        "Čeština": "cs",
        "Dansk": "da",
        "Nederlands": "nl",
        "English": "en",
        "English (British)": "en-GB",
        "English (American)": "en-US",
        "Eesti": "et",
        "Suomi": "fi",
        "Français": "fr",
        "Deutsch": "de",
        "Ελληνικά": "el",
        "Magyar": "hu",
        "Indonesia": "id",
        "Italiano": "it",
        "日本語": "ja",
        "한국어": "ko",
        "Latviešu": "lv",
        "Lietuvių": "lt",
        "Norsk (Bokmål)": "nb",
        "Polski": "pl",
        "Português": "pt",
        "Português (Brasil)": "pt-BR",
        "Română": "ro",
        "Русский": "ru",
        "Slovenčina": "sk",
        "Slovenščina": "sl",
        "Español": "es",
        "Svenska": "sv",
        "Türkçe": "tr",
        "Українська": "uk",
    }
    return language_mapping.get(language_name, None)


def get_language_code(language_name):
    """
    Convert full language names to ISO 639-1 or 639-2 language codes.
    """
    language_map = {
        "None": "None",
        "Arabic": "ara",
        "Bulgarian": "bul",
        "Czech": "ces",
        "Danish": "dan",
        "German": "deu",
        "Greek": "ell",
        "English": "eng",
        "Spanish": "spa",
        "Estonian": "est",
        "Finnish": "fin",
        "French": "fra",
        "Hungarian": "hun",
        "Indonesian": "ind",
        "Italian": "ita",
        "Japanese": "jpn",
        "Korean": "kor",
        "Lithuanian": "lit",
        "Latvian": "lav",
        "Dutch": "nld",
        "Polish": "pol",
        "Portuguese": "por",
        "Romanian": "ron",
        "Russian": "rus",
        "Slovak": "slk",
        "Slovenian": "slv",
        "Swedish": "swe",
        "Turkish": "tur",
        "Ukrainian": "ukr",
        "Chinese": "zho",
    }

    return language_map.get(language_name, None)


def language_code_to_name(code):
    """
    Convert ISO 639-1 or 639-2 language codes to full language names.
    """
    lang_map = {
        "eng": "English",
        "fre": "French",
        "fra": "French",
        "ger": "German",
        "deu": "German",
        "spa": "Spanish",
        "spl": "Spanish (Latin)",
        "srp": "Serbian",
        "hrv": "Croatian",
        "slo": "Slovak",
        "slk": "Slovak",
        "slv": "Slovenian",
        "ell": "Greek",
        "gre": "Greek",
        "ara": "Arabic",
        "jpn": "Japanese",
        "vie": "Vietnamese",
        "ron": "Romanian",
        "rum": "Romanian",
        "kur": "Kurdish",
        "ind": "Indonesian",
        "tur": "Turkish",
        "mal": "Malayalam",
        "per": "Persian",
        "fas": "Persian",
        "ita": "Italian",
        "nld": "Dutch",
        "dut": "Dutch",
        "por": "Portuguese",
        "zho": "Chinese",
        "chi": "Chinese",
        # Add more as needed
    }

    return lang_map.get(code.lower(), f"Unknown ({code})")
