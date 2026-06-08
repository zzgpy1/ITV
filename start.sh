#!/bin/bash
# start.sh - 同时启动采集服务和 HTTP 文件服务

set -e

echo "=========================================="
echo "IPTV 智能整理平台 Docker 容器启动"
echo "=========================================="

# 创建必要的目录
mkdir -p /app/data /app/output

# 进入工作目录
cd /app

# 更新 IP 数据库（首次或文件不存在时）
if [ ! -f /app/qqwry.dat ] || [ "$(stat -c %s /app/qqwry.dat 2>/dev/null || echo 0)" -lt 1048576 ]; then
    echo "正在更新 IP 数据库..."
    python -m src.update_ipdb || echo "⚠️ IP 数据库更新失败，将使用已有文件（如有）"
fi

# 判断运行模式
RUN_MODE=${RUN_MODE:-once}

if [ "$RUN_MODE" = "once" ]; then
    echo "执行一次性采集任务..."
    python -m src.run
    echo "✅ 任务完成"
elif [ "$RUN_MODE" = "schedule" ]; then
    INTERVAL=${SCHEDULE_INTERVAL:-21600}  # 默认6小时
    echo "启动定时模式，每 ${INTERVAL} 秒执行一次"
    
    # 启动后台循环执行采集
    while true; do
        echo "$(date): 开始采集任务..."
        python -m src.run
        echo "$(date): 任务完成，等待 ${INTERVAL} 秒后继续..."
        sleep $INTERVAL
    done &
fi

# 启动 HTTP 文件服务器
echo "启动 HTTP 文件服务器..."
exec python -m src.server
