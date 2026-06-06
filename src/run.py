#!/usr/bin/env python3
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (
    IPTV_SOURCES, OUTPUT_DIR, ENABLE_REGION_FILTER,
    PREFERRED_LOCATION, PREFERRED_ISP, ENABLE_IP_RESOLVE,
    ENABLE_DEMO_FILTER, ENABLE_ALIAS, ENABLE_BLACKLIST,
    CCTV_ORDER, MAX_WORKERS, TIMEOUT
)
from src.fetcher import fetch_all_sources
from src.parser import parse_and_dedupe
from src.speed_tester import test_channels_concurrent
from src.ffmpeg_validator import validate_with_ffmpeg_batch
from src.classifier import classify_channel
from src.generator import generate_outputs
from src.merger import merge_channels_by_name
from src.ip_resolver import get_resolver, matches_region
from src.cache_manager import CacheManager
from src.blacklist_filter import get_blacklist_filter
from src.demo_filter import filter_and_order_by_demo
from src.alias_matcher import get_alias_matcher

ALLOWED_CATEGORIES = {"央视", "卫视", "地方", "港澳台"}

def init_ip_resolver():
    if not ENABLE_IP_RESOLVE:
        print("⚙️ IP解析未启用")
        return
    resolver = get_resolver()
    if resolver.is_available:
        print("✅ IP解析器已就绪")
    else:
        print("⚠️ IP解析器不可用，将跳过地域筛选")

def filter_by_region(channels):
    if not ENABLE_REGION_FILTER:
        return channels
    preferred_locations = [loc.strip() for loc in PREFERRED_LOCATION.split(",") if loc.strip()]
    preferred_isps = [isp.strip() for isp in PREFERRED_ISP.split(",") if isp.strip()]
    if not preferred_locations and not preferred_isps:
        return channels
    print(f"🎯 地域筛选: 地域={preferred_locations}, 运营商={preferred_isps}")
    resolver = get_resolver()
    if not resolver.is_available:
        print("⚠️ IP解析器不可用，跳过地域筛选")
        return channels
    filtered = []
    for ch in channels:
        ip_info = ch.get("ip_info") if isinstance(ch, dict) else getattr(ch, 'ip_info', None)
        if ip_info and matches_region(ip_info, preferred_locations, preferred_isps):
            filtered.append(ch)
    print(f"  筛选结果: {len(filtered)}/{len(channels)} 个频道通过地域筛选")
    return filtered

def build_classified_from_ordered(ordered_channels, alias_matcher=None):
    temp = {cat: [] for cat in ALLOWED_CATEGORIES}
    for ch in ordered_channels:
        orig_name = ch.name if hasattr(ch, 'name') else ch.get('name', '')
        display_name = orig_name
        if alias_matcher:
            mapped = alias_matcher.match(orig_name)
            if mapped:
                display_name = mapped
        if alias_matcher and mapped:
            if hasattr(ch, 'name'):
                old = ch.name
                ch.name = mapped
                cat = classify_channel(ch)
                ch.name = old
            elif isinstance(ch, dict):
                old = ch['name']
                ch['name'] = mapped
                cat = classify_channel(ch)
                ch['name'] = old
            else:
                cat = classify_channel(ch)
        else:
            cat = classify_channel(ch)
        if cat in ["🌊港·澳·台", "港澳台"]:
            cat = "港澳台"
        if cat not in ALLOWED_CATEGORIES:
            continue
        if isinstance(ch, dict):
            ch_dict = ch
        elif hasattr(ch, 'to_dict'):
            ch_dict = ch.to_dict()
        else:
            ch_dict = {
                "name": display_name,
                "url": getattr(ch, 'url', ''),
                "urls": getattr(ch, 'urls', [getattr(ch, 'url', '')]),
                "group_title": getattr(ch, 'group_title', ''),
                "id": getattr(ch, 'tvg_id', ''),
                "logo": getattr(ch, 'tvg_logo', ''),
                "latency": getattr(ch, 'latency', 9999),
                "video_codec": getattr(ch, 'video_codec', ''),
                "ip_info": getattr(ch, 'ip_info', None)
            }
        temp[cat].append(ch_dict)
    def ctv_key(ch):
        name = ch["name"]
        for idx, std in enumerate(CCTV_ORDER):
            if std.lower() in name.lower() or name.lower() in std.lower():
                return idx
        return len(CCTV_ORDER)
    if temp["央视"]:
        temp["央视"] = sorted(temp["央视"], key=ctv_key)
    result = {}
    for cat in ["央视", "卫视", "地方", "港澳台"]:
        if temp.get(cat):
            result[cat] = temp[cat]
        else:
            result[cat] = []
    print("📊 分类统计（强制顺序：央视、卫视、地方、港澳台）：")
    for cat, lst in result.items():
        if lst:
            print(f"  {cat}: {len(lst)} 个频道")
    return result

async def full_update(alias_matcher):
    print("\n📥 执行全量采集流程...")
    steps = [
        "拉取源文件", "解析并去重", "HTTP测速", "ffmpeg深度验证", "合并多源", "应用过滤规则"
    ]
    for i, step in enumerate(steps, 1):
        print(f"\n[{i}/6] {step}...")
        if step == "拉取源文件":
            raw_contents = await fetch_all_sources(IPTV_SOURCES)
        elif step == "解析并去重":
            channels_dict = parse_and_dedupe(raw_contents)
            if not channels_dict:
                print("❌ 未获取到任何频道")
                return None
            total_before = len(channels_dict)
            print(f"   去重后共 {total_before} 个频道")
        elif step == "HTTP测速":
            valid = await test_channels_concurrent(channels_dict)
            if not valid:
                print("❌ 无有效频道")
                return None
            print(f"   测速通过 {len(valid)}/{total_before}")
        elif step == "ffmpeg深度验证":
            valid = await validate_with_ffmpeg_batch(valid)
            if not valid:
                print("❌ 深度验证后无有效频道")
                return None
            print(f"   通过 {len(valid)} 个")
        elif step == "合并多源":
            merged = merge_channels_by_name(valid)
        elif step == "应用过滤规则":
            if ENABLE_BLACKLIST:
                merged = get_blacklist_filter().filter_channels(merged)
            if ENABLE_DEMO_FILTER:
                merged = filter_and_order_by_demo(merged, alias_matcher=alias_matcher)
            merged = filter_by_region(merged)
    return merged

async def main():
    print("🚀 IPTV智能整理平台启动")
    print(f"📡 配置：超时={TIMEOUT}s, 并发={MAX_WORKERS}, ffmpeg={os.getenv('FFMPEG_ENABLE','true')}")
    print(f"📋 增强过滤: demo={ENABLE_DEMO_FILTER}, alias={ENABLE_ALIAS}, blacklist={ENABLE_BLACKLIST}")

    init_ip_resolver()
    if os.getenv("FFMPEG_ENABLE", "true").lower() == "true":
        from src.ffmpeg_validator import check_ffprobe
        await check_ffprobe()

    cache = CacheManager()
    alias_matcher = get_alias_matcher() if ENABLE_ALIAS else None

    if cache.should_full_update():
        final_channels = await full_update(alias_matcher)
        if not final_channels:
            return 1
        cache.save_to_cache(final_channels, verified=True)
    else:
        print("\n📦 使用缓存数据（增量模式）...")
        cached = cache.load_active_channels()
        if not cached:
            print("⚠️ 缓存无有效数据，执行全量采集...")
            final_channels = await full_update(alias_matcher)
            if not final_channels:
                return 1
            cache.save_to_cache(final_channels, verified=True)
        else:
            # 直接使用缓存，无需重新验证（7天内有效）
            class SimpleChannel:
                def __init__(self, data):
                    self.name = data['name']
                    self.url = data['url']
                    self.latency = data.get('latency', 9999)
                    self.video_codec = data.get('video_codec', '')
                    self.group_title = data.get('group_title', '')
                    self.tvg_id = data.get('id', '')
                    self.tvg_logo = data.get('logo', '')
                    self.ip_info = data.get('ip_info')
            simple = [SimpleChannel(rec) for rec in cached]
            merged = merge_channels_by_name(simple)
            if ENABLE_BLACKLIST:
                merged = get_blacklist_filter().filter_channels(merged)
            if ENABLE_DEMO_FILTER:
                final_channels = filter_and_order_by_demo(merged, alias_matcher=alias_matcher)
            else:
                final_channels = merged

    classified = build_classified_from_ordered(final_channels, alias_matcher=alias_matcher)
    generate_outputs(classified)

    total = sum(len(lst) for lst in classified.values())
    print(f"🎉 完成！有效频道总数: {total}")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        sys.exit(1)
