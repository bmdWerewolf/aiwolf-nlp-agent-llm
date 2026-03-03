#!/bin/bash
mkdir -p /workspace/tmp
export TMPDIR="/workspace/tmp"
export TEMP="/workspace/tmp"
export TMP="/workspace/tmp"

# 1. uvインストール
# 1. uvのバイナリパッケージを直接ダウンロード
curl -L https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz -o uv.tar.gz

# 2. 所有権変更を無視して強制解凍（--no-same-owner がポイントです）
tar -xf uv.tar.gz --no-same-owner

# 3. バイナリをパスの通った場所に移動
mv uv-x86_64-unknown-linux-gnu/uv /usr/local/bin/
mv uv-x86_64-unknown-linux-gnu/uvx /usr/local/bin/

# 4. 確認
uv --version

# 2. キャッシュ領域の隔離
mkdir -p /workspace/.cache/uv /workspace/.cache/huggingface /workspace/.cache/vllm /workspace/.cache/torch /workspace/.cache/triton
export UV_CACHE_DIR="/workspace/.cache/uv"
export HF_HOME="/workspace/.cache/huggingface"
export VLLM_CACHE_ROOT="/workspace/.cache/vllm"
export TORCH_HOME="/workspace/.cache/torch"
export TRITON_CACHE_DIR="/workspace/.cache/triton"

# 3. 仮想環境準備
cd /workspace/aiwolf
if [ ! -d ".venv" ]; then uv venv .venv; fi
source .venv/bin/activate
export OPENAI_API_KEY="dummy"

echo "Updating libraries..."
uv pip install fastapi uvicorn vllm openai langchain jinja2 pydantic python-dotenv langchain-openai nest_asyncio python-ulid websocket-client langchain-google-genai langchain_ollama langchain-openai langchain-anthropic langchain-community numpy pandas ulid-transform ipython
echo "--------------------------------------------------"
echo "Success! Environment is ready and storage-proof."
echo "--------------------------------------------------"