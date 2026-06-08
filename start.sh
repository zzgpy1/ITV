#!/bin/bash
set -e

echo "=========================================="
echo "IPTV 智能整理平台 Docker 容器启动"
echo "=========================================="

mkdir -p /app/data /app/output
cd /app

# 更新 IP 数据库（首次或文件不存在时）
if [ ! -f /app/qqwry.dat ] || [ "$(stat -c %s /app/qqwry.dat 2>/dev/null || echo 0)" -lt 1048576 ]; then
    echo "正在更新 IP 数据库..."
    python -m src.update_ipdb || echo "⚠️ IP 数据库更新失败，将使用已有文件（如有）"
fi

# 读取运行模式
RUN_MODE=${RUN_MODE:-once}
INTERVAL=${SCHEDULE_INTERVAL:-21600}

# 定义采集任务函数
run_collector() {
    while true; do
        echo "$(date): 开始采集任务..."
        python -m src.run
        echo "$(date): 任务完成，等待 ${INTERVAL} 秒后继续..."
        sleep $INTERVAL
    done
}

if [ "$RUN_MODE" = "once" ]; then
    echo "执行一次性采集任务..."
    python -m src.run
    echo "✅ 任务完成"
elif [ "$RUN_MODE" = "schedule" ]; then
    echo "启动定时模式，每 ${INTERVAL} 秒执行一次"
    run_collector &      # 后台运行采集循环
else
    echo "未知的运行模式: $RUN_MODE，请设置为 once 或 schedule"
    exit 1
fi

# 启动 HTTP 文件服务器（前台运行，保证容器不退出）
echo "启动 HTTP 文件服务器..."
exec python -m src.server
