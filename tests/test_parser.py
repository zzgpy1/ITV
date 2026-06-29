# tests/test_parser.py
import pytest
from src.parser import parse_m3u, parse_txt

def test_parse_m3u_basic():
    content = """#EXTM3U
#EXTINF:-1 group-title="央视",CCTV-1
http://example.com/1.m3u8
#EXTINF:-1 group-title="卫视",CCTV-2
http://example.com/2.m3u8
"""
    channels = parse_m3u(content)
    assert len(channels) == 2
    assert channels[0]['name'] == 'CCTV-1'
    assert channels[0]['url'] == 'http://example.com/1.m3u8'
    assert channels[0]['group_title'] == '央视'

def test_parse_txt_basic():
    content = """#央视
http://example.com/1.m3u8
#卫视
http://example.com/2.m3u8
"""
    channels = parse_txt(content)
    assert len(channels) == 2
    assert channels[0]['name'] == '央视'
    assert channels[0]['url'] == 'http://example.com/1.m3u8'

def test_parse_m3u_no_group_title():
    content = """#EXTM3U
#EXTINF:-1,CCTV-1
http://example.com/1.m3u8
"""
    channels = parse_m3u(content)
    assert channels[0]['group_title'] == '港澳台日'  # 默认推断

def test_parse_txt_no_channel_name():
    content = """http://example.com/1.m3u8
"""
    channels = parse_txt(content)
    assert channels[0]['name'] == '未知频道'
    assert channels[0]['url'] == 'http://example.com/1.m3u8'
