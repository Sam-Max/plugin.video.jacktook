import re

VIDEO_EXTENSIONS = (
    "avi",
    "m2ts",
    "m4v",
    "mkv",
    "mov",
    "mp4",
    "mpeg",
    "mpg",
    "ts",
    "webm",
    "wmv",
)
TECHNICAL_RELEASE_GROUP = re.compile(
    r"^(?:"
    r"(?:2160|1080|720|480)p|4k|8k|[0-9]+bit|"
    r"x26[45]|h\.?26[45]|hevc|av1|avc|"
    r"hdr(?:10\+?)?|dv|dolby-vision|"
    r"web(?:-dl)?|webrip|bluray|bdrip|brrip|remux|"
    r"proper|repack|real|complete|internal|"
    r"multi|dual|latino|castellano|english|spanish|german|french|italian|"
    r"japanese|korean|russian|"
    r"dts(?:-hd|-x)?|truehd|atmos|aac|ac3|e-?ac3|ddp?[0-9]*|flac|opus|mp3|"
    r"[0-9]+ch|dl|[0-9]{3,4}x[0-9]{3,4}|s[0-9]+e[0-9]+"
    r")$",
    re.IGNORECASE,
)


def get_color_tag(label, text, color):
    # Standardized format [B]LABEL: VALUE[/B]
    clean_color = color.replace("FF", "CC")
    return f"[B][COLOR CCFFFFFF]{label}[/COLOR] [COLOR {clean_color}]{text}[/COLOR][/B]"


def clean_display_title(title):
    if not title:
        return ""

    # Redundant tags to remove (expanded list)
    tags_to_remove = [
        r"\b2160P\b",
        r"\b1080P\b",
        r"\b720P\b",
        r"\b480P\b",
        r"\b4K\b",
        r"\bHEVC\b",
        r"\bH265\b",
        r"\bH\.265\b",
        r"\bX265\b",
        r"\bH264\b",
        r"\bH\.264\b",
        r"\bX264\b",
        r"\bAVC\b",
        r"\bAV1\b",
        r"\bDV\b",
        r"\bDOLBY VISION\b",
        r"\bDOLBYVISION\b",
        r"\bHDR10\+\b",
        r"\bHDR10\b",
        r"\bHDR\b",
        r"\bHYBRID\b",
        r"\bREMUX\b",
        r"\bWEB-DL\b",
        r"\bWEBDL\b",
        r"\bWEB\b",
        r"\bBRRIP\b",
        r"\bBDRIP\b",
        r"\bBLURAY\b",
        r"\b10BIT\b",
        r"\b8BIT\b",
        r"\b12BIT\b",
        r"\.MKV\b",
        r"\.MP4\b",
        r"\.AVI\b",
        r"\.TS\b",
        r"\.M2TS\b",
        r"\bIMAX\b",
        r"\bEXTENDED\b",
        r"\bREMASTERED\b",
        r"\bUNRATED\b",
        r"\bDIRECTORS CUT\b",
        r"\bPROPER\b",
        r"\bREPACK\b",
        r"\bREAL\b",
        r"\b7\.1\b",
        r"\b5\.1\b",
        r"\b2\.0\b",
        r"\b8CH\b",
        r"\b6CH\b",
        r"\bLATINO\b",
        r"\bCASTELLANO\b",
        r"\bSPANISH\b",
        r"\bDUAL\b",
        r"\bMULTI\b",
    ]

    clean_title = title
    for tag in tags_to_remove:
        clean_title = re.sub(tag, "", clean_title, flags=re.IGNORECASE)

    # Clean up extra dots, underscores, and spaces
    clean_title = (
        clean_title.replace(".", " ")
        .replace("_", " ")
        .replace("[", " ")
        .replace("]", " ")
        .replace("(", " ")
        .replace(")", " ")
    )
    clean_title = re.sub(r"\s+", " ", clean_title).strip()

    if clean_title:
        clean_title = clean_title.capitalize()

    return clean_title


def extract_codec_hdr(title):
    if not title:
        return "", ""

    title_upper = (
        title.upper()
        .replace(".", " ")
        .replace("_", " ")
        .replace("-", " ")
        .replace("[", " ")
        .replace("]", " ")
    )

    codec = ""
    if any(x in title_upper for x in ["HEVC", "H265", "X265"]):
        codec = "HEVC"
    elif any(x in title_upper for x in ["H264", "X264", "AVC"]):
        codec = "H.264"
    elif "AV1" in title_upper:
        codec = "AV1"

    hdr = ""
    if any(x in title_upper for x in [" DV ", "DOLBY VISION"]):
        hdr = "DV"
    elif "HDR10+" in title_upper:
        hdr = "HDR10+"
    elif "HDR10" in title_upper:
        hdr = "HDR10"
    elif "HDR" in title_upper:
        hdr = "HDR"

    return codec, hdr


def _extract_release_group(title):
    title_without_extension = re.sub(
        rf"\.({'|'.join(VIDEO_EXTENSIONS)})$", "", title.strip(), flags=re.IGNORECASE
    )
    candidates = []
    remaining_title = title_without_extension

    while True:
        match = re.match(r"^\s*\[([a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*)\]\s*", remaining_title)
        if not match:
            break
        candidate = match.group(1)
        if not TECHNICAL_RELEASE_GROUP.fullmatch(candidate):
            candidates.append(candidate)
        remaining_title = remaining_title[match.end() :]

    match = re.search(r"-([a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*)$", title_without_extension)
    if match and not TECHNICAL_RELEASE_GROUP.fullmatch(match.group(1)):
        candidates.append(match.group(1))

    unique_candidates = {}
    for candidate in candidates:
        unique_candidates.setdefault(candidate.casefold(), candidate)
    if len(unique_candidates) != 1:
        return ""
    return next(iter(unique_candidates.values()))


def parse_title_info(title):
    if not title:
        return {
            "codec": "",
            "audio": "",
            "hdr": "",
            "source": "",
            "format": "",
            "edition": "",
            "note": "",
            "lang_detail": "",
            "clean_title": "",
            "badges": "",
            "release_group": "",
        }

    info = {
        "codec": "",
        "audio": "",
        "hdr": "",
        "source": "",
        "format": "",
        "edition": "",
        "note": "",
        "lang_detail": "",
        "release_group": "",
        "clean_title": clean_display_title(title),
        "badges": "",
    }

    title_upper = (
        title.upper()
        .replace(".", " ")
        .replace("_", " ")
        .replace("-", " ")
        .replace("[", " ")
        .replace("]", " ")
    )

    # 1. Video & Bit Depth
    bit_depth = "10bit" if "10BIT" in title_upper else "12bit" if "12BIT" in title_upper else ""
    if any(x in title_upper for x in ["HEVC", "H265", "X265"]):
        val = f"HEVC {bit_depth}".strip()
        info["codec"] = get_color_tag("VIDEO:", val, "FF00FF00")
    elif any(x in title_upper for x in ["H264", "X264", "AVC"]):
        val = f"H.264 {bit_depth}".strip()
        info["codec"] = get_color_tag("VIDEO:", val, "FF9ACD32")
    elif "AV1" in title_upper:
        val = f"AV1 {bit_depth}".strip()
        info["codec"] = get_color_tag("VIDEO:", val, "FF9ACD32")

    # 2. Audio & Channels
    channels = ""
    if "7 1" in title_upper or "8CH" in title_upper:
        channels = "7.1"
    elif "5 1" in title_upper or "6CH" in title_upper:
        channels = "5.1"
    elif "2 0" in title_upper or "2CH" in title_upper:
        channels = "2.0"

    audio_format = ""
    if "ATMOS" in title_upper:
        audio_format = "ATMOS"
    elif "DTS-HD" in title_upper or "DTSHD" in title_upper:
        audio_format = "DTS-HD"
    elif "DTS-X" in title_upper or "DTSX" in title_upper:
        audio_format = "DTS:X"
    elif "TRUEHD" in title_upper:
        audio_format = "TRUEHD"
    elif any(x in title_upper for x in ["DD+", "DDP", "E-AC3"]):
        audio_format = "DD+"
    elif any(x in title_upper for x in ["AC3", "DD5 1"]):
        audio_format = "AC3"

    if audio_format or channels:
        val = f"{audio_format} {channels}".strip()
        info["audio"] = get_color_tag("AUDIO:", val, "FF00BFFF")

    # 3. HDR & Hybrid
    hdr_val = ""
    is_hybrid = "HYBRID" in title_upper
    if any(x in title_upper for x in [" DV ", "DOLBY VISION"]):
        hdr_val = "DV"
    elif "HDR10+" in title_upper:
        hdr_val = "HDR10+"
    elif "HDR10" in title_upper:
        hdr_val = "HDR10"
    elif "HDR" in title_upper:
        hdr_val = "HDR"

    if hdr_val:
        val = f"{hdr_val} HYBRID" if is_hybrid else hdr_val
        info["hdr"] = get_color_tag("HDR:", val, "FFFFA500")

    # 4. Editions
    editions = []
    if "IMAX" in title_upper:
        editions.append("IMAX")
    if "EXTENDED" in title_upper:
        editions.append("EXTENDED")
    if "DIRECTOR" in title_upper and "CUT" in title_upper:
        editions.append("DIRECTOR'S CUT")
    if "UNRATED" in title_upper:
        editions.append("UNRATED")
    if "REMASTERED" in title_upper:
        editions.append("REMASTERED")
    if editions:
        info["edition"] = get_color_tag("EDITION:", " ".join(editions), "FFDA70D6")

    # 5. Integrity Notes
    notes = []
    if "PROPER" in title_upper:
        notes.append("PROPER")
    if "REPACK" in title_upper:
        notes.append("REPACK")
    if "REAL" in title_upper:
        notes.append("REAL")
    if notes:
        info["note"] = get_color_tag("NOTE:", " ".join(notes), "FFFF4500")

    # 6. Language Details
    lang = ""
    if "LATINO" in title_upper or " LAT " in title_upper:
        lang = "LATINO"
    elif "CASTELLANO" in title_upper or " SPA " in title_upper:
        lang = "CASTELLANO"
    elif "DUAL" in title_upper:
        lang = "DUAL"
    elif "MULTI" in title_upper:
        lang = "MULTI"
    if lang:
        info["lang_detail"] = get_color_tag("LANG:", lang, "FFFFD700")

    # 7. Format & Source
    if "MKV" in title_upper:
        info["format"] = get_color_tag("FORMAT:", "MKV", "FF87CEEB")
    if "REMUX" in title_upper:
        info["source"] = get_color_tag("SOURCE:", "REMUX", "FFDA70D6")

    # Build Badge Line
    badges_list = []
    for key in [
        "codec",
        "audio",
        "hdr",
        "edition",
        "lang_detail",
        "format",
        "source",
        "note",
    ]:
        if info[key]:
            badges_list.append(info[key])

    bullet = "[COLOR 80FFFFFF] • [/COLOR]"
    info["badges"] = f"  {bullet}  ".join(badges_list)

    info["release_group"] = _extract_release_group(title)

    return info


# ── Title matching ──────────────────────────
# Normalizes titles and compares release titles against a search query so
# full-text indexers (Easynews) can drop unrelated posts.

_ACCENT_MAP = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "ß": "ss",
    "Ä": "Ae",
    "Ö": "Oe",
    "Ü": "Ue",
    "æ": "ae",
    "ø": "oe",
    "å": "aa",
    "Æ": "Ae",
    "Ø": "Oe",
    "Å": "Aa",
}


def sanitize_title(title: str) -> str:
    """Normalize a title for case-insensitive comparison.

    Converts accented characters to their digraph spelling, replaces common
    separators with a single space, drops brackets/parentheses, removes
    non-alphanumeric characters, and lowercases the result.
    """
    if not title:
        return ""
    result = title
    for char, replacement in _ACCENT_MAP.items():
        result = result.replace(char, replacement)
    result = result.replace("&", " and ")
    result = re.sub(r"[.\-_:\s]+", " ", result)
    result = re.sub(r"[\[\]\(\){}]", " ", result)
    result = re.sub(r"[^\w\sÀ-ÿ]", "", result)
    result = re.sub(r"\s+", " ", result)
    return result.lower().strip()


def is_anchored_query(query: str) -> bool:
    """Whether a query carries an episode code (SxxExx) or a 19xx/20xx year.

    Unanchored queries (bare title) are low-precision for full-text indexers;
    callers force strict matching when this returns False.
    """
    return bool(re.search(r"s\d{1,3}e\d{1,3}", query, re.IGNORECASE)) or bool(
        re.search(r"\b(?:19|20)\d{2}\b", query)
    )


def _word_in_text(word: str, text: str) -> bool:
    escaped = re.escape(word)
    return re.search(rf"\b{escaped}\b", text) is not None


def matches_title(title: str, query: str, strict: bool) -> bool:
    """Whether a release title matches a search query.

    Mirrors easynews-plus-plus matchesTitle():
    - strict: exact title match, or exact title + year / episode code.
    - non-strict: episode code present plus >=70% of the show-name words
      (whole-word), or >=70% of significant query words.
    """
    if not title or not query:
        return False

    sanitized_query = sanitize_title(query)
    sanitized_title = sanitize_title(title)

    # Main title part of the query, excluding episode info.
    main_query_part = sanitized_query.split(r"s\d+e\d+")[0].strip()
    season_episode_pattern = re.compile(r"s\d+e\d+", re.IGNORECASE)
    has_season_episode = season_episode_pattern.search(sanitized_query)

    if strict:
        if has_season_episode:
            se_match = has_season_episode
            title_before_se = sanitized_title.split(se_match.group(0))[0].strip()
            title_without_year = re.sub(r"\b(?:19|20)\d{2}\b", "", title_before_se).strip()

            if sanitized_title == main_query_part:
                return True
            if title_before_se == main_query_part or title_without_year == main_query_part:
                return True

            # Series title must start with the exact query words followed by
            # episode info (possibly with a year in between).
            main_query_words = main_query_part.split()
            title_words = title_without_year.split()
            if len(title_words) > len(main_query_words):
                return False
            return title_words == main_query_words

        # Movie path: exact title, or title + year.
        year_match = re.search(r"\b(?:19|20)\d{2}\b", sanitized_query)
        query_year = year_match.group(0) if year_match else None
        query_without_year = re.sub(r"\b(?:19|20)\d{2}\b", "", sanitized_query).strip()
        title_without_year = re.sub(r"\b(?:19|20)\d{2}\b", "", sanitized_title).strip()

        if sanitized_title == sanitized_query:
            return True
        if query_year and title_without_year == query_without_year:
            return True
        return title_without_year == sanitized_query

    # Non-strict path.
    if has_season_episode:
        pattern = has_season_episode.group(0).lower()
        if pattern not in sanitized_title:
            return False
        name_words = [
            w
            for w in re.sub(season_episode_pattern, " ", sanitized_query).split()
            if len(w) > 2
        ]
        if not name_words:
            return True
        matching = sum(1 for w in name_words if _word_in_text(w, sanitized_title))
        return matching / len(name_words) >= 0.7

    query_words = sanitized_query.split()
    significant_words = [w for w in query_words if len(w) > 2]
    if not significant_words:
        return True
    matching = sum(1 for w in significant_words if _word_in_text(w, sanitized_title))
    return matching / len(significant_words) >= 0.7
