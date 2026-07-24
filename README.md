# IPTV 智能整理平台

全自动 IPTV 直播源采集、测速、验证、分类、合并与自治管理平台。

## 功能特性

- 多源聚合 – 同时拉取多个公开 IPTV 源，自动解析 M3U / TXT 格式
- 双重测速 – HTTP 快速探测 + ffmpeg 深度验证
- 智能分类 – 按央视、卫视、地方（省份）、港澳台自动归类
- 固定源保护 – 用户可预设优质源，系统永不自动替换
- 自治模式 – 源池 → 候选观察 → 稳定提升 → 质量监控
- 多格式输出 – tv.m3u、tv.txt、tv_multi.m3u、channels.json

## 快速开始

### 使用 Docker

```bash
docker-compose up -d
