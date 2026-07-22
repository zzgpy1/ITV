# IPTV 智能管理平台（自治版）

自动采集、测速、验证、分类、合并并输出 M3U/TXT/JSON，支持自治模式自动替换失效源。

## 快速开始
1. Fork 仓库
2. 配置 `config/demo.txt` 和 `config/alias.txt`（可选）
3. GitHub Actions 自动运行，或手动执行 `python -m src.run`

## 输出文件
- `output/tv.m3u` 标准 M3U
- `output/tv.txt` TXT 格式
- `output/tv_multi.m3u` 多源 M3U
- `output/channels.json` JSON API

## 配置
所有配置通过环境变量或 `.env` 文件，默认值见 `src/settings.py`。

## 免责声明
仅供学习，请勿用于商业用途。
