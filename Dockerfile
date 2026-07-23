FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY src/ ./src/
COPY config/ ./config/

# 创建输出和数据目录
RUN mkdir -p output data

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV IPTV_AUTONOMOUS_MODE=true
ENV IPTV_FFMPEG_ENABLE=true

# 运行
CMD ["python", "-m", "src.run"]
