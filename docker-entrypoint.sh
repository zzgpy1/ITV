#!/bin/sh
set -e

# 生成 nginx 配置（替换端口）
envsubst '${APP_PORT} ${NGINX_HTTP_PORT} ${NGINX_RTMP_PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# 启动 nginx
nginx -g 'daemon off;' &

# 启动 Python 服务（如果开启了 RTMP，则启动 Flask 服务；否则仅运行一次采集）
if [ "$OPEN_RTMP" = "true" ]; then
    # 启动 Flask 服务（后台）
    python -m src.service.app &
fi

# 执行采集（一次）
python -m src.run

# 保持容器运行（如果服务在后台）
wait
