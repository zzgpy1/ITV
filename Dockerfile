FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖（FFmpeg, nginx）
RUN apt-get update && apt-get install -y \
    ffmpeg \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY . /app

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制 nginx 配置模板
COPY utils/nginx-rtmp/conf/nginx.conf.template /etc/nginx/nginx.conf.template

# 暴露端口
EXPOSE 5180 8080 1935

# 启动脚本
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
