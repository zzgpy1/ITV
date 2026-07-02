# ===================== 构建阶段 =====================
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# 仅安装编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 安装依赖 + 清理所有无用文件（关键瘦身）
RUN pip install --no-cache-dir --root-user=1 -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn \
    # 删除所有无用文件：文档、测试、缓存、字节码、dist-info
    && find /usr/local/lib/python3.11/site-packages -type d -name "__pycache__" -o -name "*.pyc" -o -name "*.pyo" -o -name "*.dist-info" -o -name "*.egg-info" -o -name "tests" -o -name "docs" | xargs rm -rf

# ===================== 运行阶段（超精简） =====================
FROM python:3.11-slim-bookworm

WORKDIR /app

# 只装必须的 ffmpeg，不装任何多余工具
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/share/doc /usr/share/man /usr/share/locale \
    && ffprobe -version

# 完整复制 Python 运行环境（只复制有效文件）
COPY --from=builder /usr/local /usr/local

# 复制项目代码
COPY src/ ./src/
COPY demo.txt alias.txt blacklist.txt ./
COPY entrypoint.sh ./

# 目录
RUN mkdir -p /app/data /app/output && chmod +x /app/entrypoint.sh

# 环境变量（不变）
ENV AUTONOMOUS_MODE=true \
    FFMPEG_ENABLE=true \
    MAX_WORKERS=20 \
    TIMEOUT=8 \
    CACHE_HOURS=24 \
    CACHE_RAW_HOURS=48 \
    ENABLE_INCREMENTAL_FETCH=true \
    ENABLE_DEMO_FILTER=true \
    ENABLE_ALIAS=true \
    ENABLE_BLACKLIST=true \
    DATABASE_ENABLE=true \
    RUN_MODE=schedule \
    SCHEDULE_INTERVAL=21600 \
    WEB_SERVER_PORT=8080 \
    WEB_SERVER_HOST=0.0.0.0 \
    ENABLE_JSON_OUTPUT=true \
    ENABLE_LITE_VERSION=false \
    ENABLE_EPG_OUTPUT=false \
    HTTP_TIMEOUT=8 \
    SLOW_SPEED_THRESHOLD=3000 \
    MAX_RETRY_BEFORE_BLACKLIST=2 \
    PREDICT_THRESHOLD=0.6 \
    HEALTH_HISTORY_DAYS=30

EXPOSE 8080

ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
