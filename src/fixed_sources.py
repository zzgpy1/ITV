# src/fixed_sources.py
"""固定优质源配置 - 优先级最高，跳过测速直接使用"""

# 固定央视频道源（用户提供），每个频道可以指定多个备选源
CCTV_FIXED_SOURCES = {
    "CCTV-1": [
         "http://69.30.245.50/live/cctv1.m3u8"
    ],
    "CCTV-2": [
         "http://69.30.245.50/live/cctv2.m3u8"
    ],
    "CCTV-3": [
         "http://69.30.245.50/live/cctv3.m3u8"
    ],
    "CCTV-4": [
         "http://69.30.245.50/live/cctv4.m3u8"
    ],
    "CCTV-5": [
         "http://69.30.245.50/live/cctv5.m3u8"
    ],
    "CCTV-5+": [
        "http://45.192.97.170:8880/play/6.m3u8"
        # 新源可能没有 cctv5+ 对应，暂不添加
    ],
    "CCTV-6": [
        "http://69.30.245.50/live/cctv6.m3u8"
    ],
    "CCTV-7": [
        "http://69.30.245.50/live/cctv7.m3u8"
    ],
    "CCTV-8": [
        "http://69.30.245.50/live/cctv8.m3u8"
    ],
    "CCTV-9": [
         "http://69.30.245.50/live/cctv9.m3u8"
    ],
    "CCTV-10": [
         "http://69.30.245.50/live/cctv10.m3u8"
    ],
    "CCTV-11": ["http://45.192.97.170:8880/play/12.m3u8"],
    "CCTV-12": ["http://45.192.97.170:8880/play/13.m3u8"],
    "CCTV-13": ["http://45.192.97.170:8880/play/14.m3u8"],
    "CCTV-14": ["http://45.192.97.170:8880/play/15.m3u8"],
    "CCTV-15": ["http://45.192.97.170:8880/play/16.m3u8"],
    "CCTV-16": [],
    "CCTV-17": ["http://45.192.97.170:8880/play/17.m3u8"],
    "CCTV-4K": [],
    "CCTV-8K": [],
}

# 是否启用固定源（优先级最高）
ENABLE_FIXED_SOURCES = True

# 固定源的质量评分（极低延迟，确保被优先选择）
FIXED_SOURCE_LATENCY = 50  # 50ms 极低延迟

# 固定源的编码格式
FIXED_SOURCE_CODEC = "h264"
