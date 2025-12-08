# AIWolf NLP Agent - Quick Start Guide

This guide will help you run the AIWolf game with LLM-powered agents in just a few steps.

## Prerequisites

- **Docker Desktop** installed and running
- **API Key** from one of:
  - [OpenRouter](https://openrouter.ai/) (recommended, supports multiple models)
  - [OpenAI](https://platform.openai.com/)
  - [Google AI](https://aistudio.google.com/)

## Quick Start (3 Steps)

### Step 1: Create Environment File

Copy the template and add your API key:

```bash
# Windows (PowerShell)
copy env.example .env

# Linux / Mac
cp env.example .env
```

Then edit `.env` and add your API key:

```
OPENAI_API_KEY=sk-or-v1-your-actual-api-key-here
```

> **Note**: Even if using OpenRouter, the variable name must be `OPENAI_API_KEY`.

### Step 2: Start All Services

```bash
docker-compose up --build
```

This will:
1. Build the Server and Agent images
2. Start the game server on port 8080
3. Connect 5 AI agents to play the game

### Step 3: Watch the Game!

You'll see real-time logs in the terminal. Game logs are saved in:
- `./log/` - Agent decision logs
- `./server/logs/game/` - Complete game records

## Common Commands

| Action | Command |
|--------|---------|
| Start (first time) | `docker-compose up --build` |
| Start (after first time) | `docker-compose up` |
| Stop | `Ctrl+C` or `docker-compose down` |
| View logs | `docker-compose logs -f` |
| Rebuild after code changes | `docker-compose up --build` |

## Configuration

### Change LLM Model

Edit `config/config_opr.yml`:

```yaml
openai:
  model: openai/gpt-3.5-turbo  # Change this
  temperature: 0.7
  base_url: https://openrouter.ai/api/v1
```

Available models on OpenRouter:
- `openai/gpt-3.5-turbo` (fast, cheap)
- `openai/gpt-4` (better reasoning)
- `anthropic/claude-3-haiku` (fast)
- `google/gemini-pro`

### Change Number of Games

Edit `server/default_5.yml`:

```yaml
matching:
  game_count: 5  # Number of games to play
```

## Troubleshooting

### Error: "port is already allocated"

Another container is using port 8080. Stop it first:

```bash
docker ps                    # Find the container
docker rm -f <container_id>  # Remove it
docker-compose up
```

### Error: "OPENAI_API_KEY not set"

Make sure `.env` file exists in the project root (not in `config/` folder):

```bash
# Check if .env exists
ls .env

# If not, create it
copy env.example .env
# Then edit and add your API key
```

### Error: "Connection refused"

The server might not be ready yet. Wait a few seconds and try again, or restart:

```bash
docker-compose down
docker-compose up
```

## Project Structure

```
aiwolf-nlp-agent-llm/
├── .env                 # Your API keys (create from env.example)
├── docker-compose.yml   # One-click startup config
├── Dockerfile           # Agent container definition
├── config/
│   └── config_opr.yml   # LLM and game settings
├── server/
│   ├── Dockerfile       # Server container definition
│   └── default_5.yml    # Server settings
├── src/                 # Agent source code
└── log/                 # Game logs (auto-generated)
```

## Development Mode

Source code is mounted as a volume, so you can:
1. Edit files in `src/` or `config/`
2. Stop the container (`Ctrl+C`)
3. Restart without rebuilding: `docker-compose up`

For Python code changes, no rebuild is needed!

## Need Help?

- Check the logs: `docker-compose logs -f agent`
- View server status: `docker-compose logs -f server`
- Read game results: `./server/logs/game/`

