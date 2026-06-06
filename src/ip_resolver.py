# src/ip_resolver.py
# IP 归属地和运营商解析模块（基于纯真 IP 数据库）

import socket
import re
from urllib.parse import urlparse
from typing import Optional, Tuple
from pathlib import Path
from src.config import IP_DATABASE_FILE
from src.logger import logger

try:
    from qqwry import QQwry
    QQWRY_AVAILABLE = True
except ImportError:
    QQWRY_AVAILABLE = False
    logger.warning("⚠️ qqwry-py3 未安装，IP 归属地解析功能将不可用")

class IPResolver:
    _instance = None
    _qqwry = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_resolver()
        return cls._instance
    
    def _init_resolver(self):
        self._loaded = False
        if not QQWRY_AVAILABLE:
            return
        if not IP_DATABASE_FILE.exists():
            logger.warning(f"⚠️ IP 数据库文件不存在: {IP_DATABASE_FILE}")
            return
        try:
            self._qqwry = QQwry()
            if self._qqwry.load_file(str(IP_DATABASE_FILE), loadindex=False):
                self._loaded = True
                version = self._qqwry.get_lastone()
                logger.info(f"✅ IP 数据库加载成功: {IP_DATABASE_FILE}, 版本: {version}")
            else:
                logger.warning(f"⚠️ IP 数据库加载失败: {IP_DATABASE_FILE}")
        except Exception as e:
            logger.warning(f"⚠️ IP 数据库加载异常: {e}")
    
    def extract_ip_from_url(self, url: str) -> Optional[str]:
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            if not hostname:
                return None
            ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
            if ip_pattern.match(hostname):
                return hostname
            try:
                ip = socket.gethostbyname(hostname)
                return ip
            except socket.gaierror:
                return None
        except Exception:
            return None
    
    def lookup(self, ip: str) -> Optional[Tuple[str, str]]:
        if not self._loaded or not self._qqwry:
            return None
        try:
            result = self._qqwry.lookup(ip)
            if result and len(result) >= 2:
                location = result[0].strip()
                isp = result[1].strip()
                return (location, isp)
            return None
        except Exception:
            return None
    
    def resolve_channel_ip(self, channel: dict) -> Optional[dict]:
        if not self._loaded:
            return None
        url = channel.get("url", "")
        if not url:
            return None
        ip = self.extract_ip_from_url(url)
        if not ip:
            return None
        result = self.lookup(ip)
        if not result:
            return None
        location, isp = result
        province, city = self._parse_location(location)
        return {
            "ip": ip,
            "location_raw": location,
            "province": province,
            "city": city,
            "isp": isp
        }
    
    def _parse_location(self, location: str) -> Tuple[str, str]:
        provinces = [
            "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
            "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
            "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "台湾",
            "内蒙古", "广西", "西藏", "宁夏", "新疆", "香港", "澳门"
        ]
        province = ""
        city = ""
        for p in provinces:
            if p in location:
                province = p
                remaining = location.split(p, 1)[-1]
                if remaining and remaining.startswith(("省", "市")):
                    remaining = remaining[1:]
                if remaining:
                    import re
                    city_match = re.match(r'^[^市,\s]+', remaining)
                    if city_match:
                        city = city_match.group()
                break
        if not province and location:
            province = location
        return province, city
    
    @property
    def is_available(self) -> bool:
        return self._loaded

_resolver = None

def get_resolver() -> IPResolver:
    global _resolver
    if _resolver is None:
        _resolver = IPResolver()
    return _resolver

def matches_region(channel_info: dict, preferred_locations: list, preferred_isps: list) -> bool:
    if not preferred_locations and not preferred_isps:
        return True
    province = channel_info.get("province", "")
    city = channel_info.get("city", "")
    isp = channel_info.get("isp", "")
    location_match = not preferred_locations or any(loc in province or loc in city for loc in preferred_locations)
    isp_match = not preferred_isps or any(i in isp for i in preferred_isps)
    return location_match and isp_match
