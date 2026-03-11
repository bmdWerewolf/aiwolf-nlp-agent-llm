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

**Switch to 5-player server**

Pass `SERVER_CONFIG` before the docker command:

```bash
SERVER_CONFIG=default_5.yml docker compose --env-file ./config/.env up --build
```

Also update `agent.num` in your config file to match:

| Config file | `agent.num` |
|-------------|-------------|
| 9-player    | `9`         |
| 5-player    | `5`         |

**Switch agent config (e.g. Ollama instead of Gemini)**

```bash
uv run python src/main.py -c ./config/config_ollama_local_jp.yml
```

For Ollama, make sure the model is downloaded and the server is running first:

```bash
ollama pull phi3:mini
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
