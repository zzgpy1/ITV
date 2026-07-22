# src/parser.py
import re
from typing import List, Dict
from src.alias_matcher import get_alias_matcher
from src.logger import logger

def parse_m3u(content: str) -> List[Dict]:
    channels = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            group_title = ""
            tvg_id = ""
            tvg_logo = ""
            for attr in ["group-title", "tvg-id", "tvg-logo"]:
                m = re.search(rf'{attr}="([^"]+)"', line)
                if m:
                    if attr == "group-title":
                        group_title = m.group(1)
                    elif attr == "tvg-id":
                        tvg_id = m.group(1)
                    elif attr == "tvg-logo":
                        tvg_logo = m.group(1)
            parts = line.split(",")
            name = ",".join(parts[1:]).strip() if len(parts) >= 2 else line
            if i + 1 < len(lines) and not lines[i+1].startswith("#"):
                url = lines[i+1].strip()
                if url.startswith(("http://", "https://", "rtmp://")):
                    channels.append({
                        "name": name,
                        "url": url,
                        "group_title": group_title,
                        "tvg_id": tvg_id,
                        "tvg_logo": tvg_logo,
                        "source_url": "m3u"
                    })
            i += 2
        else:
            i += 1
    return channels

def parse_txt(content: str) -> List[Dict]:
    channels = []
    lines = content.splitlines()
    for line in lines:
        if line.startswith("#") or not line:
            continue
        if "," in line:
            name, url = line.split(",", 1)
            if url.startswith(("http://", "https://")):
                channels.append({"name": name.strip(), "url": url.strip(), "group_title": "", "tvg_id": "", "tvg_logo": ""})
    return channels

def apply_alias(channels: List[Dict]) -> List[Dict]:
    matcher = get_alias_matcher()
    if matcher:
        for ch in channels:
            std = matcher.normalize(ch["name"])
            if std != ch["name"]:
                ch["name"] = std
    return channels

def parse_and_dedupe(raw_contents: dict) -> dict:
    all_channels = {}
    for source_url, content in raw_contents.items():
        if not content:
            continue
        if content.strip().startswith("#EXTM3U"):
            channels = parse_m3u(content)
        else:
            channels = parse_txt(content)
        channels = apply_alias(channels)
        for ch in channels:
            ch["source_url"] = source_url
            key = f"{ch['name']}|{ch['url']}"
            if key not in all_channels:
                all_channels[key] = ch
    logger.info(f"解析去重后 {len(all_channels)} 个频道")
    return all_channels
