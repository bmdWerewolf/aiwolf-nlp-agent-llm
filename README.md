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

### A. Run with Docker (recommended)

**① Start**

```bash
docker compose up --build
```

Uses `default_9.yml` (9-player) and `config_koji_api.yml` (Google Gemini) by default.

**② Custom configuration**

```bash
# Switch to 5-player
SERVER_CONFIG=default_5.yml docker compose up --build

# Specify a different agent config
CONFIG_FILE=./config/config_koji_local.yml docker compose up --build

# Both at once
SERVER_CONFIG=default_5.yml CONFIG_FILE=./config/config_koji_local.yml docker compose up --build
```

> Logs are written to `./log/` and `./server/logs/`.

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

```bash
# Using Google Gemini API (production)
uv run python src/main.py -c ./config/config_koji_api.yml

# Using Ollama (local testing)
uv run python src/main.py -c ./config/config_koji_local.yml
```

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
| `config_koji_api.yml` | **Production** (Google Gemini API, 9-player) |
| `config_koji_local.yml` | **Local testing** (Ollama) |
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
| `agent.num` in `config_koji_api.yml` | `9` | `5` |
| `agent.num` in `config_koji_local.yml` | `9` | `5` |

---

## Directory Structure

```
aiwolf/
├── config/
│   ├── config_koji_api.yml     # Production agent config
│   ├── config_koji_local.yml   # Local testing config
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
