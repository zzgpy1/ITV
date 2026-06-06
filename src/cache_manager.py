#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV 频道缓存管理器（增量更新版）
"""

import time
from src.db_manager import IPTVDatabase, DATA_VALID_SECONDS, DATA_EXPIRY_SECONDS

class CacheManager:
    def __init__(self):
        self.db = IPTVDatabase()
        self._print_stats()

    def _print_stats(self):
        stats = self.db.get_stats()
        print(f"📊 数据库统计: 总计={stats['total']}, 活跃={stats['active']}, 失效={stats['inactive']}, 近期有效={stats['recent']}")
        print(f"📅 数据有效期: {stats['valid_days']}天, 全量更新阈值: {stats['expiry_days']}天")

    def should_full_update(self) -> bool:
        """判断是否需要全量采集（所有数据已超过 expiry_days 天未验证）"""
        if self.db.is_expired():
            print(f"⏰ 所有活跃数据已超过 {DATA_EXPIRY_SECONDS // 86400} 天，执行全量更新")
            return True
        print(f"✅ 缓存数据有效，执行增量更新（只验证过期数据）")
        return False

    def load_active_channels(self) -> list:
        """加载当前有效的频道（只返回最近 valid_days 天内验证成功的）"""
        channels = self.db.load_active_channels()
        print(f"📂 从缓存加载了 {len(channels)} 个有效频道")
        return channels

    def save_to_cache(self, channels: list, verified: bool = True):
        """保存频道到缓存（增量更新）"""
        records = []
        for ch in channels:
            if isinstance(ch, dict):
                if 'urls' in ch and isinstance(ch['urls'], list):
                    for url in ch['urls']:
                        records.append({
                            "name": ch.get("name", ""),
                            "url": url,
                            "group_title": ch.get("group_title", ""),
                            "id": ch.get("id", ""),
                            "logo": ch.get("logo", ""),
                            "latency": ch.get("latency", 9999),
                            "video_codec": ch.get("video_codec", ""),
                            "ip_info": ch.get("ip_info")
                        })
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
            self.db.batch_upsert(records, verified)
            self.db.set_last_update_time()
            print(f"💾 增量更新完成：处理 {len(records)} 条记录")

    def update_failed(self, channel) -> None:
        """标记单个频道验证失败（用于增量验证时）"""
        if hasattr(channel, 'url'):
            self.db.upsert_channel({"name": channel.name, "url": channel.url}, verified=False)
        elif isinstance(channel, dict) and 'url' in channel:
            self.db.upsert_channel(channel, verified=False)
