#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV 频道缓存管理器
"""

import time
import os
from src.db_manager import IPTVDatabase, DATA_EXPIRY_SECONDS

class CacheManager:
    def __init__(self):
        self.db = IPTVDatabase()
        self.stats = self.db.get_stats()
        # 打印数据库统计
        print(f"📊 数据库统计: 总计={self.stats['total_channels']}, 活跃={self.stats.get('active', 0)}, 失效={self.stats.get('failed', 0)}, 近期有效={self.stats.get('recent_valid', 0)}")
        print(f"📅 数据有效期: {DATA_EXPIRY_SECONDS // 86400}天, 全量更新阈值: 30天")

    def should_update(self) -> bool:
        """
        判断是否需要执行完整采集更新：
        1. 数据库为空 → 需要更新
        2. 数据已超过有效期 → 需要更新
        3. 距离上次全量更新超过30天 → 需要更新
        4. 否则不需要
        """
        if self.stats["total_channels"] == 0:
            print("📦 数据库为空，需要执行完整采集")
            return True

        # 检查数据是否过期
        if self.db.is_stale():
            print(f"⏰ 缓存数据已超过 {DATA_EXPIRY_SECONDS // 3600} 小时，需要执行完整采集")
            return True

        # 检查全量更新阈值（30天）
        last_full = self.db.get_last_full_update_time()
        if last_full is None:
            print("📦 从未执行全量采集，需要执行")
            return True
        if (int(time.time()) - last_full) > 30 * 24 * 3600:
            print("⏰ 距离上次全量采集已超过30天，需要执行完整采集")
            return True

        print(f"✅ 缓存数据有效（上次更新: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.db.get_last_update_time()))}），跳过完整采集")
        return False

    def load_from_cache(self):
        """从缓存加载频道数据（返回每个 URL 一条记录的列表）"""
        channels = self.db.load_valid_channels(skip_old=False)
        print(f"📂 从缓存加载了 {len(channels)} 个频道（每个 URL 一条记录）")
        return channels

    def save_to_cache(self, channels):
        """
        保存频道数据到缓存（自动展开多源）
        channels: 列表，每个元素可以是包含 urls 或 url 的字典/对象
        """
        records = []
        for ch in channels:
            if isinstance(ch, dict):
                if 'urls' in ch and ch['urls']:
                    for url in ch['urls']:
                        record = {
                            "name": ch.get("name", ""),
                            "url": url,
                            "group_title": ch.get("group_title", ""),
                            "id": ch.get("id", ""),
                            "logo": ch.get("logo", ""),
                            "latency": ch.get("latency", 9999),
                            "video_codec": ch.get("video_codec", ""),
                            "ip_info": ch.get("ip_info")
                        }
                        records.append(record)
                elif 'url' in ch:
                    records.append(ch)
            else:
                # 对象形式
                if hasattr(ch, 'urls') and ch.urls:
                    for url in ch.urls:
                        records.append({
                            "name": ch.name,
                            "url": url,
                            "group_title": getattr(ch, 'group_title', ''),
                            "id": getattr(ch, 'tvg_id', ''),
                            "logo": getattr(ch, 'tvg_logo', ''),
                            "latency": getattr(ch, 'latency', 9999),
                            "video_codec": getattr(ch, 'video_codec', ''),
                            "ip_info": getattr(ch, 'ip_info', None)
                        })
                elif hasattr(ch, 'url'):
                    records.append({
                        "name": ch.name,
                        "url": ch.url,
                        "group_title": getattr(ch, 'group_title', ''),
                        "id": getattr(ch, 'tvg_id', ''),
                        "logo": getattr(ch, 'tvg_logo', ''),
                        "latency": getattr(ch, 'latency', 9999),
                        "video_codec": getattr(ch, 'video_codec', ''),
                        "ip_info": getattr(ch, 'ip_info', None)
                    })
        if records:
            self.db.save_channels(records)
            self.db.set_last_update_time()
            print(f"💾 已保存 {len(records)} 条记录（来自 {len(channels)} 个合并频道）到缓存")
        else:
            print("⚠️ 没有可保存的记录")

    def get_cache_age(self) -> int:
        last_update = self.db.get_last_update_time()
        if last_update is None:
            return 0
        elapsed = int(time.time()) - last_update
        return max(0, DATA_EXPIRY_SECONDS - elapsed)
