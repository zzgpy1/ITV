import re
from collections import defaultdict
from src.settings import settings
from src.logger import logger
from src.models import Stable
from src.repositories import StableRepository
from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES

def normalize_name(name: str) -> str:
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*|备用)\s*', '', name, flags=re.I)
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def get_cctv_standard(name: str) -> str:
    # 略，保留原有逻辑
    import re
    m = re.search(r'cctv[-\s]*(\d+)(?:\+|plus)?', name, re.I)
    if m:
        num = m.group(1)
        if '+' in name.lower() or 'plus' in name.lower():
            return f"CCTV-{num}+"
        return f"CCTV-{num}"
    return None

def get_quality_score(ch: dict) -> tuple:
    if ch.get('is_fixed'):
        return (0, 0, 0)
    codec = ch.get('video_codec', '').lower()
    codec_prio = 1 if codec == 'h264' else 2 if codec in ['hevc','h265'] else 3
    latency = ch.get('latency', 9999)
    return (codec_prio, latency, 0)

async def merge_channels(valid_channels: list) -> list:
    groups = defaultdict(list)
    for ch in valid_channels:
        raw = ch['name']
        std = get_cctv_standard(raw)
        norm = std if std else normalize_name(raw)
        if not norm or len(norm) < 2:
            norm = raw
        groups[norm].append(ch)

    # 加载稳定源（用于覆盖）
    stable_repo = StableRepository()
    stables = await stable_repo.get_all()

    merged = []
    for norm, ch_list in groups.items():
        ch_list.sort(key=get_quality_score)
        top = ch_list[:settings.max_sources_per_channel]
        primary = top[0] if top else None
        if not primary:
            continue
        # 检查是否有稳定源覆盖
        stable = stables.get(norm)
        if stable and stable.url:
            primary['url'] = stable.url
            primary['latency'] = stable.latency
            primary['video_codec'] = stable.video_codec
            primary['is_fixed'] = stable.is_fixed
        merged.append({
            'name': norm,
            'urls': [c['url'] for c in top],
            'url': primary['url'],
            'latency': primary.get('latency', 9999),
            'video_codec': primary.get('video_codec', ''),
            'group_title': primary.get('group_title', ''),
            'is_fixed': primary.get('is_fixed', False)
        })

    # 固定源强制补充
    if ENABLE_FIXED_SOURCES:
        for fixed_name, fixed_urls in CCTV_FIXED_SOURCES.items():
            if isinstance(fixed_urls, str):
                fixed_urls = [fixed_urls]
            if not fixed_urls:
                continue
            url = fixed_urls[0]
            # 如果已存在则更新，否则追加
            exist = next((ch for ch in merged if ch['name'] == fixed_name), None)
            if exist:
                exist['url'] = url
                exist['urls'] = [url] + [u for u in exist['urls'] if u != url][:settings.max_sources_per_channel-1]
                exist['is_fixed'] = True
            else:
                merged.append({
                    'name': fixed_name,
                    'urls': fixed_urls,
                    'url': url,
                    'latency': 50,
                    'video_codec': 'h264',
                    'group_title': '央视',
                    'is_fixed': True
                })
    logger.info(f"合并后共 {len(merged)} 个频道")
    return merged
