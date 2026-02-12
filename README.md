# 🎩 RH Quiz

A Red Hat-themed quiz application that generates multiple-choice quizzes from any subject using an LLM (Ollama), scores answers with custom rules, and maintains a live leaderboard.

![Red Hat](app/static/logo.png)

## Features

- **LLM-powered quiz generation** — Enter any subject, get 3 tailored questions
- **Smart scoring** — Correct (+10), Obviously Wrong (-5), Doubtful (0)
- **2× multiplier** — Red Hat & OpenShift topics earn double points
- **Live leaderboard** — Auto-refreshing every 30 seconds with countdown
- **Mobile-first UI** — Designed for phones, works everywhere
- **Cookie-based identity** — No login required, just enter your name
- **Admin controls** — Leaderboard reset with token auth

## Architecture

```
┌───────────────────────────┐
│    Docker Container        │
│  ┌─────────────────────┐  │
│  │  FastAPI Backend     │  │
│  │  + Static Frontend   │  │
│  └──────────┬──────────┘  │
│             │              │
│  📁 SQLite (/data/quiz.db)│
└──────────────┬────────────┘
               │ HTTP
               ▼
        ┌─────────────┐
        │   Ollama     │
        │  (external)  │
        └─────────────┘
```

## Quick Start

### 1. Configure

```bash
cp .env.example .env
# Edit .env with your Ollama endpoint
```

### 2. Run with Docker Compose

```bash
docker compose up -d --build
```

### 3. Open

Navigate to `http://localhost:8000`

## Configuration

All config is via `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://192.168.1.153:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `mistral` | LLM model to use |
| `DB_PATH` | `/data/quiz.db` | SQLite database path |
| `APP_HOST` | `0.0.0.0` | Bind address |
| `APP_PORT` | `8000` | Bind port |
| `ADMIN_TOKEN` | `change-me-to-a-secret` | Token for leaderboard reset |

## Subject Multiplier

Subjects matching entries in `subjects.yaml` get a 2x score multiplier. Edit the YAML to add/remove subjects. Matching is fuzzy — close matches count.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/user/register` | Register/find user |
| `GET` | `/api/user/{id}` | Get user |
| `POST` | `/api/quiz/generate` | Generate quiz from subject |
| `POST` | `/api/quiz/submit` | Submit answers, get score |
| `GET` | `/api/leaderboard` | Get leaderboard |
| `DELETE` | `/api/leaderboard/reset` | Reset leaderboard (admin) |
| `GET` | `/health` | Health check |

## Development

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Deploy to OpenShift

Manifests are in `openshift/`. Make sure you're logged in and have your project selected:

```bash
oc login <cluster>
oc project <your-namespace>

# Option A: Use the helper script
cd openshift/
chmod +x deploy-openshift.sh
./deploy-openshift.sh

# Option B: Manual
oc apply -f openshift/
oc start-build rh-quiz --from-dir=. --follow
```

Ensure your cluster can reach the Ollama endpoint. Edit `openshift/01-secret.yaml` before applying if you need to change the Ollama URL, model, or admin token.

## License

Internal use.
