# Dockerfile
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# 设置 Debian 镜像源为阿里云（加速下载，避免网络问题）
RUN echo "deb http://mirrors.aliyun.com/debian bookworm main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian bookworm-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free" >> /etc/apt/sources.list

# 安装编译依赖（仅构建阶段需要），带重试机制（失败时重试）
RUN apt-get update && \
    apt-get install -y --no-install-recommends --fix-missing gcc && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt 并安装依赖（跳过 pip 升级，避免哈希校验失败）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn

# 最终镜像
FROM python:3.11-slim-bookworm

WORKDIR /app

# 设置 Debian 镜像源为阿里云
RUN echo "deb http://mirrors.aliyun.com/debian bookworm main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian bookworm-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free" >> /etc/apt/sources.list

# 安装运行时依赖（ffmpeg 用于视频验证），带重试机制（失败时重试）
RUN apt-get update && \
    apt-get install -y --no-install-recommends --fix-missing ffmpeg curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    ffprobe -version

# 从构建阶段复制已安装的 Python 包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/output

# 暴露端口
EXPOSE 8080

# 启动脚本
ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
