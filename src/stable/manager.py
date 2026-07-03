# src/stable/manager.py
"""稳定版管理器 - 管理最终使用的稳定源"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.logger import logger
from src.config import OUTPUT_DIR, ENABLE_FIXED_OPTIMIZATION, FIXED_OPTIMIZATION_THRESHOLD
from src.stable.models import StableSource, StableStatus


class StableManager:
    """稳定版管理器"""
    
    STABLE_FILE = OUTPUT_DIR / "stable_sources.json"
    
    def __init__(self):
        self.stable_sources: Dict[str, StableSource] = {}
        self._load()
        self._sync_fixed_sources()   # 每次启动时同步固定源配置
    
    def _load(self):
        """加载稳定源配置"""
        if self.STABLE_FILE.exists():
            try:
                with open(self.STABLE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, src in data.items():
                        self.stable_sources[name] = StableSource.from_dict(src)
                logger.info(f"✅ 加载 {len(self.stable_sources)} 个稳定源")
            except Exception as e:
                logger.warning(f"加载稳定源失败: {e}")
    
    def _save(self):
        """保存稳定源配置"""
        try:
            data = {name: src.to_dict() for name, src in self.stable_sources.items()}
            with open(self.STABLE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存稳定源失败: {e}")
    
    def _sync_fixed_sources(self):
        """从 fixed_sources.py 同步固定源配置，删除配置中不存在的固定源"""
        try:
            from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES
            if not ENABLE_FIXED_SOURCES:
                return
            # 获取当前所有固定源的名称
            current_fixed_names = set()
            for name, src in self.stable_sources.items():
                if src.is_fixed:
                    current_fixed_names.add(name)
            # 配置中的固定源名称
            config_fixed_names = set(CCTV_FIXED_SOURCES.keys())
            # 1. 添加或更新配置中的固定源
            for name, url in CCTV_FIXED_SOURCES.items():
                if not url:
                    continue
                # 如果 url 是列表，取第一个
                if isinstance(url, list):
                    url = url[0] if url else None
                if not url:
                    continue
                if name in self.stable_sources:
                    src = self.stable_sources[name]
                    if src.url != url:
                        src.url = url
                        src.is_fixed = True
                        src.auto_optimize = True
                        src.promoted_at = datetime.now()
                        logger.info(f"📌 更新固定源: {name} -> {url}")
                else:
                    self.set_fixed_source(name, url, auto_optimize=True)
                    logger.info(f"📌 添加固定源: {name} -> {url}")
            # 2. 移除不再在配置中的固定源（降级为普通稳定源）
            for name in current_fixed_names:
                if name not in config_fixed_names:
                    src = self.stable_sources.get(name)
                    if src and src.is_fixed:
                        src.is_fixed = False
                        src.auto_optimize = True
                        logger.info(f"📌 固定源已移除固定标记: {name}（不再在配置中）")
            self._save()
        except ImportError:
            logger.warning("⚠️ fixed_sources.py 不存在，跳过固定源同步")
        except Exception as e:
            logger.warning(f"⚠️ 固定源同步失败: {e}")
    
    def sync_fixed_sources(self):
        """公共方法，供外部调用以手动同步固定源"""
        self._sync_fixed_sources()
    
    def promote_candidate(self, channel_name: str, url: str, latency: int, video_codec: str) -> bool:
        """将候选源提升为稳定源"""
        current = self.stable_sources.get(channel_name)
        if current and current.is_fixed:
            logger.warning(f"⚠️ {channel_name} 是固定源，不允许自动替换")
            return False
        if current and current.url == url:
            logger.debug(f"{channel_name} URL 未变化，跳过更新")
            return False
        self.stable_sources[channel_name] = StableSource(
            channel_name=channel_name,
            url=url,
            latency=latency,
            video_codec=video_codec,
            promoted_at=datetime.now(),
            is_fixed=False,
            auto_optimize=False,
            status=StableStatus.ACTIVE
        )
        self._save()
        logger.info(f"✅ {channel_name} 已提升为稳定源: {url[:80]}...")
        return True
    
    def set_fixed_source(self, channel_name: str, url: str, auto_optimize: bool = True) -> bool:
        """
        设置固定源（用户明确保留，不会被自动替换）
        auto_optimize: 是否允许自动优化（默认 True，即允许系统在找到更优源时替换）
        """
        if not url:
            return False
        self.stable_sources[channel_name] = StableSource(
            channel_name=channel_name,
            url=url,
            latency=0,
            video_codec="",
            promoted_at=datetime.now(),
            is_fixed=True,
            auto_optimize=auto_optimize,
            status=StableStatus.ACTIVE
        )
        self._save()
        logger.info(f"📌 {channel_name} 已设为固定源 (自动优化: {auto_optimize})")
        return True

    def optimize_fixed_sources(self, all_sources_by_channel: Dict[str, List[Dict]], 
                               candidate_observer=None) -> int:
        """
        对固定源进行动态优化，选择当前延迟最低的源作为固定源。
        all_sources_by_channel: {channel_name: [{'url': str, 'latency': int, 'success_count': int, 'fail_count': int}, ...]}
        candidate_observer: 可选，用于将被替换的旧源加入候选池
        返回被替换的固定源数量
        """
        if not ENABLE_FIXED_OPTIMIZATION:
            return 0

        fixed_sources = {name: src for name, src in self.stable_sources.items() if src.is_fixed}
        if not fixed_sources:
            return 0

        optimized_count = 0

        for channel_name, current_src in fixed_sources.items():
            if not current_src.auto_optimize:
                continue

            candidates = all_sources_by_channel.get(channel_name, [])
            if not candidates:
                continue

            # 过滤掉无效数据
            valid_candidates = []
            for c in candidates:
                lat = c.get('latency', 0)
                if lat <= 0:
                    continue
                # 要求至少成功 2 次，失败不超过 3 次
                if c.get('success_count', 0) < 2:
                    continue
                if c.get('fail_count', 0) > 3:
                    continue
                valid_candidates.append(c)

            if not valid_candidates:
                continue

            # 按延迟排序，选最低的
            best = min(valid_candidates, key=lambda x: x['latency'])

            # 如果最佳源就是当前固定源，跳过
            if best['url'] == current_src.url:
                continue

            # 检查延迟改进是否显著（差值大于阈值）
            improvement = current_src.latency - best['latency']
            if improvement <= FIXED_OPTIMIZATION_THRESHOLD:
                continue

            # 执行替换
            old_url = current_src.url
            new_url = best['url']
            new_latency = best['latency']

            logger.info(f"🔄 固定源优化: {channel_name} 延迟 {current_src.latency}ms -> {new_latency}ms (改进 {improvement}ms)")
            # 替换
            self.replace_source(channel_name, new_url, new_latency, best.get('video_codec', ''))
            optimized_count += 1

            # 将旧源加入候选池（如果提供了observer）
            if candidate_observer:
                from src.database import channel_key
                old_key = channel_key(channel_name, old_url)
                candidate_observer.add_candidate(old_key, channel_name, old_url)
                logger.debug(f"📥 旧源已加入候选池: {old_url[:50]}...")

        return optimized_count
    
    def set_auto_optimize(self, channel_name: str, enabled: bool) -> bool:
        """切换固定源的自动优化开关"""
        if channel_name not in self.stable_sources:
            return False
        src = self.stable_sources[channel_name]
        if not src.is_fixed:
            return False
        src.auto_optimize = enabled
        self._save()
        logger.info(f"🔄 {channel_name} 自动优化开关: {enabled}")
        return True
    
    def get_stable_sources(self) -> Dict[str, StableSource]:
        return self.stable_sources
    
    def get_active_sources(self) -> Dict[str, StableSource]:
        return {n: s for n, s in self.stable_sources.items() if s.status == StableStatus.ACTIVE and s.url}
    
    def get_output_channels(self) -> List[dict]:
        channels = []
        for name, src in self.stable_sources.items():
            if src.status == StableStatus.ACTIVE and src.url:
                channels.append({
                    "name": name,
                    "url": src.url,
                    "latency": src.latency,
                    "video_codec": src.video_codec,
                    "is_fixed": src.is_fixed,
                    "auto_optimize": src.auto_optimize
                })
        return channels
    
    def record_failure(self, channel_name: str):
        if channel_name in self.stable_sources:
            src = self.stable_sources[channel_name]
            src.fail_count += 1
            src.last_verified = datetime.now()
            if src.fail_count >= 3 and not src.is_fixed:
                src.status = StableStatus.DEGRADED
                logger.warning(f"⚠️ {channel_name} 质量下降，已标记为 DEGRADED")
            self._save()
    
    def record_success(self, channel_name: str):
        if channel_name in self.stable_sources:
            src = self.stable_sources[channel_name]
            src.fail_count = 0
            src.last_verified = datetime.now()
            if src.status == StableStatus.DEGRADED:
                src.status = StableStatus.ACTIVE
                logger.info(f"✅ {channel_name} 已恢复活跃")
            self._save()
    
    def replace_source(self, channel_name: str, new_url: str, latency: int, video_codec: str) -> bool:
        """替换失效源（保留原有的 is_fixed 和 auto_optimize）"""
        current = self.stable_sources.get(channel_name)
        # 如果是固定源且不允许自动优化，则拒绝替换
        if current and current.is_fixed and not current.auto_optimize:
            logger.warning(f"⚠️ {channel_name} 是固定源且不允许自动优化，拒绝替换")
            return False
        old_url = current.url if current else "None"
        # 保留原有的固定标记和自动优化开关
        is_fixed = current.is_fixed if current else False
        auto_optimize = current.auto_optimize if current else False
        self.stable_sources[channel_name] = StableSource(
            channel_name=channel_name,
            url=new_url,
            latency=latency,
            video_codec=video_codec,
            promoted_at=datetime.now(),
            is_fixed=is_fixed,
            auto_optimize=auto_optimize,
            status=StableStatus.ACTIVE
        )
        self._save()
        logger.info(f"🔄 {channel_name} 已替换: {old_url[:50]}... -> {new_url[:50]}...")
        return True
