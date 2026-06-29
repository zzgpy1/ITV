# Dockerfile
# 阶段1：构建依赖
FROM python:3.11-alpine AS builder

WORKDIR /app

# 安装编译依赖
RUN apk add --no-cache gcc musl-dev libffi-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 阶段2：运行时镜像
FROM python:3.11-alpine

WORKDIR /app

# 安装运行时依赖（ffmpeg）
RUN apk add --no-cache ffmpeg curl

# 复制已安装的包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/output

EXPOSE 8080

ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
