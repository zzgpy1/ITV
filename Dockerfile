# 多阶段构建
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 升级 pip 并使用国内镜像源（清华/阿里云）加速安装
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 最终镜像
FROM python:3.11-slim-bookworm

# 安装 ffmpeg 和运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ffprobe -version

WORKDIR /app

# 从 builder 复制依赖
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY src/ ./src/
COPY alias.txt blacklist.txt demo.txt ./

# 创建必要目录
RUN mkdir -p /app/data /app/output

# 暴露 HTTP 服务端口
EXPOSE 8080

# 健康检查（需要 curl）
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/api/status || exit 1

# 启动脚本
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
