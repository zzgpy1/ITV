# Dockerfile
FROM python:3.11-alpine AS builder

WORKDIR /app

# 设置 Alpine 国内镜像源（阿里云）
RUN echo "https://mirrors.aliyun.com/alpine/v3.19/main" > /etc/apk/repositories && \
    echo "https://mirrors.aliyun.com/alpine/v3.19/community" >> /etc/apk/repositories

# 安装编译依赖（gcc 等）
RUN apk add --no-cache --update gcc musl-dev libffi-dev

COPY requirements.txt .
# 先升级 pip，然后安装依赖，增加超时时间
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/ \
        --trusted-host pypi.tuna.tsinghua.edu.cn --default-timeout=120

# 运行时镜像
FROM python:3.11-alpine

WORKDIR /app

RUN echo "https://mirrors.aliyun.com/alpine/v3.19/main" > /etc/apk/repositories && \
    echo "https://mirrors.aliyun.com/alpine/v3.19/community" >> /etc/apk/repositories

# 安装 ffmpeg 和 curl
RUN apk add --no-cache --update ffmpeg curl && \
    rm -rf /var/cache/apk/*

# 从构建阶段复制已安装的 Python 包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/output

EXPOSE 8080

ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
