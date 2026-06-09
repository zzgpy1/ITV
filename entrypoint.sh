#!/bin/bash
set -e

echo "=========================================="
echo "IPTV 智能整理平台 Docker 容器启动"
echo "检测架构: $(uname -m)"
echo "=========================================="

mkdir -p /app/data /app/output
cd /app

if [ ! -f /app/qqwry.dat ] || [ "$(stat -c %s /app/qqwry.dat 2>/dev/null || echo 0)" -lt 1048576 ]; then
    echo "正在更新 IP 数据库..."
    python -m src.update_ipdb || echo "⚠️ IP 数据库更新失败，将使用已有文件（如有）"
fi

echo "启动 HTTP 服务器，监听 0.0.0.0:8000，目录 /app/output"
python -m src.server >> /app/output/http.log 2>&1 &
HTTP_PID=$!
echo "HTTP 服务器进程 PID: $HTTP_PID"

sleep 2
if ! kill -0 $HTTP_PID 2>/dev/null; then
    echo "❌ HTTP 服务器启动失败，查看 /app/output/http.log"
    cat /app/output/http.log
    exit 1
fi
echo "✅ HTTP 服务器已启动"

RUN_MODE=${RUN_MODE:-once}
INTERVAL=${SCHEDULE_INTERVAL:-21600}

run_collector() {
    if [ "$RUN_MODE" = "once" ]; then
        echo "执行一次性采集任务..."
        python -m src.run
        echo "✅ 一次性采集完成，HTTP 服务器继续运行"
        wait $HTTP_PID
    elif [ "$RUN_MODE" = "schedule" ]; then
        echo "启动定时模式，每 ${INTERVAL} 秒执行一次"
        while true; do
            echo "$(date): 开始采集任务..."
            python -m src.run
            echo "$(date): 采集完成，等待 ${INTERVAL} 秒后继续..."
            sleep $INTERVAL
        done
    else
        echo "未知运行模式: $RUN_MODE，请设置为 once 或 schedule"
        exit 1
    fi
}

run_collector
