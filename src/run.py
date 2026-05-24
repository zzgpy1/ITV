#!/usr/bin/env python3
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    IPTV_SOURCES, ENABLE_REGION_FILTER, PREFERRED_LOCATION, PREFERRED_ISP,
    ENABLE_IP_RESOLVE, ENABLE_DEMO_FILTER, ENABLE_ALIAS, ENABLE_BLACKLIST,
    DATABASE_ENABLE
)
from src.fetcher import fetch_all_sources
from src.parser import parse_and_dedupe
from src.speed_tester import test_channels_concurrent
from src.ffmpeg_validator import validate_batch, cleanup as ffmpeg_cleanup
from src.classifier import classify_and_filter
from src.generator import generate_outputs
from src.merger import merge_channels_by_name
from src.ip_resolver import get_resolver, matches_region
from src.blacklist_filter import get_blacklist_filter
from src.demo_filter import filter_and_order_by_demo
from src.alias_matcher import get_alias_matcher
from src.database import get_db_cache

async def init_ip_resolver():
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
        ip_info = ch.get("ip_info")
        if ip_info and matches_region(ip_info, preferred_locations, preferred_isps):
            filtered.append(ch)
    print(f"  筛选结果: {len(filtered)}/{len(channels)} 个频道通过地域筛选")
    return filtered

async def main():
    print("🚀 IPTV智能整理平台启动")
    print(f"📡 配置：超时={os.getenv('TIMEOUT','10')}s, 并发={os.getenv('MAX_WORKERS','10')}, ffmpeg={os.getenv('FFMPEG_ENABLE','true')}")
    print(f"📋 增强过滤: demo={ENABLE_DEMO_FILTER}, alias={ENABLE_ALIAS}, blacklist={ENABLE_BLACKLIST}")

    await init_ip_resolver()
    if os.getenv("FFMPEG_ENABLE", "true").lower() == "true":
        from src.ffmpeg_validator import check_ffprobe
        await check_ffprobe()

    db = await get_db_cache()
    
    # 完整采集（为了简化，始终完整采集，避免缓存不一致问题）
    print("\n📥 执行完整采集流程...")
    raw_contents = await fetch_all_sources(IPTV_SOURCES)
    channels_dict = parse_and_dedupe(raw_contents)
    if not channels_dict:
        print("❌ 未获取到任何频道，请检查网络或源地址")
        return 1
    
    print(f"📊 原始频道数（去重后）: {len(channels_dict)}")
    
    valid_channels = await test_channels_concurrent(channels_dict)
    print(f"📊 通过HTTP测速的频道数: {len(valid_channels)}")
    
    valid_channels = await validate_batch(valid_channels)
    print(f"📊 通过ffmpeg深度验证的频道数: {len(valid_channels)}")
    
    merged_channels = merge_channels_by_name(valid_channels)
    print(f"📊 合并后的频道数（按名称分组）: {len(merged_channels)}")
    
    if ENABLE_BLACKLIST:
        blacklist_filter = get_blacklist_filter()
        before = len(merged_channels)
        merged_channels = blacklist_filter.filter_channels(merged_channels)
        print(f"📊 黑名单过滤后: {len(merged_channels)} (减少 {before - len(merged_channels)})")
    
    if ENABLE_DEMO_FILTER:
        before = len(merged_channels)
        merged_channels = filter_and_order_by_demo(merged_channels)
        print(f"📊 Demo筛选后: {len(merged_channels)} (减少 {before - len(merged_channels)})")
    
    merged_channels = filter_by_region(merged_channels)
    if not merged_channels:
        print("❌ 过滤后无有效频道")
        return 1
    
    # 分类并只保留四个大类
    classified = classify_and_filter(merged_channels)
    
    generate_outputs(classified)
    
    total = sum(len(lst) for lst in classified.values())
    print(f"🎉 完成！有效频道总数: {total}")
    ffmpeg_cleanup()
    await db.close()
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
