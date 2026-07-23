# src/logo_matcher.py
import re
from typing import Dict, Optional
from src.logger import logger


class LogoMatcher:
    LOGO_CDN = "https://epg.112114.xyz/logo/"
    LOGO_CDN_BACKUP = "https://raw.githubusercontent.com/iptv-org/iptv/master/resources/"

    CCTV_LOGO_MAP = {
        "CCTV-1": "cctv1.png", "CCTV-2": "cctv2.png", "CCTV-3": "cctv3.png",
        "CCTV-4": "cctv4.png", "CCTV-5": "cctv5.png", "CCTV-5+": "cctv5plus.png",
        "CCTV-6": "cctv6.png", "CCTV-7": "cctv7.png", "CCTV-8": "cctv8.png",
        "CCTV-9": "cctv9.png", "CCTV-10": "cctv10.png", "CCTV-11": "cctv11.png",
        "CCTV-12": "cctv12.png", "CCTV-13": "cctv13.png", "CCTV-14": "cctv14.png",
        "CCTV-15": "cctv15.png", "CCTV-16": "cctv16.png", "CCTV-17": "cctv17.png",
        "CCTV-4K": "cctv4k.png", "CCTV-8K": "cctv8k.png",
        "CGTN": "cgtn.png", "CGTN俄语": "cgtn_russian.png",
        "CGTN法语": "cgtn_french.png", "CGTN西语": "cgtn_spanish.png",
        "CGTN阿语": "cgtn_arabic.png", "CGTN纪录": "cgtn_documentary.png",
    }

    SATELLITE_LOGO_MAP = {
        "北京卫视": "beijing.png", "东方卫视": "dragon_tv.png",
        "湖南卫视": "hunan.png", "浙江卫视": "zhejiang.png",
        "江苏卫视": "jiangsu.png", "广东卫视": "guangdong.png",
        "深圳卫视": "shenzhen.png", "天津卫视": "tianjin.png",
        "山东卫视": "shandong.png", "安徽卫视": "anhui.png",
        "湖北卫视": "hubei.png", "黑龙江卫视": "heilongjiang.png",
        "江西卫视": "jiangxi.png", "河南卫视": "henan.png",
        "河北卫视": "hebei.png", "山西卫视": "shanxi.png",
        "陕西卫视": "shaanxi.png", "甘肃卫视": "gansu.png",
        "宁夏卫视": "ningxia.png", "青海卫视": "qinghai.png",
        "云南卫视": "yunnan.png", "贵州卫视": "guizhou.png",
        "广西卫视": "guangxi.png", "内蒙古卫视": "neimenggu.png",
        "新疆卫视": "xinjiang.png", "西藏卫视": "xizang.png",
        "海南卫视": "hainan.png", "东南卫视": "dnwei.png",
        "重庆卫视": "chongqing.png", "四川卫视": "sichuan.png",
        "辽宁卫视": "liaoning.png", "吉林卫视": "jilin.png",
        "厦门卫视": "xiamen.png", "大湾区卫视": "dawanqu.png",
        "海峡卫视": "haixia.png", "金鹰卡通": "eagle.png",
        "卡酷少儿": "kaku.png",
    }

    HK_TW_LOGO_MAP = {
        "翡翠台": "tvbjade.png", "明珠台": "tvbpearl.png",
        "凤凰中文": "phoenix.png", "凤凰资讯": "phoenix_info.png",
        "凤凰香港": "phoenix_hk.png", "TVB无线新闻": "tvbnews.png",
        "TVB星河": "tvbstar.png", "HOY TV": "hoytv.png",
        "东森综合": "ettvasia.png", "民视": "ftv.png",
        "台视": "ttv.png", "华视": "cts.png",
        "中视": "ctv.png", "三立台湾": "set_taiwan.png",
        "TVBS": "tvbs.png", "纬来体育": "wl_sports.png",
        "澳视澳门": "tdm.png",
    }

    def __init__(self):
        self.cache: Dict[str, str] = {}

    def get_logo_url(self, channel_name: str) -> str:
        if channel_name in self.cache:
            return self.cache[channel_name]

        if channel_name in self.CCTV_LOGO_MAP:
            url = self.LOGO_CDN + self.CCTV_LOGO_MAP[channel_name]
            self.cache[channel_name] = url
            return url

        if "cctv" in channel_name.lower() or "央视" in channel_name:
            logo = self._match_cctv_logo(channel_name)
            if logo:
                url = self.LOGO_CDN + logo
                self.cache[channel_name] = url
                return url

        for keyword, logo_file in self.SATELLITE_LOGO_MAP.items():
            if keyword in channel_name or channel_name in keyword:
                url = self.LOGO_CDN + logo_file
                self.cache[channel_name] = url
                return url

        for keyword, logo_file in self.HK_TW_LOGO_MAP.items():
            if keyword in channel_name or channel_name in keyword:
                url = self.LOGO_CDN + logo_file
                self.cache[channel_name] = url
                return url

        url = self.LOGO_CDN_BACKUP + channel_name + ".png"
        self.cache[channel_name] = url
        return url

    def _match_cctv_logo(self, name: str) -> Optional[str]:
        name_lower = name.lower()
        match = re.search(r'cctv[-\s]*(\d+)', name_lower)
        if match:
            num = match.group(1)
            if num in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17']:
                return f"cctv{num}.png"
            if num == '5plus' or '5+' in name_lower:
                return "cctv5plus.png"
        if '4k' in name_lower:
            return "cctv4k.png"
        if '8k' in name_lower:
            return "cctv8k.png"
        if 'cgtn' in name_lower:
            if '俄' in name:
                return "cgtn_russian.png"
            if '法' in name:
                return "cgtn_french.png"
            if '西' in name:
                return "cgtn_spanish.png"
            if '阿' in name:
                return "cgtn_arabic.png"
            if '纪录' in name:
                return "cgtn_documentary.png"
            return "cgtn.png"
        return None


_logo_matcher = None


def get_logo_matcher() -> LogoMatcher:
    global _logo_matcher
    if _logo_matcher is None:
        _logo_matcher = LogoMatcher()
    return _logo_matcher
