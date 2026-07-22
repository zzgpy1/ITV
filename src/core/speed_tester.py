# src/core/speed_tester.py
import asyncio
import aiohttp
import time
from typing import List, Dict, Tuple
from tqdm.asyncio import tqdm
from src.settings import settings
from src.repositories import repo_factory
from src.logger import logger
import hashlib

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def channel_key(name: str, url: str) -> str:
    return hashlib.md5(f"{name}|{url}".encode()).hexdigest()

# 国内频道关键词过滤（用于测速前预过滤）
DOMESTIC_KEYWORDS = [
    "cctv", "央视", "中央", "cgtn",
    "卫视", "东方卫视", "北京卫视", "湖南卫视", "浙江卫视", "江苏卫视",
    "广东卫视", "深圳卫视", "天津卫视", "山东卫视", "安徽卫视",
    "湖北卫视", "黑龙江卫视", "江西卫视", "河南卫视", "河北卫视",
    "山西卫视", "陕西卫视", "甘肃卫视", "宁夏卫视", "青海卫视",
    "云南卫视", "贵州卫视", "广西卫视", "内蒙古卫视", "新疆卫视",
    "西藏卫视", "海南卫视", "东南卫视", "重庆卫视", "四川卫视",
    "辽宁卫视", "吉林卫视", "厦门卫视", "大湾区卫视", "海峡卫视",
    "电视台", "综合频道", "新闻频道", "都市频道", "生活频道",
    "影视", "少儿", "公共", "经济", "科教", "文艺", "体育",
    "北京", "上海", "广东", "浙江", "江苏", "湖南", "湖北",
    "山东", "河南", "四川", "福建", "安徽", "辽宁", "陕西",
    "河北", "江西", "黑龙江", "吉林", "山西", "云南", "贵州",
    "甘肃", "海南", "青海", "宁夏", "新疆", "西藏", "广西",
    "内蒙古", "香港", "澳门", "台湾",
    "凤凰", "翡翠", "明珠", "TVB", "无线", "RTHK", "HOY",
    "东森", "民视", "台视", "华视", "中视", "三立", "纬来"
]

def is_domestic_channel(name: str) -> bool:
    """判断是否为国内频道（央视/卫视/地方/港澳台）"""
    name_lower = name.lower()
    for kw in DOMESTIC_KEYWORDS:
        if kw in name_lower:
            return True
    return False

class SpeedTester:
    def __init__(self):
        self.candidate_repo = None
        self.history_repo = None
        self.cache_repo = None

    async def _ensure_repos(self):
        if self.candidate_repo is None:
            self.candidate_repo = repo_factory.candidate
            self.history_repo = repo_factory.history
            self.cache_repo = repo_factory.cache

    async def test_batch(self, channels: List[Dict]) -> List[Dict]:
        """测速并返回有效频道列表，同时更新候选池和缓存"""
        await self._ensure_repos()
        
        # 预过滤：只测速国内频道（大幅减少测速量）
        domestic = [ch for ch in channels if is_domestic_channel(ch["name"])]
        if len(domestic) < len(channels):
            logger.info(f"📊 测速前过滤: {len(channels)} -> {len(domestic)} 个国内频道")

        semaphore = asyncio.Semaphore(settings.max_workers)
        connector = aiohttp.TCPConnector(limit=settings.max_workers, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=settings.http_timeout + 5)

        valid = []
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [self._test_one(session, ch, semaphore) for ch in domestic]
            pbar = tqdm(total=len(tasks), desc="🚀 测速")
            for coro in asyncio.as_completed(tasks):
                result = await coro
                pbar.update(1)
                if result:
                    valid.append(result)
            pbar.close()
        logger.info(f"✅ 测速完成: 有效 {len(valid)}/{len(domestic)} 个国内频道")
        return valid

    async def _test_one(self, session: aiohttp.ClientSession, channel: Dict, semaphore: asyncio.Semaphore):
        async with semaphore:
            name = channel["name"]
            url = channel["url"]
            key = channel_key(name, url)

            # 检查缓存
            cached = await self.cache_repo.get(key, "speed")
            if cached:
                import json
                data = json.loads(cached)
                if data.get("latency", 9999) < settings.slow_speed_threshold:
                    channel["latency"] = data["latency"]
                    channel["video_codec"] = data.get("video_codec", "")
                    return channel

            # 执行测速
            ok, latency, video_codec = await self._probe(session, url)
            if ok and latency < settings.slow_speed_threshold:
                channel["latency"] = latency
                channel["video_codec"] = video_codec
                # 更新候选池和缓存
                await self.candidate_repo.update_latency(key, latency, True)
                await self.history_repo.add(key, url, latency, True)
                await self.cache_repo.set(key, f'{{"latency": {latency}, "video_codec": "{video_codec}"}}', "speed", settings.cache_speed_hours)
                return channel
            else:
                await self.candidate_repo.update_latency(key, latency, False)
                await self.history_repo.add(key, url, latency, False)
                return None

    async def _probe(self, session: aiohttp.ClientSession, url: str) -> Tuple[bool, int, str]:
        try:
            start = time.time()
            async with session.head(url, timeout=5, allow_redirects=True, headers=HEADERS) as resp:
                if resp.status != 200:
                    return False, 0, ""
            head_latency = int((time.time() - start) * 1000)

            start_dl = time.time()
            async with session.get(url, timeout=settings.http_timeout, headers={**HEADERS, "Range": f"bytes=0-{settings.download_chunk_size-1}"}) as resp:
                if resp.status not in (200, 206):
                    return False, head_latency, ""
                data = await resp.content.read(settings.download_chunk_size)
                if not data:
                    return False, head_latency, ""
            dl_time = time.time() - start_dl
            total_latency = head_latency + int(dl_time * 1000)

            if data.startswith(b'#EXTM3U') or b'#EXTINF' in data:
                is_valid = True
                codec = "h264"
            elif any(data.startswith(sig) for sig in [b'\x00\x00\x00\x18ftyp', b'\x00\x00\x00\x1cftyp', b'\x1a\x45\xdf\xa3', b'\x47\x40\x00', b'FLV']):
                is_valid = True
                codec = "h264"
            else:
                is_valid = False
                codec = ""

            if is_valid and total_latency < settings.slow_speed_threshold:
                return True, total_latency, codec
            else:
                return False, total_latency, codec
        except Exception as e:
            logger.debug(f"测速失败 {url}: {e}")
            return False, 0, ""
