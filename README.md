# IPTV 智能整理平台

> 全自动 IPTV 源采集、测速、验证、分类与输出系统

---

## 📖 项目简介

IPTV 智能整理平台 是一个全自动的 IPTV 直播源采集与维护系统。它能够从多个公开源自动抓取直播链接，通过多级验证（HTTP 测速 + ffmpeg 深度验证）过滤无效源，并按照央视、卫视、地方、港澳台等分类智能整理输出，解决公共直播源频繁失效、卡顿的痛点。

**核心特点**：

🔍 多源采集：自动聚合 10+ 公开 IPTV 源，支持 M3U/TXT 格式解析

⚡ 双重验证：HTTP 并发测速 + ffmpeg 深度验证（支持缓存复用）

🧠 自治维护：源池 → 候选版 → 稳定版 → 质量回路，系统自动维护源列表

📊 Web 管理面板：美观的暗色主题仪表盘，可视化查看和管理频道

🏷️ 智能分类：基于 Demo 模板匹配 + 省份自动归类 + 拼音匹配

📌 固定源保护：用户指定的优质源不会被自动替换

🎬 特色分类补充：从 abc123 源采集音乐、电影、动漫等特色频道

📦 多格式输出：支持 M3U、TXT、多源 M3U、JSON API 四种输出格式

🐳 简单部署：支持 Docker 一键部署和 GitHub Actions 自动化

---

🏗️ 系统架构

┌─────────────────────────────────────────────────────────────────────┐
│                         Web 管理面板 (Flask)                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐   │
│  │ 仪表盘  │ │ 频道列表 │ │固定源管理│ │ 配置管理 │ │ 质量趋势   │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│                      质量回路 (持续监控与评估)                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────────┐ │
│  │ 成功率监控  │ │ 失败次数统计 │ │ 崩溃风险分析 │ │  自动回滚    │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│  稳定版        │  候选版         │  源池           │  固定源        │
│  (输出使用)    │  (观察验证中)   │  (新源发现)     │  (用户指定)    │
│  ✅ 已验证稳定 │  ⏳ 持续观察    │  🔍 待验证      │  📌 永久保留   │
└─────────────────────────────────────────────────────────────────────┘

✨ 功能特点
1. 智能采集与验证
多源聚合：自动拉取 10+ 公开 IPTV 源（iptv-org、GitHub 等）

HTTP 测速：并发探测每个频道的响应速度（HEAD + 分段下载）

ffmpeg 深度验证：通过 ffprobe 检测视频流有效性，过滤纯音频/DRM/失效源

分级验证策略：缓存复用 + HTTP 初筛 + ffprobe 深度验证，减少 50%-70% 的 ffmpeg 调用

国内频道过滤：自动识别并过滤国外频道，聚焦国内直播源

2. 自治维护体系
源池管理：自动发现新源，存入源池数据库

候选版观察：新源进入候选池，经过持续验证（成功率 > 80%，延迟 < 2000ms）后才提升

稳定版管理：只保留经过验证的稳定源用于输出

质量回路：持续监控稳定版质量，自动替换失效源

固定源保护：用户指定的源不会被自动替换

3. Web 管理面板
仪表盘：展示稳定源数量、固定源数量、源池总量、候选观察中数量

频道列表：展示所有稳定源，支持搜索和分类筛选

固定源管理：在线添加/删除固定源，实时生效

配置管理：在线调整并发数、超时时间、匹配模式等参数（需重启生效）

质量趋势：查看每个频道的延迟变化曲线，绿色/红色点表示成功/失败

4. 智能分类与匹配
Demo 模板匹配：基于 demo.txt 定义频道顺序和分类

拼音匹配：支持中文频道名与拼音的相互匹配

省份自动归类：未匹配频道根据名称中的省份/城市自动分配到对应分类

动态分类追加：新分类自动追加到输出文件末尾

5. 固定源保护机制
用户通过 Web 界面或 fixed_sources.py 指定的源，标记为 is_fixed=True

自治模式不会自动替换固定源

Web 界面可随时添加/删除固定源

6. 多格式输出
tv.m3u：标准 M3U 播放列表

tv.txt：标准 TXT 格式（频道名,URL）

tv_multi.m3u：多源切换 M3U（同一频道多个备源）

channels.json：JSON API 格式，供其他程序调用


🚀 部署方法
方式一：Docker 部署（推荐）
# 1. 克隆项目
git clone https://github.com/zzgpy1/ITV.git
cd ITV

# 2. 配置环境变量（可选）
cp .env.example .env
# 编辑 .env 调整配置

# 3. 启动容器
docker-compose up -d

# 4. 查看日志
docker logs -f iptv-collector

访问 http://你的设备IP:8080 打开 Web 管理面板。

方式二：GitHub Actions 自动化（Fork 使用）
Fork 本仓库 到你的 GitHub 账号

启用 GitHub Actions：仓库 → Actions → 允许工作流

手动触发首次运行：Actions → IPTV 源智能更新与整理 → Run workflow

等待 10-20 分钟后访问：

https://你的用户名.github.io/ITV/tv.m3u

https://你的用户名.github.io/ITV/tv.txt

方式三：本地运行
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env

# 3. 运行采集
python -m src.run

# 4. 启动 Web 服务
python -m src.server

⚙️ 环境变量配置

   运行模式  
  
    变量	                             默认值	                     说明

   RUN_MODE	                         schedule            	once 或 schedule

  SCHEDULE_INTERVAL	                 21600	                 定时任务间隔（秒）
    
    性能配置

     变量	                         默认值	                       说明

  MAX_WORKERS	                       20	                       最大并发数

    TIMEOUT	                          8	                      请求超时（秒）

 DYNAMIC_CONCURRENCY	                true	                      是否启用动态并发

    MIN_WORKERS	                    5	                     最小并发数

   验证配置

   变量	                         默认值                         	说明

FFMPEG_ENABLE	                   true	                   是否启用 ffmpeg 验证

FFMPEG_MODE	                      deep	                   deep / quick / off

FFPROBE_CACHE_HOURS	              168	                 ffprobe 缓存时长（小时）

  缓存配置

   变量	                        默认值	                       说明

CACHE_RAW_HOURS	                48	                   原始源缓存时长

CACHE_SPEED_HOURS	                24	                   测速结果缓存时长

ENABLE_INCREMENTAL_FETCH	       true	                   启用增量更新

   功能开关

    变量	                          默认值	                       说明

ENABLE_DEMO_FILTER	              true	               启用 Demo 筛选

ENABLE_ALIAS	                    true	               启用别名标准化

ENABLE_BLACKLIST	                 true	               启用 URL 黑名单

DATABASE_ENABLE	                 true	               启用数据库缓存

   自治模式

    变量	                         默认值	                  说明

AUTONOMOUS_MODE            	    false	               启用自治模式

AUTO_UPDATE_STABLE	              true	               自动更新稳定版

AUTO_REPLACE_FAILED	              true	               自动替换失效源

QUALITY_CHECK_INTERVAL	            24	                  质量检查间隔（小时）

CANDIDATE_MIN_SUCCESS	            10	                 候选稳定最少成功次数


CANDIDATE_MIN_SUCCESS_RATE	        0.8	                 候选最低成功率

CANDIDATE_MAX_LATENCY	          2000	                候选最大延迟（ms）

   Web 界面

    变量	                        默认值	                    说明

WEB_SERVER_PORT                	 8080	                Web 服务端口

WEB_SERVER_HOST	               0.0.0.0	               监听地址

   输出配置
        
    变量	                       默认值	                   说明

ENABLE_JSON_OUTPUT	            true	                生成 JSON API

ENABLE_LITE_VERSION	            false	                生成精简版

ENABLE_EPG_OUTPUT	               false	                生成 EPG 版本

MAX_SOURCES_PER_CHANNEL	           3	             每个频道保留源数

📁 数据文件说明

   文件	                                 说明

output/tv.m3u	                    标准 M3U 播放列表

output/tv.txt	                   TXT 格式播放列表

output/tv_multi.m3u	               多源切换 M3U

output/channels.json	             JSON API 格式

output/stable_sources.json	         稳定源配置

output/stats.json	                  运行统计信息

data/source_pool.json	             源池数据库

data/candidate_pool.json	         候选池数据库

data/trend.db	                 质量趋势数据库（SQLite）

🎯 使用说明

Web 管理面板

页面	                                功能

仪表盘	                         查看系统状态（稳定源、固定源、源池、候选观察中数量，最后运行时间）

频道列表	                       查看所有稳定源，支持搜索和分类筛选（央视/卫视/地方/港澳台/其他）

固定源管理	                   添加/删除固定源，添加后该源不会被自动替换

配置管理	                      调整并发数、超时时间、匹配模式等参数（需重启生效）

质量趋势	                     输入频道名查看延迟变化曲线，绿色/红色点表示成功/失败

固定源管理

在 Web 界面「固定源管理」页面输入频道名和 URL

点击「添加」即可将指定源设为固定源

固定源会显示在列表中，点击回收站图标可移除

固定源不会被自治模式的自动替换机制覆盖

质量趋势查看
在 Web 界面「质量趋势」页面输入稳定源频道名（如 CCTV-1）

选择时间范围（最近7/14/30天）

点击「查看趋势」即可显示延迟变化曲线

🔧 自定义配置
添加自定义 IPTV 源
编辑 src/config.py，在 IPTV_SOURCES 列表中添加 URL：
IPTV_SOURCES = [
    # ... 现有源 ...
    "https://your-custom-source.com/playlist.m3u",
]

修改分类匹配规则
编辑 demo.txt 定义频道顺序和分类，格式：
📺央视频道,#genre#
CCTV-1
CCTV-2
...

预置固定源
编辑 src/fixed_sources.py：
CCTV_FIXED_SOURCES = {
    "CCTV-1": "http://45.192.97.170:8880/play/1.m3u8",
    "CCTV-2": "http://45.192.97.170:8880/play/2.m3u8",
    # ...
}

配置黑名单
编辑 blacklist.txt，每行一个关键词或正则表达式，匹配到的 URL 将被过滤。

📊 预期效果
指标	自治模式关闭	自治模式开启
采集源数量	10 个	10 个 + 自动发现
输出频道数	200-400 个	300-600 个
源维护	手动	自动
失效源处理	下次采集可能仍存在	自动替换
Web 管理	无	完整面板

📝 更新日志
v2.0 (2026-06)
🚀 新增自治模式（源池→候选版→稳定版→质量回路）

🌐 新增 Web 管理面板（仪表盘、频道列表、固定源管理、配置管理、质量趋势）

🧠 新增智能分类匹配（拼音匹配 + 省份自动归类 + 地级市映射）

📌 新增固定源保护机制

📈 新增质量趋势监控（延迟变化曲线）

⚡ 优化 ffmpeg 验证（缓存复用 + 分级验证 + 轻量级模式）

🔧 优化并发控制（动态并发 + 连接池复用）

🐳 优化 Docker 部署（国内镜像源加速）

v1.0 (2026-05)
初始版本：多源采集、HTTP 测速、ffmpeg 验证、Demo 筛选、多格式输出

⚖️ 免责声明
本项目仅用于个人学习与测试用途，不用于任何商业、盈利及违规用途。

所有节目源均来自互联网公开可访问链接

项目本身不生产、不存储、不篡改任何媒体内容

严禁将本项目及生成的播放列表用于商业传播、二次分发、公开分享等行为

所有频道版权均归原版权方所有，使用前请确保符合当地法律法规

因违规使用本项目产生的任何法律责任、版权纠纷，均归使用者自行承担

🙏 致谢
iptv-org/iptv - 全球 IPTV 频道集合

Guovin/iptv-api - IPTV API 服务

zilong7728/Collect-IPTV - IPTV 源采集

fanmingming/live - 国内直播源

📞 反馈与贡献
欢迎提交 Issue 和 Pull Request！

Issue: GitHub Issues

讨论: GitHub Discussions

⭐ 如果本项目对您有帮助，请给一个 Star 支持一下！
