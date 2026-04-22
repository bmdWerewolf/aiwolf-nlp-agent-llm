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

# Install dependencies
uv sync

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

## Evaluation & Judge Workflow

After running a game, use the LLM-as-a-judge pipeline to score player performance.

### Build judge packets (without calling LLM)

Extract and structure game logs into prompt-ready bundles:

```bash
python -m evaluate.build_judge_packets \
  --log server/logs/game/1773290733_bmd_1x_bmd_2x_bmd_3x_bmd_4x_bmd_5x_bmd_6x_bmd_7x_bmd_8x_bmd_9x.log \
  --json server/logs/json/1773290733_bmd_1x_bmd_2x_bmd_3x_bmd_4x_bmd_5x_bmd_6x_bmd_7x_bmd_8x_bmd_9x.json \
  --out evaluate/out/sample \
  --write-prompts
```

### Run the judge end-to-end

Score each player using the configured LLM (Gemini, OpenAI, etc.):

```bash
python -m evaluate.run_judge \
  --config config/config_gemini_jp.yml \
  --log server/logs/game/1773290733_bmd_1x_bmd_2x_bmd_3x_bmd_4x_bmd_5x_bmd_6x_bmd_7x_bmd_8x_bmd_9x.log \
  --json server/logs/json/1773290733_bmd_1x_bmd_2x_bmd_3x_bmd_4x_bmd_5x_bmd_6x_bmd_7x_bmd_8x_bmd_9x.json \
  --out evaluate/out/judge_run
```

### Dry run (test without calling LLM)

```bash
python -m evaluate.run_judge \
  --config config/config_gemini_jp.yml \
  --log server/logs/game/1773290733_bmd_1x_bmd_2x_bmd_3x_bmd_4x_bmd_5x_bmd_6x_bmd_7x_bmd_8x_bmd_9x.log \
  --json server/logs/json/1773290733_bmd_1x_bmd_2x_bmd_3x_bmd_4x_bmd_5x_bmd_6x_bmd_7x_bmd_8x_bmd_9x.json \
  --out evaluate/out/dry_run \
  --dry-run
```

### Scoring rubric

The judge evaluates players across two layers:

**Validity Layer**
- `anti_hallucination_penalty` — penalizes factually incorrect statements
- `rules_compliance_penalty` — penalizes rule violations

**Quality Layer**
- `strategy_quality_score` — game strategy effectiveness
- `role_consistency_score` — consistency with claimed role
- `teamplay_score` — team coordination (alignment, signals, voting, role awareness)

See `evaluate/README.md` for full pipeline details.

---

## Game Simulation

Run Monte Carlo simulations to analyze win rates and game dynamics:

```bash
python simulation.py
```

This simulates 50,000 games and reports:
- Average game length (in days)
- Villager win rate
- Werewolf win rate

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
├── evaluate/
│   ├── run_judge.py            # Judge execution CLI
│   ├── build_judge_packets.py  # Bundle builder CLI
│   ├── judge_schema.json       # Judge output schema
│   ├── rubric.md               # Scoring rubric
│   ├── parser.py               # Game log parser
│   ├── packet_builder.py       # Bundle generator
│   ├── templates/              # Jinja2 prompt templates
│   ├── README.md               # Detailed pipeline docs
│   └── out/                    # Judge outputs
├── simulation.py               # Monte Carlo game simulator
├── Dockerfile                  # Agent Docker image
├── docker-compose.yml          # Docker Compose
└── pyproject.toml              # Dependency definitions
```
