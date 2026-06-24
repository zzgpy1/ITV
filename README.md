IPTV 智能整理平台 · 自治版

全自动 IPTV 直播源采集、测速、验证、分类、输出与自治管理平台

本项目是一个集多源采集、双重测速、智能分类、固定源保护、质量回滚于一体的 IPTV 源管理工具。通过 GitHub Actions 或 Docker 一键部署，实现从“被动维护”到“主动自治”的升级，让老人孩子都能稳定观看电视。

✨ 功能特点
功能模块	说明
🌐 多源聚合	同时拉取 10+ 公开 IPTV 源（GitHub、iptv-org、自定义），自动去重
⚡ 双重测速	HTTP 快速探测 + ffmpeg 深度验证（支持分级模式），过滤无效/卡顿源
🧠 智能分类	基于频道名和 group-title 自动归类：央视、卫视、地方（按省份）、港澳台
📌 固定源保护	用户指定的优质源（如 http://45.192.97.170:8880/play/1.m3u8）永不自动替换
🔄 自治模式	发现新源 → 候选池观察 → 稳定版提升 → 质量监控 → 失效自动回滚
📊 Web 管理面板	仪表盘、频道列表、固定源管理、配置编辑、质量趋势图表（暗色主题）
📦 多格式输出	tv.m3u、tv.txt、tv_multi.m3u（多源切换）、channels.json（API）
🐳 简单部署	Docker 一键运行，内置 HTTP 文件服务器 + Flask Web 界面
⏱️ 定时自动化	GitHub Actions 每 6 小时运行，缓存复用，增量更新

🏗️ 系统架构
系统分层	细分模块 / 源类型	说明
Web 管理界面 (Flask)	仪表盘	系统数据总览首页
Web 管理界面 (Flask)	频道列表	全部频道查询、编辑管理
Web 管理界面 (Flask)	固定源	用户自定义播放源管理入口
Web 管理界面 (Flask)	配置管理	系统参数、自动化策略配置
Web 管理界面 (Flask)	质量趋势	播放源长期质量可视化图表
自治模式（质量回路）	源池发现	自动采集、抓取全新播放源
自治模式（质量回路）	候选观察	新源灰度测试，持续稳定性监测
自治模式（质量回路）	稳定提升	测试达标候选源晋升稳定源
自治模式（质量回路）	质量回滚	源故障时自动切回可靠源
播放源分层	稳定版	家中电视正式输出使用
播放源分层	候选版	测试观察期，未完全验证
播放源分层	源池	新采集入库，等待质量检测
播放源分层	固定源	用户手动指定，永久保留不自动替换

🚀 快速开始
方式一：Docker 部署（推荐）
# 1. 克隆项目
git clone https://github.com/zzgpy1/ITV.git
cd ITV

# 2. 配置环境变量（可选）
cp .env.example .env

# 3. 启动容器
docker-compose up -d

# 4. 访问 Web 界面
# 浏览器打开 http://你的IP:8080
容器启动后，会自动执行以下任务：

拉取所有配置的 IPTV 源

测速、验证、分类、输出播放列表

启动 Web 管理界面（端口 8080）

数据持久化：

./data/ → 缓存数据库、源池、候选池

./output/ → 生成的播放列表、日志、统计信息

方式二：GitHub Actions 自动运行
Fork 本仓库到你的 GitHub 账号

启用 Actions：仓库 → Actions → 允许工作流

手动触发首次运行：Actions → IPTV 源智能更新与整理 → Run workflow

访问播放列表：

https://你的用户名.github.io/ITV/tv.m3u

https://你的用户名.github.io/ITV/tv.txt

⚙️ 配置说明
项目通过 环境变量（.env 文件或 Docker 环境）灵活配置。所有配置项见 .env.example。

核心配置项


变量	默认值	说明
RUN_MODE	schedule	运行模式：once（一次性）或 schedule（定时）
SCHEDULE_INTERVAL	21600	定时模式间隔（秒），默认 6 小时
MAX_WORKERS	20	并发测速线程数
TIMEOUT	8	HTTP 超时（秒）
FFMPEG_ENABLE	true	是否启用 ffmpeg 深度验证
FFMPEG_MODE	deep	deep（深度）/ quick（快速）/ off（关闭）
AUTONOMOUS_MODE	false	是否启用自治模式（源池→候选→稳定）
ENABLE_DEMO_FILTER	true	是否按 demo.txt 筛选频道
CACHE_RAW_HOURS	48	原始源缓存时长（小时）
WEB_SERVER_PORT	8080	Web 管理界面端口

固定源配置
编辑 src/fixed_sources.py 可预设优质源，格式：
CCTV_FIXED_SOURCES = {
    "CCTV-1": "http://45.192.97.170:8880/play/1.m3u8",
    "CCTV-5+": "http://45.192.97.170:8880/play/6.m3u8",
    # ...
}

📺 Web 管理界面
访问 http://你的IP:8080 进入管理面板：

1. 仪表盘
显示稳定源、固定源、源池总量、候选观察中数量

系统状态与最后运行时间

2. 频道列表
展示所有稳定源频道（名称、分类、延迟、编码、固定状态）

支持按频道名搜索、按分类筛选

点击图表图标快速跳转质量趋势

3. 固定源管理
添加固定源（频道名 + URL），同名会更新 URL

删除固定源（移除保护，但频道仍保留）

列表展示所有固定源及其 URL

4. 配置管理
在线编辑 MAX_WORKERS、TIMEOUT、MAX_SOURCES_PER_CHANNEL、DEMO_MATCH_MODE、FFMPEG_ENABLE

保存后需重启容器生效

5. 质量趋势
输入任意稳定源频道名（如 CCTV-1）

显示最近 7/14/30 天的延迟变化曲线

成功/失败状态用绿/红点标识

📂 输出文件说明


文件	说明
output/tv.m3u	标准 M3U 播放列表（按 demo.txt 顺序）
output/tv.txt	标准 TXT 格式（频道名,URL）
output/tv_multi.m3u	多源 M3U（每个频道多个备源，用 # 分隔）
output/channels.json	JSON API（供第三方调用）
output/shai.txt	demo 未匹配的频道列表
output/stats.json	采集统计信息
output/stable_sources.json	稳定源列表（含固定标记）
data/source_pool.json	源池（所有发现过的源）
data/candidate_pool.json	候选池（观察中的源）
data/trend.db	质量趋势数据库（SQLite）

🔧 高级特性
自治模式工作流程
发现阶段：拉取所有源，新源进入候选池

观察阶段：候选源经多次验证（成功率≥80%、延迟≤2000ms）后稳定

提升阶段：稳定候选源提升为稳定版，替换同名劣质源

质量监控：稳定源持续检测，连续失败 3 次触发告警

回滚机制：质量严重下降时自动从候选池找替代源

智能分类匹配
支持拼音匹配（如 zhejiang → 浙江卫视）

自动归类：全国省份、直辖市、港澳台

未匹配频道按省份关键词自动归类

固定源保护
用户指定的固定源不会被自动替换

可在 Web 界面或 fixed_sources.py 中管理

🐳 Docker 高级部署
使用 Docker Compose（推荐）
# docker-compose.yml
services:
  iptv-collector:
    build: .
    container_name: iptv-collector
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data
      - ./output:/app/output
      - ./alias.txt:/app/alias.txt:ro
      - ./blacklist.txt:/app/blacklist.txt:ro
      - ./demo.txt:/app/demo.txt:ro
    environment:
      - AUTONOMOUS_MODE=true
      - MAX_WORKERS=20
      - TIMEOUT=8
      - RUN_MODE=schedule
      - SCHEDULE_INTERVAL=21600
      - WEB_SERVER_PORT=8080

      手动构建镜像
      docker build -t iptv-collector .
docker run -d \
  --name iptv-collector \
  -p 8080:8080 \
  -v ./data:/app/data \
  -v ./output:/app/output \
  -e AUTONOMOUS_MODE=true \
  iptv-collector

  📦 依赖与兼容性
Python：3.10+

关键依赖：aiohttp, aiosqlite, Flask, flask-cors, pypinyin, tqdm, Chart.js (前端)

系统工具：ffmpeg（用于深度验证）

架构支持：x86_64 / ARM64（Docker 自动适配）

🤝 贡献指南
欢迎提交 Issue 和 Pull Request。开发前请确保：

代码风格符合 PEP8

新功能有对应测试（或日志验证）

更新 README.md 和 .env.example

📄 免责声明
本项目仅用于个人学习与测试，不用于任何商业用途。

所有节目源均来自互联网公开链接，项目本身不存储、不篡改任何媒体内容。
严禁将本项目及生成的播放列表用于商业传播、二次分发。
所有频道版权归原版权方所有，使用前请确保符合当地法律法规。
因违规使用产生的任何法律责任，均由使用者自行承担。

🙏 致谢
iptv-org/iptv – 公开 IPTV 源

Guovin/iptv-api – 采集工具参考

zilong7728/Collect-IPTV – 国内源

Flask – Web 框架

Chart.js – 前端图表

📬 反馈与支持
提交 Issue

查看 Actions 运行日志

交流讨论 Discussions
