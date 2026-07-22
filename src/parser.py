import re
from typing import List, Dict, Optional
from src.alias_matcher import get_alias_matcher


def parse_m3u(content: str) -> List[Dict]:
    channels = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            match = re.search(r'group-title="([^"]+)"', line)
            group = match.group(1) if match else ""
            tvg_id = re.search(r'tvg-id="([^"]+)"', line)
            tvg_id = tvg_id.group(1) if tvg_id else ""
            tvg_logo = re.search(r'tvg-logo="([^"]+)"', line)
            tvg_logo = tvg_logo.group(1) if tvg_logo else ""
            parts = line.split(",")
            name = ",".join(parts[1:]).strip() if len(parts) > 1 else line
            if i + 1 < len(lines) and not lines[i+1].startswith("#"):
                url = lines[i+1].strip()
                if url.startswith(("http://", "https://")):
                    channels.append({
                        "name": name, "url": url,
                        "group_title": group, "tvg_id": tvg_id, "tvg_logo": tvg_logo
                    })
            i += 2
        else:
            i += 1
    return channels

def parse_txt(content: str) -> List[Dict]:
    channels = []
    lines = content.splitlines()
    current = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            current = line.lstrip("#").strip()
            continue
        if line.startswith(("http://", "https://")):
            name = current if current else "未知"
            channels.append({"name": name, "url": line, "group_title": "", "tvg_id": "", "tvg_logo": ""})
            current = None
    return channels

def apply_alias(channels: List[Dict]) -> List[Dict]:
    matcher = get_alias_matcher()
    if matcher:
        for ch in channels:
            ch["name"] = matcher.normalize(ch["name"])
    return channels

def parse_and_dedupe(raw: Dict[str, Optional[str]]) -> List[Dict]:
    all_ch = []
    seen = set()
    for url, content in raw.items():
        if not content:
            continue
        if content.strip().startswith("#EXTM3U"):
            channels = parse_m3u(content)
        else:
            channels = parse_txt(content)
        channels = apply_alias(channels)
        for ch in channels:
            key = f"{ch['name']}|{ch['url']}"
            if key not in seen:
                seen.add(key)
                all_ch.append(ch)
    return all_ch
