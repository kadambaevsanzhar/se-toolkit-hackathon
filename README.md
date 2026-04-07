# AI Homework Photo Feedback Checker

A minimal full-stack application that analyzes homework photos and provides AI-powered feedback with suggested scores.

## Features

- **Web UI**: Upload homework photos via React frontend
- **Telegram Bot**: Send photos directly to Telegram for instant analysis
- **AI Analysis**: Integration with Qwen API for image analysis
- **Result Storage**: PostgreSQL persistence of submissions and results
- **Docker Compose**: Full local development environment

## Stack

- **Backend**: FastAPI + SQLAlchemy + Pydantic
- **Frontend**: React + Vite
- **Database**: PostgreSQL
- **Runtime**: Docker Compose

## Prerequisites

- Docker and Docker Compose
- Running Qwen API v1 endpoint (qwen-code-api service)
- Valid API key for authentication

## Getting Started with Real Qwen API

### Option 1: Local Deployment (Recommended for Development)

1. **Deploy qwen-code-api locally**

```bash
# Clone qwen-code-api repository
git clone https://github.com/QwenLM/qwen-code-api.git
cd qwen-code-api

# Build and run with Docker
docker-compose up -d

# API will be available at http://localhost:42006/v1
# API key: my-secret-qwen-key (from docker-compose.yml)
```

2. **Configure backend**

```bash
# In backend/.env (or .env)
AI_BASE_URL=http://localhost:42006/v1
# If running backend inside Docker Compose and qwen-code-api on the host, use host.docker.internal:
# AI_BASE_URL=http://host.docker.internal:42006/v1
AI_API_KEY=my-secret-qwen-key
AI_MODEL=qwen3-coder-plus
AI_MAX_SCORE=10
```

### Option 2: Remote VM Deployment

If running qwen-code-api on another VM:

```bash
# In backend/.env
AI_BASE_URL=http://<VM_IP>:42006/v1
AI_API_KEY=my-secret-qwen-key
AI_MODEL=qwen3-coder-plus
```

### Option 3: Cloud-Hosted Qwen API

If using cloud Qwen service:

```bash
# Update endpoint and key with cloud provider credentials
AI_BASE_URL=https://your-cloud-provider/v1
AI_API_KEY=<your_cloud_api_key>
AI_MODEL=qwen3-coder-plus
```

## Quick Start

### 1. Clone the repository

```bash
git clone <repo-url>
cd ai-grader
```

### 2. Set up environment

```bash
cp backend/.env.example backend/.env
```

Then edit `backend/.env` with your Qwen API configuration (see above).

### 3. Start services

```bash
docker-compose up --build
```

Services will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Database: localhost:5432

### 4. Test upload

1. Open http://localhost:3000
2. Upload a homework image
3. See the result with suggested score and feedback

## Development

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

- `POST /analyze` - Upload homework image and receive immediate AI feedback
- `POST /submit` - Upload homework image for storage and later retrieval
- `GET /result/{submission_id}` - Get submission result
- `GET /history` - Get list of all stored submissions
- `GET /health` - Health check

## Environment Variables

Backend configuration in `backend/.env`:

### AI Service (Real Qwen API v1)
- `AI_BASE_URL` — Base URL of Qwen API v1 endpoint (e.g., `http://localhost:42006/v1`)
- `AI_API_KEY` — API key for authentication
- `AI_MODEL` — Model name (default: `qwen3-coder-plus`)
- `AI_MAX_SCORE` — Maximum homework score (default: `10`)
- `AI_TIMEOUT` — API request timeout in seconds (default: `30`)

### Database
- `DATABASE_URL` — PostgreSQL connection string (auto-fallback to SQLite for local dev)

### Telegram Bot
- `TELEGRAM_TOKEN` — Telegram bot token
- `BACKEND_URL` — Backend service URL (default: `http://backend:8000` in Docker Compose)

### Application
- `MAX_UPLOAD_SIZE_MB` — Maximum upload file size (default: `10`)
- `LOG_LEVEL` — Logging level (default: `INFO`)
- `VITE_API_URL` — Frontend build-time backend URL for Docker Compose (default: `http://backend:8000`)

## Bot Service

To run the Telegram bot locally:

```bash
cd bot
pip install -r requirements.txt
TELEGRAM_TOKEN=your-token BACKEND_URL=http://localhost:8000 python bot.py
```

To run the bot with Docker Compose:

```bash
docker compose up --build bot
```

## License

MIT
