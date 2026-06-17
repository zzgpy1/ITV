# IPTV 智能整理平台

> 全自动 IPTV 源采集、测速、验证、分类与输出系统

[![GitHub Actions](https://img.shields.io/github/actions/workflow/status/zzgpy1/ITV/update_iptv.yml?branch=main&label=Auto%20Update)](https://github.com/zzgpy1/ITV/actions)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📖 项目简介

本项目是一个**全自动 IPTV 源采集、测速、验证、分类与输出系统**。它从多个公开源聚合 IPTV 播放链接，通过 HTTP 探测 + ffmpeg 深度验证过滤无效链接，并自动将频道归类到「央视、卫视、地方、港澳台」等分类，输出标准 M3U/TXT/JSON 格式播放列表。

**核心能力**：

- ✅ **多源聚合**：同时拉取 10+ 公开 IPTV 源，自动去重
- ✅ **双重验证**：HTTP 快速测速 + ffmpeg 深度验证（地理封锁/DRM/纯音频检测）
- ✅ **智能分类**：基于频道名、group-title 和拼音匹配自动归类
- ✅ **自治模式**：源池 → 候选版 → 稳定版 → 质量回路，系统自动维护可用源
- ✅ **固定源支持**：用户明确指定的源不被自动替换
- ✅ **多格式输出**：M3U / TXT / JSON / 多源切换版 / EPG兼容版 / 精简版
- ✅ **全自动化**：GitHub Actions 每 6 小时运行，缓存依赖大幅减少构建时间

---

## 🎯 功能特性

### 采集与验证
- 从 10+ 公开 IPTV 源并发拉取（支持 CDN 代理加速）
- 自动去重（基于频道名 + URL）
- HTTP 快速测速（HEAD + 少量数据验证）
- ffmpeg 深度验证（检测视频流、编码格式）

### 智能分类
- **央视**：CCTV-1 ~ CCTV-17、CCTV-4K/8K、CGTN 系列等
- **卫视**：全国各省卫视
- **地方**：按省份/城市自动归类（如「☘️浙江频道」）
- **港澳台**：统一归入「🌊港·澳·台」
- **特色分类**：韩国女团、戏曲频道、每日电影/经典电影、热门歌曲/动感舞曲、网络电台

### 自治模式（推荐）
- **源池**：自动发现新源，仅保留国内频道
- **候选版**：新源进入观察期，从缓存复用测速结果
- **稳定版**：验证通过的源自动提升为稳定源
- **质量回路**：持续监控稳定源质量，自动替换失效源
- **固定源保护**：用户指定的源不会被自动替换

### 输出格式
| 文件 | 说明 |
|------|------|
| `tv.m3u` | 标准 M3U 播放列表（按 demo.txt 顺序） |
| `tv.txt` | 标准 TXT 格式（频道名,URL） |
| `tv_multi.m3u` | 多源切换版（同一频道多个备源，用 `#` 分隔） |
| `tv_epg.m3u` | EPG 兼容版（保留 tvg-id 占位） |
| `tv_lite.m3u` | 精简版（仅保留最低延迟源，适合移动设备） |
| `channels.json` | JSON API 格式（供其他程序调用） |
| `shai.txt` | 未匹配频道列表（便于人工复核） |

### 性能优化
- **动态并发控制**：根据网络状况自适应调整并发数
- **连接池复用**：TCP 连接复用，减少握手开销
- **ffmpeg 缓存**：验证结果缓存 7 天，避免重复调用
- **分级验证**：HTTP 初筛 → ffmpeg 深度验证（减少 50-70% 调用）
- **轻量级模式**：支持 `quick`/`deep`/`off` 三种 ffmpeg 模式
- **预编译正则**：加速分类匹配
- **布隆过滤器**：高效去重，降低内存占用

---

## 🏗️ 架构概览
┌─────────────────────────────────────────────────────────────────┐
│ GitHub Actions │
│ (每 6 小时自动运行) │
└─────────────────────────┬───────────────────────────────────────┘
▼
┌─────────────────────────────────────────────────────────────────┐
│ IPTV 智能整理平台 │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ 多源采集 │ │ 候选版观察 │ │ 稳定版管理 │ │
│ │ (源池) │→ │ (验证) │→ │ (输出) │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ │
│ ↑ ↑ ↓ │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 质量回路 (持续监控) │ │
│ └─────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ 输出: tv.m3u / tv.txt / tv_multi.m3u / tv_epg.m3u / channels.json │
└─────────────────────────────────────────────────────────────────┘

---

## 🚀 部署方式

### 方式一：GitHub Actions（推荐）
1. **Fork 本仓库** 到你的 GitHub 账号
2. **启用 GitHub Actions**：仓库 → Actions → 允许工作流
3. **手动触发首次运行**：Actions → `IPTV 源智能更新与整理` → Run workflow
4. 等待约 10-20 分钟，访问以下地址获取播放列表：
   - `https://你的用户名.github.io/ITV/tv.m3u`
   - `https://你的用户名.github.io/ITV/tv.txt`

### 方式二：本地运行
```bash
# 克隆项目
git clone https://github.com/你的用户名/ITV.git
cd ITV

# 安装依赖
pip install -r requirements.txt

# 安装 ffmpeg (可选，深度验证需要)
# Ubuntu/Debian: sudo apt install ffmpeg
# macOS: brew install ffmpeg

# 运行（传统模式）
python -m src.run

# 运行（自治模式）
AUTONOMOUS_MODE=true python -m src.run
docker-compose up -d

⚙️ 配置说明
环境变量（.env）
变量	说明	默认值
AUTONOMOUS_MODE	启用自治模式	false
MAX_WORKERS	HTTP 并发数	20
TIMEOUT	HTTP 超时（秒）	8
FFMPEG_MODE	ffmpeg 模式 (deep/quick/off)	deep
FFPROBE_CACHE_HOURS	ffmpeg 结果缓存时长（小时）	168
CACHE_RAW_HOURS	原始源缓存时长（小时）	48
ENABLE_INCREMENTAL_FETCH	启用增量更新	true
DYNAMIC_CONCURRENCY	动态并发控制	true
ENABLE_BLOOM_FILTER	启用布隆过滤器去重	true

自定义源
编辑 src/config.py 中的 RAW_SOURCES 和 DIRECT_SOURCES 列表。

固定源
编辑 src/fixed_sources.py，添加你明确想保留的频道和 URL（如 CCTV-1 的稳定源）。
📂 输出文件说明
运行后，output/ 目录将包含：

tv.m3u — 标准 M3U

tv.txt — 标准 TXT

tv_multi.m3u — 多源切换版

tv_epg.m3u — EPG 兼容版

tv_lite.m3u — 精简版（移动端优化）

channels.json — JSON API

stats.json — 运行统计

shai.txt — 未匹配频道列表

🧩 依赖说明
Python 依赖
aiohttp>=3.9.0        # 异步 HTTP 请求
aiosqlite>=0.19.0     # SQLite 异步支持
tqdm>=4.66.0          # 进度条
pypinyin>=0.49.0      # 拼音匹配（可选）

系统依赖（可选）
ffmpeg：用于深度验证（推荐安装，可大幅提高过滤准确性）

❓ 常见问题
1. 为什么自治模式没有产生稳定源？
首次运行需要积累测速缓存，建议先运行几次传统模式后再启用自治模式。

2. 播放列表中的频道无法播放？
可能是源已失效，系统会在下次运行时自动替换（自治模式）或您可手动更新固定源。

3. 如何增加新的分类？
在 demo.txt 中添加新分类行（格式：分类名,#genre#），然后在该分类下列出频道名即可。

4. 港澳台频道如何归类？
所有香港、澳门、台湾频道会自动合并到 🌊港·澳·台 分类中（已在 demo_filter.py 中硬编码）。

5. 拼音匹配需要额外安装什么？
安装 pypinyin 即可：pip install pypinyin

6. 能否关闭 ffmpeg 深度验证？
设置 FFMPEG_MODE=off 或 FFMPEG_ENABLE=false。

📝 自定义 demo.txt 示例
📺央视频道,#genre#
CCTV-1
CCTV-2
CCTV-3
...

📡卫视频道,#genre#
广东卫视
浙江卫视
...

☘️北京频道,#genre#
北京卫视
北京科教
...

🌊港·澳·台,#genre#
翡翠台
明珠台
...

📜 免责声明
本项目仅用于个人学习和研究，所有节目源均来自互联网公开可访问链接，项目本身不存储、不修改任何媒体内容。严禁将本项目用于商业传播或非法用途。因违规使用产生的任何法律责任由使用者自行承担。

📄 许可证
MIT License © 2026

🎉 感谢使用 IPTV 智能整理平台！如果觉得有用，欢迎 Star ⭐
