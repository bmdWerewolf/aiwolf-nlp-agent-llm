# ============================================
# AIWolf NLP Agent LLM - Dockerfile
# ============================================

# 1. Base image: Official Python 3.11 slim version
#    - slim version has smaller size, suitable for production
#    - bookworm is the codename for Debian 12
FROM python:3.11-slim-bookworm

# 2. Set working directory
#    - All subsequent commands run in /app directory
WORKDIR /app

# 3. Install uv (fast Python package manager)
#    - Using pip to install
#    - Clean cache to reduce image size
RUN pip install uv --no-cache-dir

# 4. Copy dependency definition files
#    - Copy these files first to leverage Docker cache
#    - If dependencies unchanged, subsequent builds skip installation
COPY pyproject.toml uv.lock ./

# 5. Install Python dependencies
#    - --frozen: Use versions locked in uv.lock
#    - --no-cache: Don't cache downloaded packages, reduce image size
RUN uv sync --frozen --no-cache

# 6. Copy source code
#    - Placed after dependency installation, code changes won't trigger reinstall
COPY src/ ./src/

# 7. Set environment variable placeholders (actual values passed at runtime)
#    - These are just declarations, actual values provided via docker run -e
ENV OPENAI_API_KEY=""
ENV GOOGLE_API_KEY=""

# 8. Create log directory
RUN mkdir -p ./log

# 9. Default startup command
#    - Use uv run to execute in virtual environment
#    - Config file path needs to be mounted at runtime
CMD ["uv", "run", "python", "src/main.py", "-c", "./config/config.yml"]
