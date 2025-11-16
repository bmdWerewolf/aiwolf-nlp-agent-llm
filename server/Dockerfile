# 1. 使用一个轻量级的 Linux 基础镜像
FROM debian:bookworm-slim

# 2. 安装 curl (用于下载)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 3. 设置工作目录
WORKDIR /app

# 4. 【关键】在构建镜像时下载服务器（而不是从本地复制）
RUN curl -LO https://github.com/aiwolfdial/aiwolf-nlp-server/releases/latest/download/aiwolf-nlp-server-linux-amd64
RUN chmod u+x ./aiwolf-nlp-server-linux-amd64

# 5. 从构建上下文 (./server) 复制配置文件到镜像中
COPY default_5.yml .
COPY default_13.yml .
# COPY .env .

# 6. 设置默认启动命令
CMD ["./aiwolf-nlp-server-linux-amd64", "-c", "./default_5.yml"]