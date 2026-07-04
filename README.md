# IPTV 智能管理平台 · 自治版

全自动 IPTV 直播源采集、测速、验证、分类、合并与自治管理平台。  
通过 **GitHub Actions** 定时运行，无需服务器，永久免费。

---

## 📖 目录

- [功能特点](#功能特点)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
  - [Fork 仓库](#fork-仓库)
  - [查看输出](#查看输出)
  - [自定义配置](#自定义配置)
- [运行方式](#运行方式)
- [配置说明](#配置说明)
- [输出文件](#输出文件)
- [自治模式详解](#自治模式详解)
- [固定源管理](#固定源管理)
- [常见问题](#常见问题)
- [免责声明](#免责声明)

---

## 🚀 功能特点

- **多源聚合**：同时拉取 10+ 公开 IPTV 源，自动去重
- **双重测速**：HTTP 快速探测 + ffmpeg 深度验证（支持 deep/quick/off 三种模式）
- **智能分类**：按央视、卫视、地方（省份）、港澳台自动归类，支持拼音匹配
- **自治模式**：候选源观察 → 自动提升 → 质量监控 → 健康预测替换，全自动闭环
- **固定源保护**：用户指定优质源，永不自动替换
- **多格式输出**：M3U、TXT、多源 M3U（`#` 分隔多地址）、JSON API
- **GitHub Actions 定时运行**：每 6 小时自动更新，推送至仓库，永久免费
- **输出托管**：通过 GitHub Pages 直接访问播放列表

---

## 🏗️ 系统架构
┌─────────────────────────────────────────────────────────────────┐
│ GitHub Actions 定时触发 │
│ （每 6 小时 / 手动） │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│ 传统模式（采集与评估） │
├─────────────────────────────────────────────────────────────────┤
│ 拉取源 → 解析去重 → HTTP测速 → ffmpeg验证 → 合并 → 分类 → 输出 │
│ ↓ │
│ 写入候选池 (candidate_pool.json) │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│ 自治模式（观察与提升） │
├─────────────────────────────────────────────────────────────────┤
│ 阶段1（可选）：发现新源 → 加入候选池 │
│ 阶段2：观察候选源（读取历史统计数据，标记稳定） │
│ 阶段3：提升稳定源 → 写入稳定版 (stable_sources.json) │
│ 阶段4：健康预测替换（高风险源自动替换） │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│ 输出层（推送到仓库） │
├─────────────────────────────────────────────────────────────────┤
│ tv.m3u / tv.txt / tv_multi.m3u / channels.json / stats.json │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│ GitHub Pages 托管 │
│ https://你的用户名.github.io/ITV/tv.m3u │
└─────────────────────────────────────────────────────────────────┘


---

## 🚀 快速开始

### Fork 仓库

1. 访问 [https://github.com/zzgpy1/ITV](https://github.com/zzgpy1/ITV)
2. 点击右上角 **Fork** 按钮
3. 等待 Fork 完成

### 启用 GitHub Pages（可选）

1. 进入你的仓库 → **Settings** → **Pages**
2. 将 **Source** 设置为 `main` 分支，`/(root)` 目录
3. 点击 **Save**
4. 几分钟后，播放列表可通过以下地址访问：
   - `https://你的用户名.github.io/ITV/tv.m3u`
   - `https://你的用户名.github.io/ITV/tv.txt`

### 查看输出文件

输出文件位于仓库的 `output/` 目录：
- `output/tv.m3u` - 标准 M3U 播放列表
- `output/tv.txt` - TXT 格式
- `output/tv_multi.m3u` - 多源 M3U
- `output/channels.json` - JSON API
- `output/stats.json` - 统计信息

### 自定义配置

编辑 `.env.example` 并重命名为 `.env`，或直接修改仓库中的 `.github/workflows/update_iptv.yml` 中的环境变量。

---

## 🔄 运行方式

### 方式一：自动运行（推荐）

GitHub Actions 会按照以下规则自动运行：

- **定时触发**：每 6 小时自动执行一次（UTC 0, 6, 12, 18 点）
- **手动触发**：进入 Actions → `IPTV 源智能更新与整理` → `Run workflow`

### 方式二：本地运行

```bash
# 克隆仓库
git clone https://github.com/你的用户名/ITV.git
cd ITV

# 安装依赖
pip install -r requirements.txt

# 安装 ffmpeg（用于深度验证）
# Ubuntu/Debian
sudo apt-get install ffmpeg
# macOS
brew install ffmpeg

# 运行
python -m src.run

⚙️ 配置说明
通过修改 .github/workflows/update_iptv.yml 中的环境变量，或本地 .env 文件进行配置。

变量	默认值	说明
AUTONOMOUS_MODE	true	启用自治模式（先跑传统模式，再跑自治模式）
MAX_WORKERS	20	并发测速线程数
TIMEOUT	8	HTTP 超时（秒）
FFMPEG_ENABLE	true	是否启用 ffmpeg 深度验证
FFMPEG_MODE	deep	deep（深度）/ quick（快速）/ off（关闭）
ENABLE_DEMO_FILTER	true	是否按 demo.txt 筛选频道
CANDIDATE_MIN_SUCCESS	3	候选源提升所需最少成功次数
CANDIDATE_MIN_SUCCESS_RATE	0.5	候选源最低成功率（50%）
CANDIDATE_MAX_LATENCY	3000	候选源最大平均延迟（毫秒）
PREDICT_THRESHOLD	0.6	健康预测失效阈值（超过则尝试替换）
SLOW_SPEED_THRESHOLD	3000	慢速源阈值
📂 输出文件
所有输出文件位于 output/ 目录：

文件	说明
tv.m3u	标准 M3U 播放列表（按 demo.txt 顺序）
tv.txt	TXT 格式（频道名,URL）
tv_multi.m3u	多源 M3U（每个频道多个备源，用 # 分隔）
channels.json	JSON API（供第三方调用）
shai.txt	Demo 未匹配的频道列表
stats.json	采集统计信息
stable_sources.json	稳定源列表（含固定标记）
run.log	运行日志
数据文件位于 data/ 目录：

文件	说明
source_pool.json	源池（所有发现过的源）
candidate_pool.json	候选池（观察中的源）
iptv_cache.db	SQLite 缓存（测速结果、历史记录）
🤖 自治模式详解
自治模式实现“采集→评估→观察→提升→替换”的完整闭环：

阶段1：发现新源（可选）
拉取所有配置源，新发现的源自动加入候选池（状态 observing）。

阶段2：观察候选源
从数据库读取候选源的历史测速统计数据（成功率、平均延迟、检查次数），将满足以下条件的源标记为 stable：

检查次数 ≥ CANDIDATE_MIN_SUCCESS（默认 3 次）

成功率 ≥ CANDIDATE_MIN_SUCCESS_RATE（默认 50%）

平均延迟 ≤ CANDIDATE_MAX_LATENCY（默认 3000ms）

阶段3：提升稳定源
将 stable 候选源提升为稳定源，写入 stable_sources.json，并替换同名旧源（除非是固定源）。

阶段4：健康预测与自动替换
对每个稳定源，基于过去 HEALTH_HISTORY_DAYS 天的速度历史预测失效概率。若概率超过 PREDICT_THRESHOLD，尝试从候选池中寻找更优源进行替换。

运行流程
当 AUTONOMOUS_MODE=true 时：

传统模式：拉取源 → 测速 → 验证 → 合并 → 输出（同时将结果写入候选池）

自治模式（跳过发现）：直接观察候选池 → 提升稳定源 → 健康预测替换

📌 固定源管理
编辑 src/fixed_sources.py 可预设优质源，这些源不会被自动替换，且拥有最高优先级。
CCTV_FIXED_SOURCES = {
    "CCTV-1": [
        "http://69.30.245.50/live/cctv1.m3u8",
        "http://45.192.97.170:8880/play/1.m3u8"
    ],
    "CCTV-5+": [
        "http://45.192.97.170:8880/play/6.m3u8"
    ],
    # ...
}
固定源支持多个备选地址，系统会自动选择延迟最低的有效源。

如何添加自定义固定源？
编辑 src/fixed_sources.py

按 "频道名": ["url1", "url2"] 格式添加

提交并推送，下次 Actions 运行时会自动生效

❓ 常见问题
Q: 自治模式提升数为 0，怎么办？
A: 可能原因：

候选源检查次数不足（需 ≥ CANDIDATE_MIN_SUCCESS）

成功率低于阈值

延迟过高

解决方法：降低门槛（调整 .env 中相关变量），或等待更多测速数据积累。

Q: 源池总数为 0，正常吗？
A: 正常。source_pool.json 仅在发现阶段写入，自治模式跳过发现时不会加载。不影响候选池提升。

Q: 如何手动触发一次更新？
A: 进入仓库 Actions → IPTV 源智能更新与整理 → Run workflow。

Q: 固定源如何更新？
A: 修改 src/fixed_sources.py，提交后下次运行会自动生效。

Q: 播放列表多久更新一次？
A: 每 6 小时自动更新一次。如需更频繁，可修改 .github/workflows/update_iptv.yml 中的 cron 表达式。

Q: 如何查看运行日志？
A: 进入仓库 Actions → 点击最新的运行记录 → 展开 运行采集程序 步骤即可查看详细日志。

⚠️ 免责声明
本项目仅用于个人学习与测试，不用于任何商业用途。
所有节目源均来自互联网公开链接，项目本身不存储、不篡改任何媒体内容。
严禁将本项目及生成的播放列表用于商业传播、二次分发。
所有频道版权归原版权方所有，使用前请确保符合当地法律法规。
因违规使用产生的任何法律责任，均由使用者自行承担。

🙏 致谢
iptv-org/iptv – 公开 IPTV 源

Guovin/iptv-api – 采集工具参考

zilong7728/Collect-IPTV – 国内源

