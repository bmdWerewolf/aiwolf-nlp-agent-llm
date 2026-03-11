# aiwolf-nlp-agent-llm (bmd team)

LLM-based agent for the AIWolf NLP Contest (Natural Language Division).
**Default configuration: 9-player game.** 5-player mode is also supported.

## Prerequisites

### For local execution

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11+ | |
| [uv](https://docs.astral.sh/uv/) | Latest | Package manager |
| LLM API | One of the following | Google Gemini / OpenAI / Ollama |

### For Docker execution

| Tool | Notes |
|------|-------|
| Docker / Docker Compose | |
| LLM API key | Google Gemini or OpenAI |

---

## Setup

```bash
git clone <this-repository-url>
cd aiwolf

# Configure API key
cp config/.env.example config/.env
# Edit config/.env and fill in your API key
```

---

## How to Run

### ⭐ Recommended: API-based development workflow

The best way to develop and tune prompts is to run the game server via Docker
and connect the agent directly from your terminal. This gives you full
visibility into what the LLM receives and outputs in real time.

**Terminal 1 — Start the game server**

```bash
docker compose --env-file ./config/.env up --build
```

This starts only the game server (port 8080). No agents are connected yet.

**Terminal 2 — Start the agent and observe LLM I/O**

```bash
uv run python src/main.py -c ./config/config_gemini_jp.yml
```

Running the agent locally (outside Docker) prints structured LLM logs
directly to the terminal, so you can see exactly what is sent to and received
from the model at every game phase:

```
╔══════════════════════════════════════════════════════╗
║                    LLM CALL                         ║
╠══════════════════════════════════════════════════════╣
║  過去のやりとり (HISTORY)                              ║
╚══════════════════════════════════════════════════════╝
  ┌─ ⚙️  SYSTEM ─
  (rules · identity · strategy — sent once, persists throughout the game)
  └────────────────────────────────────────────────────

  ┌─ 📋 指示 ─
  ### Phase: DAILY_INITIALIZE ...
  └────────────────────────────────────────────────────

  ┌─ 🤖 応答 ─
  <action>Over</action>
  └────────────────────────────────────────────────────

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  ★ 現在のリクエスト (PROMPT)                           ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
### Phase: TALK
新着会話: ...

┌──────────────────────────────────────────────────────┐
│  LLM応答 (RESPONSE)                                  │
└──────────────────────────────────────────────────────┘
<action>こんにちは。私はアスカです。</action>
```

- **HISTORY** shows all past exchanges (system context + prior phase turns)
- **★ PROMPT** is what the model is actually being asked right now
- **RESPONSE** is the raw output before action extraction

> This workflow is ideal for iterating on prompts in `config_gemini_jp.yml`
> without rebuilding Docker on every change.

---

### A. Run with Docker (all-in-one)

**① Start (server + all agents in one command)**

```bash
docker compose --profile single up --build
```

Uses `default_9.yml` (9-player) and `config_gemini_jp.yml` (Google Gemini) by default.

The agent container automatically connects to the server using `ws://server:8080/ws` (Docker internal hostname), regardless of the `url` setting in the config file.

**② Custom configuration**

```bash
# Switch to 5-player
SERVER_CONFIG=default_5.yml docker compose --profile single up --build

# Specify a different agent config
CONFIG_FILE=./config/config_ollama_local_jp.yml docker compose --profile single up --build

# Both at once
SERVER_CONFIG=default_5.yml CONFIG_FILE=./config/config_ollama_local_jp.yml docker compose --profile single up --build
```

**③ Server only (connect agents separately)**

```bash
docker compose up --build
```

Then connect agents locally (see section B below).

**④ View logs by service**

```bash
docker compose logs -f server   # server logs only
docker compose logs -f agent    # agent logs only
```

> Logs are also written to `./log/` and `./server/logs/`.

---

### B. Run locally

**① Install dependencies**

```bash
uv sync
```

**② Download the server binary**

macOS (Apple Silicon):
```bash
curl -L https://github.com/aiwolfdial/aiwolf-nlp-server/releases/latest/download/aiwolf-nlp-server-darwin-arm64 \
  -o server/aiwolf-nlp-server-darwin-arm64
chmod +x server/aiwolf-nlp-server-darwin-arm64
```

macOS (Intel):
```bash
curl -L https://github.com/aiwolfdial/aiwolf-nlp-server/releases/latest/download/aiwolf-nlp-server-darwin-amd64 \
  -o server/aiwolf-nlp-server-darwin-amd64
chmod +x server/aiwolf-nlp-server-darwin-amd64
```

> The server binary is gitignored — download it after cloning.

**③ Start the game server (Terminal 1)**

```bash
# 9-player (default)
./server/aiwolf-nlp-server-darwin-arm64 -c ./server/default_9.yml

# 5-player
./server/aiwolf-nlp-server-darwin-arm64 -c ./server/default_5.yml
```

**④ Start the agent (Terminal 2)**

The config files use `ws://localhost:8080/ws` by default, which connects directly to the local server.

```bash
# Using Google Gemini API (production)
uv run python src/main.py -c ./config/config_gemini_jp.yml

# Using Ollama (local testing)
uv run python src/main.py -c ./config/config_ollama_local_jp.yml
```

> To override the WebSocket URL without editing the config file, set the `WS_URL` environment variable:
> ```bash
> WS_URL=ws://localhost:9999/ws uv run python src/main.py -c ./config/config_gemini_jp.yml
> ```

**For Ollama, set up in advance:**

```bash
# Download a model
ollama pull phi3:mini

# Start Ollama server before running the agent
ollama serve
```

---

## Configuration Files

### Agent config (`config/`)

| File | Purpose |
|------|---------|
| `config_gemini_jp.yml` | **Production** (Google Gemini API, 9-player) |
| `config_ollama_local_jp.yml` | **Local testing** (Ollama) |
| `.env` | API keys (gitignored — must be created) |
| `.env.example` | API key template |

### Server config (`server/`)

| File | Purpose |
|------|---------|
| `default_9.yml` | **9-player** (default) |
| `default_5.yml` | 5-player |
| `default_5_2Teams.yml` | 5-player, 2-team match |

---

## Switching between 5-player and 9-player

| Setting | 9-player | 5-player |
|---------|---------|---------|
| Server config | `default_9.yml` | `default_5.yml` |
| `agent.num` in `config_gemini_jp.yml` | `9` | `5` |
| `agent.num` in `config_ollama_local_jp.yml` | `9` | `5` |

---

## Directory Structure

```
aiwolf/
├── config/
│   ├── config_gemini_jp.yml     # Production agent config
│   ├── config_ollama_local_jp.yml   # Local testing config
│   ├── .env                    # API keys (must be created)
│   └── .env.example            # API key template
├── server/
│   ├── default_9.yml           # 9-player server config
│   ├── default_5.yml           # 5-player server config
│   ├── default_5_2Teams.yml    # 2-team match config
│   └── Dockerfile              # Server Docker image
├── src/
│   ├── main.py                 # Entry point
│   ├── starter.py              # Connection handler
│   ├── agent/                  # Agent implementation
│   └── utils/                  # Utilities
├── Dockerfile                  # Agent Docker image
├── docker-compose.yml          # Docker Compose
└── pyproject.toml              # Dependency definitions
```
