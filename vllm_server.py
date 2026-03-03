import asyncio
import uuid
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from vllm import AsyncLLMEngine, AsyncEngineArgs, SamplingParams
import nest_asyncio
import uvicorn

# 非同期実行の許可
nest_asyncio.apply()

# --- A100 (80GB) 向け最適化設定 ---
engine_args = AsyncEngineArgs(
    # 32BのAWQ量子化モデルを指定
    model="Qwen/Qwen2.5-72B-Instruct-AWQ",
    tokenizer="Qwen/Qwen2.5-72B-Instruct-AWQ",
    quantization="awq",
    gpu_memory_utilization=0.9, 
    max_model_len=32768,
    trust_remote_code=True,
    dtype="auto",
    enable_prefix_caching=True,
    max_num_seqs=16 
)

# エンジンの初期化
print("vLLM Engine Initializing... (A100のVRAMを確保中)")
engine = AsyncLLMEngine.from_engine_args(engine_args)
print("vLLM Engine Started! 準備完了です。")

app = FastAPI()

@app.post("/v1/chat/completions")
async def generate(request: dict):
    try:
        # --- 届いたメッセージを取得 ---
        messages = request.get("messages", [])

        latest_prompt = messages[-1].get("content", "")
        formatted_prompt = f"<|im_start|>user\n{latest_prompt}<|im_end|>\n<|im_start|>assistant\n"

        # --- Qwen が参照する全情報をターミナルに出力 ---
        print("\n" + "="*30 + " [QWEN FULL CONTEXT START] " + "="*30)
        print(formatted_prompt)
        print("="*30 + " [QWEN FULL CONTEXT END] " + "="*30 + "\n")

        # --- vLLMへの指示と推論 ---
        temp = request.get("temperature", 0.7)
        max_t = request.get("max_tokens", 2048)
        sampling_params = SamplingParams(
            temperature=temp,
            max_tokens=max_t,
            stop=["<|im_end|>", "<|endoftext|>"],
            skip_special_tokens=True
        )

        request_id = f"aiwolf-{str(uuid.uuid4())}"
        results_generator = engine.generate(formatted_prompt, sampling_params, request_id)

        final_output = ""
        async for request_output in results_generator:
            final_output = request_output.outputs[0].text

        # サーバー側での生成結果（タグ付き）も確認
        print(f"🔹 Qwen Output: {final_output.strip()[:100]}...") 

        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": final_output.strip()
                    },
                    "finish_reason": "stop"
                }
            ]
        }

    except Exception as e:
        print("❌ サーバー内部でエラーが起きました:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

def play_beep():
    # 440Hz（ラ）の音を1秒間生成
    framerate = 44100
    t = np.linspace(0, 1, framerate)
    data = np.sin(2 * np.pi * 440 * t)
    # Jupyterの出力として音声を送り出す
    display(Audio(data, rate=framerate, autoplay=True))

if __name__ == "__main__":
    # RunPod内部通信用にポート8000で起動
    uvicorn.run(app, host="0.0.0.0", port=8000)