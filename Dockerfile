# ============================================
# AIWolf NLP Agent LLM - Dockerfile
# ============================================

# 1. 基础镜像：使用官方 Python 3.11 slim 版本
#    - slim 版本体积小，适合生产环境
#    - bookworm 是 Debian 12 的代号
FROM python:3.11-slim-bookworm

# 2. 设置工作目录
#    - 后续所有命令都在 /app 目录下执行
WORKDIR /app

# 3. 安装 uv（快速的 Python 包管理器）
#    - 使用官方安装脚本
#    - 安装后清理缓存减小镜像体积
RUN pip install uv --no-cache-dir

# 4. 复制依赖定义文件
#    - 先复制这两个文件，利用 Docker 缓存机制
#    - 如果依赖没变，后续构建会跳过安装步骤
COPY pyproject.toml uv.lock ./

# 5. 安装 Python 依赖
#    - --frozen: 使用 uv.lock 中锁定的版本
#    - --no-cache: 不缓存下载的包，减小镜像体积
RUN uv sync --frozen --no-cache

# 6. 复制源代码
#    - 放在安装依赖之后，代码改动不会触发重新安装依赖
COPY src/ ./src/

# 7. 设置环境变量占位符（运行时传入实际值）
#    - 这里只是声明，实际值由 docker run -e 传入
ENV OPENAI_API_KEY=""
ENV GOOGLE_API_KEY=""

# 8. 创建日志目录
RUN mkdir -p ./log

# 9. 默认启动命令
#    - 使用 uv run 在虚拟环境中执行
#    - 配置文件路径需要在运行时挂载
CMD ["uv", "run", "python", "src/main.py", "-c", "./config/config.yml"]

