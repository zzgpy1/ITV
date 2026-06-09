#!/bin/bash
set -e

echo "=========================================="
echo "IPTV 智能整理平台 Docker 容器启动"
echo "=========================================="

mkdir -p /app/data /app/output
cd /app

# 更新IP数据库（首次或文件无效时）
if [ "${ENABLE_IP_RESOLVE:-true}" = "true" ]; then
    if [ ! -f /app/qqwry.dat ] || [ "$(stat -c %s /app/qqwry.dat 2>/dev/null || echo 0)" -lt 1048576 ]; then
        echo "正在更新 IP 数据库..."
        python -m src.update_ipdb || echo "⚠️ IP 数据库更新失败，将使用已有文件（如有）"
    fi
else
    echo "⚙️ IP解析已禁用，跳过 IP 数据库更新"
fi

RUN_MODE=${RUN_MODE:-once}
INTERVAL=${SCHEDULE_INTERVAL:-21600}

# 采集任务函数（一次性）
run_once() {
    echo "$(date): 执行一次性采集任务..."
    python -m src.run
    echo "$(date): 采集任务完成"
}

# 采集任务循环（定时模式）
run_loop() {
    while true; do
        echo "$(date): 开始采集任务..."
        python -m src.run
        echo "$(date): 任务完成，等待 ${INTERVAL} 秒后继续..."
        sleep $INTERVAL
    done
}

# 根据模式执行采集
if [ "$RUN_MODE" = "once" ]; then
    run_once
elif [ "$RUN_MODE" = "schedule" ]; then
    echo "启动定时模式，每 ${INTERVAL} 秒执行一次"
    run_loop &
else
    echo "未知的运行模式: $RUN_MODE，请设置为 once 或 schedule"
    exit 1
fi

# 启动 HTTP 文件服务器（前台运行，提供输出文件）
echo "启动 HTTP 文件服务器，监听 0.0.0.0:8080，服务目录 /app/output"
export WEB_SERVER_PORT=8080
exec python -m src.server
