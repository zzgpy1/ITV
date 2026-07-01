# src/fixed_sources.py
"""固定优质源配置 - 优先级最高，跳过测速直接使用"""

# 固定央视频道源（用户提供），每个频道可以指定多个备选源（列表）
CCTV_FIXED_SOURCES = {
    "CCTV-1": [
        "http://69.30.245.50/live/cctv1.m3u8",
        "http://45.192.97.170:8880/play/1.m3u8",
        "http://112.27.235.94:8000/hls/1/index.m3u8",
        "http://112.46.85.60:8009/hls/501/index.m3u8",
        "http://182.150.23.74:808/hls/1/index.m3u8"
    ],
    "CCTV-2": [
        "http://69.30.245.50/live/cctv2.m3u8",
        "http://45.192.97.170:8880/play/2.m3u8",
        "http://112.27.235.94:8000/hls/2/index.m3u8",
        "http://182.150.23.74:808/hls/2/index.m3u8",
        "http://112.46.85.60:8009/hls/502/index.m3u8"
    ],
    "CCTV-3": [
        "http://69.30.245.50/live/cctv3.m3u8",
        "http://45.192.97.170:8880/play/3.m3u8",
        "http://112.27.235.94:8000/hls/3/index.m3u8",
        "http://182.150.23.74:808/hls/3/index.m3u8"
    ],
    "CCTV-4": [
        "http://69.30.245.50/live/cctv4.m3u8",
        "http://45.192.97.170:8880/play/4.m3u8",
        "http://112.27.235.94:8000/hls/4/index.m3u8",
        "http://182.150.23.74:808/hls/4/index.m3u8",
        "https://global.cgtn.cicc.media.caton.cloud/master/cgtn-america.m3u8"
    ],
    "CCTV-5": [
        "http://69.30.245.50/live/cctv5.m3u8",
        "http://45.192.97.170:8880/play/5.m3u8",
        "http://112.27.235.94:8000/hls/5/index.m3u8",
        "http://182.150.23.74:808/hls/5/index.m3u8",
        "http://222.169.85.8:9901/tsfile/live/0005_1.m3u8"
    ],
    "CCTV-5+": [
        "http://45.192.97.170:8880/play/6.m3u8",
        "http://112.27.235.94:8000/hls/6/index.m3u8",
        "http://cssbyd.imwork.net:8082/hls/6/index.m3u8",
        "http://182.150.23.74:808/hls/16/index.m3u8"
    ],
    "CCTV-6": [
        "http://69.30.245.50/live/cctv6.m3u8",
        "http://45.192.97.170:8880/play/7.m3u8",
        "http://112.27.235.94:8000/hls/7/index.m3u8",
        "http://182.150.23.74:808/hls/6/index.m3u8",
        "http://222.169.85.8:9901/tsfile/live/0006_1.m3u8"
    ],
    "CCTV-7": [
        "http://69.30.245.50/live/cctv7.m3u8",
        "http://45.192.97.170:8880/play/8.m3u8",
        "http://112.27.235.94:8000/hls/8/index.m3u8",
        "http://182.150.23.74:808/hls/7/index.m3u8",
        "http://112.46.85.60:8009/hls/504/index.m3u8"
    ],
    "CCTV-8": [
        "http://69.30.245.50/live/cctv8.m3u8",
        "http://45.192.97.170:8880/play/9.m3u8",
        "http://112.27.235.94:8000/hls/9/index.m3u8",
        "http://182.150.23.74:808/hls/8/index.m3u8",
        "http://222.169.85.8:9901/tsfile/live/0008_1.m3u8"
    ],
    "CCTV-9": [
        "http://69.30.245.50/live/cctv9.m3u8",
        "http://45.192.97.170:8880/play/10.m3u8",
        "http://112.27.235.94:8000/hls/10/index.m3u8",
        "http://182.150.23.74:808/hls/9/index.m3u8",
        "http://222.169.85.8:9901/tsfile/live/0009_1.m3u8"
    ],
    "CCTV-10": [
        "http://69.30.245.50/live/cctv10.m3u8",
        "http://45.192.97.170:8880/play/11.m3u8",
        "http://182.150.23.74:808/hls/10/index.m3u8"
    ],
    "CCTV-11": [
        "http://45.192.97.170:8880/play/12.m3u8",
        "http://182.150.23.74:808/hls/11/index.m3u8",
        "http://112.27.235.94:8000/hls/12/index.m3u8"
    ],
    "CCTV-12": [
        "http://45.192.97.170:8880/play/13.m3u8",
        "http://182.150.23.74:808/hls/12/index.m3u8"
    ],
    "CCTV-13": [
        "http://45.192.97.170:8880/play/14.m3u8",
        "http://ali-m-l.cztv.com/channels/lantian/channel21/1080p.m3u8",
        "http://182.150.23.74:808/hls/3/index.m3u8"
    ],
    "CCTV-14": [
        "http://45.192.97.170:8880/play/15.m3u8",
        "http://182.150.23.74:808/hls/14/index.m3u8"
    ],
    "CCTV-15": [
        "http://45.192.97.170:8880/play/16.m3u8",
        "http://182.150.23.74:808/hls/15/index.m3u8",
        "http://112.27.235.94:8000/hls/16/index.m3u8"
    ],
    "CCTV-16": [
        "http://183.11.239.36:808/hls/169/index.m3u8"
    ],
    "CCTV-17": [
        "http://45.192.97.170:8880/play/17.m3u8",
        "http://222.169.85.8:9901/tsfile/live/0007_1.m3u8"
    ],
    "CCTV4欧洲": ["http://45.192.97.170:8880/play/18.m3u8"],
    "CCTV4美洲": ["http://45.192.97.170:8880/play/19.m3u8"],
    "CCTV-4K": [],
    "CCTV-8K": [],
}

# 是否启用固定源（优先级最高）
ENABLE_FIXED_SOURCES = True

# 固定源的质量评分（极低延迟，确保被优先选择）
FIXED_SOURCE_LATENCY = 50  # 50ms 极低延迟

# 固定源的编码格式
FIXED_SOURCE_CODEC = "h264"
