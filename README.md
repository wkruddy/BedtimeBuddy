# BedtimeBuddy

Agentic orchestration for generating children's bedtime stories (Phase 0) and, later, publishable children's books.

## Agent onboarding / project context

> **For Cursor agents:** read this section first to get up to speed on purpose, architecture, and locked decisions.

### Purpose and current phase

| | |
|---|---|
| **Project purpose** | Agentic orchestration for bedtime stories (Phase 0) and a children's book pipeline (Phase 2+) |
| **Current phase** | **Phase 0 complete** — bedtime story generator via Slack + CLI |
| **Dev machine** | Local Mac — editing in Cursor only; **not** the runtime host |
| **Runtime host** | AI Compute LLM VM (homelab) — PostgreSQL, always-on Slack bot, Ollama proximity, future ComfyUI |

### Architecture

```
Slack / CLI
    └── Bedtime Brain (orchestrator)
            └── Story Generation agent
                    ├── story-build skill (Ollama)
                    └── web-research skill (optional HTTP search or stub)
            └── story-persist → PostgreSQL
```

- **BedtimeBuddy Brain** is the orchestrator; it delegates to the **Story Generation** agent, which uses **research** and **story-build** skills.
- **Research** is implemented as a skill on Story Generation (not a separate top-level agent).
- **IP policy** is orchestrator-enforced: `fan_fiction` for bedtime stories (named characters OK); `original_only` for commercial books (Phase 2+).

### Data model and Slack

**Multi-tenant PostgreSQL schema:** `workspaces` → `households` → `children_profiles` → `story_sessions`

- Each Slack user maps to one household within a workspace. Stories are isolated per household.
- **Slack is parent-only.** Commands:
  - `/bedtime setup` — onboarding (kid count → name → age → interests)
  - `/bedtime story` — pick child, duration, format, topics → generate
- Phase 1 targets multi-household / neighborhood Slack deployment design.

### Ollama homelab

- Default API base: `http://ai.homelab.internal:11434`
- Models (see `.continue/agents/local-config.yaml`):
  - **Chat / story generation:** `qwen3.6:35b`
  - **Autocomplete (dev):** `qwen2.5-coder:3b`
  - **Embeddings:** `nomic-embed-text`

### Key paths

| Path | Role |
|------|------|
| `souls/` | SOUL tone / safety markdown files |
| `bedtimebuddy/` | Application package (agents, skills, Slack, DB, CLI) |
| `alembic/` | Database migrations |
| `docker-compose.yml` | PostgreSQL service definition |
| `.continue/agents/local-config.yaml` | Continue/Cursor Ollama model config |

### Phased roadmap

| Phase | Status | Scope |
|-------|--------|-------|
| **0** | Done | Bedtime stories via Slack + CLI, PostgreSQL multi-tenant schema |
| **1** | Next | Story history, preferences memory, neighborhood Slack deploy |
| **2+** | Planned | Book pipeline, ComfyUI illustration, KDP publishing |

### Locked decisions

- **PostgreSQL**, not SQLite — multi-tenant production schema from day one
- **Research as a skill** on Story Generation, not a standalone agent
- **Rhyming default** for commercial books (Phase 2+)
- **ComfyUI workflows TBD** by Illustrator Agent when that phase starts

---

## Development vs deployment

| Environment | Role |
|-------------|------|
| **Local Mac** | Development and editing in Cursor only — **not** the production runtime |
| **AI Compute LLM VM (homelab)** | Primary deployment target: PostgreSQL (`docker-compose`), always-on Slack bot, Ollama proximity, future ComfyUI |

**GitHub workflow:** push from Mac → clone or pull on VM → configure `.env` → migrate → run (CLI test, then Slack via systemd).

---

## Architecture (runtime)

```
Slack / CLI
    └── Bedtime Brain (orchestrator)
            └── Story Generation agent
                    ├── story-build skill (Ollama)
                    └── web-research skill (optional HTTP search or stub)
            └── story-persist → PostgreSQL
```

**Multi-tenant model:** `workspaces` → `households` → `children_profiles` → `story_sessions`

Each Slack user maps to one household within a workspace. Stories are isolated per household.

**IP policy:** Bedtime stories use `fan_fiction` (named characters OK). Book pipeline (Phase 2+) will use `original_only`.

---

## Prerequisites

- Python 3.11+
- Docker (for PostgreSQL on the VM)
- Ollama reachable at `OLLAMA_BASE_URL` (see [Environment variables](#environment-variables))
- Slack app with bot + socket mode tokens (optional for CLI-only dev on Mac)

---

## Quick start (local Mac — dev only)

Use this flow on your Mac to iterate in Cursor. Production runs on the AI Compute VM (see [Deployment](#deployment-ai-compute-vm)).

### 1. Start PostgreSQL

```bash
docker compose up -d
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum DATABASE_URL should match docker-compose
```

### 3. Install package

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 4. Run migrations

```bash
bedtimebuddy db migrate
# or: alembic upgrade head
```

### 5. Generate a story (CLI — no Slack needed)

```bash
bedtimebuddy story generate --duration 5 --format detailed --topics "Bluey, beach"
```

### 6. Run Slack bot (socket mode)

Create a Slack app with:
- Slash command `/bedtime`
- Bot scopes: `commands`, `chat:write`, `im:history`, `im:write`
- Socket Mode enabled

```bash
bedtimebuddy slack run
```

**Slack commands:**
- `/bedtime setup` — onboarding (kid count → name → age → interests)
- `/bedtime story` — pick child, duration, format, topics → generate

---

## Deployment (AI Compute VM)

The homelab VM is the primary runtime. Bootstrap once, then pull updates after each push from Mac.

### VM bootstrap (first run)

Replace paths and repo URL as needed for your setup.

```bash
# 1. Clone (or pull) the repo
git clone https://github.com/YOUR_ORG/BedtimeBuddy.git
cd BedtimeBuddy

# 2. Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 3. Environment
cp .env.example .env
# Edit .env on the VM — see Environment variables below

# 4. PostgreSQL
docker compose up -d

# 5. Wait for Postgres, then migrate
bedtimebuddy db migrate

# 6. Smoke-test CLI (no Slack required)
bedtimebuddy story generate --duration 3 --format short --topics "stars, moon"

# 7. Manual Slack test (optional before systemd)
bedtimebuddy slack run
# Ctrl+C when verified; use systemd for always-on (below)
```

### OLLAMA_BASE_URL on the VM

| Setup | Value |
|-------|-------|
| Ollama on **same VM** as BedtimeBuddy | `http://127.0.0.1:11434` |
| Ollama on **separate homelab host** | `http://ai.homelab.internal:11434` |

Set `OLLAMA_MODEL` to match a model pulled on that host (default: `qwen3.6:35b`).

### systemd unit (always-on Slack bot)

Create `/etc/systemd/system/bedtimebuddy-slack.service` (adjust `User`, paths, and repo location):

```ini
[Unit]
Description=BedtimeBuddy Slack bot (socket mode)
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=bedtimebuddy
WorkingDirectory=/opt/BedtimeBuddy
EnvironmentFile=/opt/BedtimeBuddy/.env
ExecStart=/opt/BedtimeBuddy/.venv/bin/bedtimebuddy slack run
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable bedtimebuddy-slack
sudo systemctl start bedtimebuddy-slack
sudo systemctl status bedtimebuddy-slack
```

Logs: `journalctl -u bedtimebuddy-slack -f`

### VM updates (after Mac push)

```bash
cd /opt/BedtimeBuddy   # or your clone path
git pull
source .venv/bin/activate
pip install -e .
bedtimebuddy db migrate
sudo systemctl restart bedtimebuddy-slack
```

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | **Yes** | PostgreSQL connection string (must match `docker-compose` credentials on VM) |
| `OLLAMA_BASE_URL` | **Yes** | Ollama API base — `http://127.0.0.1:11434` (same VM) or `http://ai.homelab.internal:11434` (remote homelab host) |
| `OLLAMA_MODEL` | No | Model name (default: `qwen3.6:35b`) |
| `SLACK_BOT_TOKEN` | **For Slack** | `xoxb-...` bot token |
| `SLACK_APP_TOKEN` | **For Slack** | `xapp-...` app-level token (socket mode) |
| `WEB_SEARCH_URL` | No | HTTP search endpoint for research skill; graceful stub used if unset |
| `SOULS_DIR` | No | Path to SOUL markdown files (default: `souls`) |

Copy from template: `cp .env.example .env`. Never commit `.env` (see [GitHub push checklist](#github-push-checklist)).

---

## GitHub push checklist

### Before pushing from Mac

- [ ] **Do not commit `.env`** — secrets stay on each machine only
- [ ] `.gitignore` already excludes `.env`, `.envrc`, and typical secret paths
- [ ] Run local smoke tests if you changed story/Slack logic

### Initial push (Mac)

```bash
git init   # if not already a repo
git remote add origin https://github.com/YOUR_ORG/BedtimeBuddy.git
git add .
git status   # confirm .env is NOT staged
git commit -m "Initial BedtimeBuddy Phase 0"
git push -u origin main
```

### First run on VM (after clone)

1. Clone repo (see [VM bootstrap](#vm-bootstrap-first-run))
2. `cp .env.example .env` and fill in VM-specific values (`DATABASE_URL`, `OLLAMA_BASE_URL`, Slack tokens)
3. `docker compose up -d` → `bedtimebuddy db migrate`
4. CLI smoke test → install systemd unit → `enable` / `start`

---

## Project layout

```
bedtimebuddy/
  agents/brain.py          # Orchestrator + Story Generation agent
  skills/                  # story-build, web-research
  services/                # Ollama, persist, tenant resolution
  slack/                   # Socket-mode bot + onboarding/story flows
  db/models.py             # SQLAlchemy models
  schemas/story.py         # StoryRequest, StoryResult
  cli.py                   # Typer CLI
souls/                     # SOUL tone files
alembic/                   # Database migrations
docker-compose.yml         # PostgreSQL
```

---

## Web research skill

The Story Generation agent includes a research skill. If `WEB_SEARCH_URL` is set, it GETs `?q=<query>` and uses the JSON response. Otherwise it returns age-appropriate guidance stubs (documented in code) so generation still works offline.

---

## Phase roadmap

- **Phase 0** (complete): Bedtime stories via Slack + CLI, PostgreSQL multi-tenant schema
- **Phase 1**: Story history, preferences memory, neighborhood Slack deploy
- **Phase 2+**: Book pipeline (`original_only` IP), ComfyUI illustration, KDP publishing
