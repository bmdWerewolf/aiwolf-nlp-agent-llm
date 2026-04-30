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

### Memory config

The `memory` block in each agent config controls compact game memory. It is
used by `src/agent/agent.py` before normal LLM requests.

```yaml
memory:
  enabled: true
  type: 0
  keep_llm_turns: 2
  summary_max_words: 180
  summary_input_max_events: 80
  rolling_summary:
    buffer_size: 5
  game_state:
    suspicion_decay: 0.1
  belief_reflexion:
    reflexion_interval: 1
```

Field meanings:

- `enabled`: turns memory on or off.
- `keep_llm_turns`: keeps only the latest N normal Human/AI turns in
  `llm_message_history`; older game context is carried by memory.
- `summary_max_words`: asks the LLM to summarize each completed day within this
  word limit. The code does not truncate the summary; if it is too long, it asks
  the LLM to compress it again.
- `summary_input_max_events`: limits how many recent talk/whisper events from
  the day are sent to the summary call.
- `rolling_summary.buffer_size`: fallback raw-event buffer used when an LLM
  summary is unavailable.
- `game_state.suspicion_decay`: lowers the weight of older suspicion signals.
- `belief_reflexion.reflexion_interval`: reserved for future belief-reflection
  logic.

Runtime behavior:

- On `INITIALIZE`, memory is reset for the new game.
- On each `DAILY_FINISH`, the agent summarizes that full day with the LLM.
- The memory prompt does not ask the LLM to summarize system rules.
- Every later request receives a compact `Game Memory` section with valid
  players, alive/dead players, role strategy, LLM round summaries, and rated
  suspicion or target priority.
- The valid player list is generated from the server state, so names not in the
  game should be treated as fake or irrelevant.
- For `WEREWOLF` and `POSSESSED`, ratings mean target priority for the agent's
  win condition; for village-side roles, ratings mean werewolf suspicion.

If timeouts are tight, reduce memory cost:

```yaml
memory:
  keep_llm_turns: 1
  summary_max_words: 120
  summary_input_max_events: 40
```

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
