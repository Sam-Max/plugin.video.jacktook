import re

def get_color_tag(label, text, color):
    # Standardized format [B]LABEL: VALUE[/B]
    clean_color = color.replace("FF", "CC")
    return f"[B][COLOR CCFFFFFF]{label}[/COLOR] [COLOR {clean_color}]{text}[/COLOR][/B]"

def clean_display_title(title):
    if not title:
        return ""
    
    # Redundant tags to remove (expanded list)
    tags_to_remove = [
        r"\b2160P\b", r"\b1080P\b", r"\b720P\b", r"\b480P\b", r"\b4K\b",
        r"\bHEVC\b", r"\bH265\b", r"\bH\.265\b", r"\bX265\b",
        r"\bH264\b", r"\bH\.264\b", r"\bX264\b", r"\bAVC\b",
        r"\bDV\b", r"\bDOLBY VISION\b", r"\bDOLBYVISION\b",
        r"\bHDR10\+\b", r"\bHDR10\b", r"\bHDR\b", r"\bHYBRID\b",
        r"\bREMUX\b", r"\bWEB-DL\b", r"\bWEBDL\b", r"\bWEB\b", r"\bBRRIP\b", r"\bBDRIP\b", r"\bBLURAY\b",
        r"\b10BIT\b", r"\b8BIT\b", r"\b12BIT\b",
        r"\.MKV\b", r"\.MP4\b", r"\.AVI\b", r"\.TS\b", r"\.M2TS\b",
        r"\bIMAX\b", r"\bEXTENDED\b", r"\bREMASTERED\b", r"\bUNRATED\b", r"\bDIRECTORS CUT\b",
        r"\bPROPER\b", r"\bREPACK\b", r"\bREAL\b",
        r"\b7\.1\b", r"\b5\.1\b", r"\b2\.0\b", r"\b8CH\b", r"\b6CH\b",
        r"\bLATINO\b", r"\bCASTELLANO\b", r"\bSPANISH\b", r"\bDUAL\b", r"\bMULTI\b"
    ]
    
    clean_title = title
    for tag in tags_to_remove:
        clean_title = re.sub(tag, "", clean_title, flags=re.IGNORECASE)
    
    # Clean up extra dots, underscores, and spaces
    clean_title = clean_title.replace(".", " ").replace("_", " ").replace("[", " ").replace("]", " ").replace("(", " ").replace(")", " ")
    clean_title = re.sub(r"\s+", " ", clean_title).strip()
    
    if clean_title:
        clean_title = clean_title.capitalize()
    
    return clean_title

def parse_title_info(title):
    if not title:
        return {"codec": "", "audio": "", "hdr": "", "source": "", "format": "", "edition": "", "note": "", "lang_detail": "", "clean_title": "", "badges": "", "release_group": ""}
    
    info = {
        "codec": "", "audio": "", "hdr": "", "source": "", "format": "", 
        "edition": "", "note": "", "lang_detail": "", "release_group": "",
        "clean_title": clean_display_title(title),
        "badges": ""
    }
    
    title_upper = title.upper().replace(".", " ").replace("_", " ").replace("-", " ").replace("[", " ").replace("]", " ")
    
    # 1. Video & Bit Depth
    bit_depth = "10bit" if "10BIT" in title_upper else "12bit" if "12BIT" in title_upper else ""
    if any(x in title_upper for x in ["HEVC", "H265", "X265"]):
        val = f"HEVC {bit_depth}".strip()
        info["codec"] = get_color_tag("VIDEO:", val, "FF00FF00")
    elif any(x in title_upper for x in ["H264", "X264", "AVC"]):
        val = f"H.264 {bit_depth}".strip()
        info["codec"] = get_color_tag("VIDEO:", val, "FF9ACD32")
    
    # 2. Audio & Channels
    channels = ""
    if "7 1" in title_upper or "8CH" in title_upper: channels = "7.1"
    elif "5 1" in title_upper or "6CH" in title_upper: channels = "5.1"
    elif "2 0" in title_upper or "2CH" in title_upper: channels = "2.0"
    
    audio_format = ""
    if "ATMOS" in title_upper: audio_format = "ATMOS"
    elif "DTS-HD" in title_upper or "DTSHD" in title_upper: audio_format = "DTS-HD"
    elif "DTS-X" in title_upper or "DTSX" in title_upper: audio_format = "DTS:X"
    elif "TRUEHD" in title_upper: audio_format = "TRUEHD"
    elif any(x in title_upper for x in ["DD+", "DDP", "E-AC3"]): audio_format = "DD+"
    elif any(x in title_upper for x in ["AC3", "DD5 1"]): audio_format = "AC3"
    
    if audio_format or channels:
        val = f"{audio_format} {channels}".strip()
        info["audio"] = get_color_tag("AUDIO:", val, "FF00BFFF")
    
    # 3. HDR & Hybrid
    hdr_val = ""
    is_hybrid = "HYBRID" in title_upper
    if any(x in title_upper for x in [" DV ", "DOLBY VISION"]): hdr_val = "DV"
    elif "HDR10+" in title_upper: hdr_val = "HDR10+"
    elif "HDR10" in title_upper: hdr_val = "HDR10"
    elif "HDR" in title_upper: hdr_val = "HDR"
    
    if hdr_val:
        val = f"{hdr_val} HYBRID" if is_hybrid else hdr_val
        info["hdr"] = get_color_tag("HDR:", val, "FFFFA500")
    
    # 4. Editions
    editions = []
    if "IMAX" in title_upper: editions.append("IMAX")
    if "EXTENDED" in title_upper: editions.append("EXTENDED")
    if "DIRECTOR" in title_upper and "CUT" in title_upper: editions.append("DIRECTOR'S CUT")
    if "UNRATED" in title_upper: editions.append("UNRATED")
    if "REMASTERED" in title_upper: editions.append("REMASTERED")
    if editions:
        info["edition"] = get_color_tag("EDITION:", " ".join(editions), "FFDA70D6")
    
    # 5. Integrity Notes
    notes = []
    if "PROPER" in title_upper: notes.append("PROPER")
    if "REPACK" in title_upper: notes.append("REPACK")
    if "REAL" in title_upper: notes.append("REAL")
    if notes:
        info["note"] = get_color_tag("NOTE:", " ".join(notes), "FFFF4500")
    
    # 6. Language Details
    lang = ""
    if "LATINO" in title_upper or " LAT " in title_upper: lang = "LATINO"
    elif "CASTELLANO" in title_upper or " SPA " in title_upper: lang = "CASTELLANO"
    elif "DUAL" in title_upper: lang = "DUAL"
    elif "MULTI" in title_upper: lang = "MULTI"
    if lang:
        info["lang_detail"] = get_color_tag("LANG:", lang, "FFFFD700")

    # 7. Format & Source
    if "MKV" in title_upper: info["format"] = get_color_tag("FORMAT:", "MKV", "FF87CEEB")
    if "REMUX" in title_upper: info["source"] = get_color_tag("SOURCE:", "REMUX", "FFDA70D6")
    
    # Build Badge Line
    badges_list = []
    for key in ["codec", "audio", "hdr", "edition", "lang_detail", "format", "source", "note"]:
        if info[key]: badges_list.append(info[key])
    
    bullet = "[COLOR 80FFFFFF] • [/COLOR]"
    info["badges"] = f"  {bullet}  ".join(badges_list)
    
    # Release Group
    match = re.search(r"-([a-zA-Z0-9]+)$", title)
    if match: info["release_group"] = match.group(1)
    
    return info
