import asyncio
import copy
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple
from src.config_loader import config
from src.logger import logger
from src.generator import generate_m3u, generate_txt, generate_multi_m3u
from src.demo_filter import parse_demo_order_with_categories
from src.merger import merge_channels_by_name

class ResultAggregator:
    """
    实时写入聚合器：测速过程中持续更新输出文件
    """
    def __init__(self, base_channels: List[dict], output_dir: Path):
        self.base_channels = base_channels  # 初始频道列表（未测速）
        self.output_dir = output_dir
        self.channel_results = defaultdict(lambda: defaultdict(list))  # {category: {name: [items]}}
        self._dirty = False
        self._flush_interval = 2.0  # 秒
        self._last_flush = 0
        self._lock = asyncio.Lock()
        self._demo_order = parse_demo_order_with_categories() if config.enable_demo_filter else []
        self._category_order = [cat for cat, _ in self._demo_order] if self._demo_order else ['央视','卫视','地方','港澳台']

    async def add_item(self, category: str, name: str, channel: dict, is_channel_last: bool = False, is_last: bool = False):
        """
        添加一条测速结果
        """
        async with self._lock:
            self.channel_results[category][name].append(channel)
            self._dirty = True
            # 如果是频道最后一个结果，或整体最后，立即刷新
            if is_channel_last or is_last:
                await self._flush()
            else:
                # 否则按间隔刷新
                now = time.time()
                if now - self._last_flush > self._flush_interval:
                    await self._flush()

    async def _flush(self):
        if not self._dirty:
            return
        try:
            # 构建最终输出数据：合并 base_channels（未测速的）和 已测速的结果
            # 由于 base_channels 可能很大，我们按 category 合并
            # 简化：每次重新生成所有频道的最终列表，用已测速的覆盖同名频道
            merged_dict = {}  # category -> {name: [urls, latency, ...]}
            # 先加载 base_channels（未测速）
            for ch in self.base_channels:
                cat = ch.get('demo_category', ch.get('group_title', '其他'))
                name = ch['name']
                merged_dict.setdefault(cat, {}).setdefault(name, []).append(ch)
            # 覆盖已测速的结果
            for cat, names in self.channel_results.items():
                for name, items in names.items():
                    if items:
                        # 取最优（延迟最低）的作为主源，保留所有备源
                        sorted_items = sorted(items, key=lambda x: x.get('latency', 9999))
                        best = sorted_items[0]
                        merged_dict.setdefault(cat, {}).setdefault(name, []).append(best)
                        # 可添加更多备源（根据 max_sources_per_channel）
                        for i in range(1, min(len(sorted_items), config.max_sources_per_channel)):
                            merged_dict[cat][name].append(sorted_items[i])
            # 转换为列表
            merged_channels = []
            for cat, names in merged_dict.items():
                for name, chs in names.items():
                    for ch in chs:
                        ch['demo_category'] = cat
                        ch['demo_name'] = name
                        merged_channels.append(ch)
            # 生成输出
            if merged_channels:
                output_dir = self.output_dir
                output_dir.mkdir(parents=True, exist_ok=True)
                generate_m3u(merged_channels, self._category_order, output_dir / "tv.m3u")
                generate_txt(merged_channels, self._category_order, output_dir / "tv.txt")
                generate_multi_m3u(merged_channels, self._category_order, output_dir / "tv_multi.m3u")
                logger.info(f"🔄 实时刷新输出：{len(merged_channels)} 个频道已更新")
        except Exception as e:
            logger.error(f"❌ 实时写入失败: {e}")
        finally:
            self._dirty = False
            self._last_flush = time.time()

    async def finalize(self):
        """最终刷新，确保所有数据写入"""
        await self._flush()
