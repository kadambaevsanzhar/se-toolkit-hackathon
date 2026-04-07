# QUICK DEPLOYMENT GUIDE

## 5-Minute Setup

### Step 1: Prepare Credentials
```bash
# Get these from your Qwen API account
export AI_API_KEY="your_bearer_token"
export AI_BASE_URL="http://10.93.26.140:42006/v1"  # or your endpoint
export AI_MODEL="qwen-vl-plus"
```

### Step 2: Create .env File
```bash
cat > .env << EOF
# AI Configuration
AI_API_KEY=${AI_API_KEY}
AI_BASE_URL=${AI_BASE_URL}
AI_MODEL=${AI_MODEL}
AI_MAX_SCORE=10

# Database
DATABASE_URL=postgresql://postgres:homework123@db:5432/homework_grader

# Frontend
VITE_API_URL=http://backend:8000

# Optional: Telegram Bot
TELEGRAM_TOKEN=your_token_here
EOF
```

### Step 3: Start Services
```bash
docker-compose up --build
```

### Step 4: Access Application
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## Verification Checklist

After starting, run these checks:

### 1. Backend Health
```bash
curl http://localhost:8000/health
# Should return: {"status":"ok"}
```

### 2. Frontend Loads
```bash
curl http://localhost:3000
# Should return HTML with "AI Homework Checker"
```

### 3. Database Connected
```bash
docker-compose exec backend python -c "from database import engine; engine.connect(); print('Database OK')"
```

### 4. Qwen API Configured
```bash
curl -X POST http://localhost:8000/analyze \
  -F "image=@/path/to/test.jpg"
# Should return JSON with score and feedback
```

---

## Troubleshooting

### Port Already in Use
```bash
# Change ports in docker-compose.yml
# Or kill existing service:
lsof -i :3000  # Find what's using port 3000
kill -9 <PID>
```

### Database Connection Failed
```bash
# Check if PostgreSQL is running
docker-compose logs db

# Or use SQLite fallback (no setup needed)
# SQLite will use grader_dev.db automatically
```

### Qwen API Returns Error
```bash
# Test credentials directly
curl -X POST ${AI_BASE_URL}/chat/completions \
  -H "Authorization: Bearer ${AI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"'${AI_MODEL}'", "messages":[{"role":"user", "content":"test"}]}'
```

### Frontend Can't Reach Backend
```bash
# Check proxy configuration
cat frontend/vite.config.js  # Should have /analyze → http://localhost:8000

# Or test API directly
curl http://localhost:8000/docs
```

---

## Production Deployment

### Recommended Setup
1. Use PostgreSQL (not SQLite)
2. Set `DATABASE_URL` to production database
3. Use environment variables for all secrets
4. Run behind reverse proxy (nginx)
5. Enable CORS if frontend on different domain
6. Use HTTPS with valid certificates

### Example Nginx Config
```nginx
server {
    listen 80;
    server_name homework-checker.example.com;
    
    location / {
        proxy_pass http://localhost:3000;
    }
    
    location /api/ {
        proxy_pass http://localhost:8000;
    }
}
```

### Docker Compose for Production
```yaml
version: '3.8'
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data
    restart: always

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://postgres:${DB_PASSWORD}@db:5432/homework_grader
      AI_API_KEY: ${AI_API_KEY}
      AI_BASE_URL: ${AI_BASE_URL}
      AI_MODEL: ${AI_MODEL}
    restart: always
    depends_on:
      - db

  frontend:
    build: ./frontend
    environment:
      VITE_API_URL: http://api.example.com
    restart: always

  bot:
    build: ./bot
    environment:
      TELEGRAM_TOKEN: ${TELEGRAM_TOKEN}
      BACKEND_URL: http://backend:8000
    restart: always
    depends_on:
      - backend

volumes:
  pg_data:
```

---

## Monitoring

### Check Service Status
```bash
docker-compose ps
```

### View Logs
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f bot
```

### Database Stats
```bash
docker-compose exec db psql -U postgres -d homework_grader -c "SELECT COUNT(*) FROM submissions;"
```

---

## Scaling

### Multiple Backend Instances
```yaml
backend:
  deploy:
    replicas: 3
  environment:
    # Same config for all instances
```

### Load Balancing
```bash
# Use docker-compose with load balancer
# Or use Kubernetes with multiple replicas
```

---

## Cleanup

### Stop All Services
```bash
docker-compose down
```

### Remove Data
```bash
docker-compose down -v
# Removes all volumes (careful - deletes database!)
```

### Remove Images
```bash
docker-compose down --rmi all
```

---

## Support

For issues:
1. Check [PROJECT_COMPLETE.md](PROJECT_COMPLETE.md)
2. Review service logs: `docker-compose logs`
3. Test components individually
4. Verify credentials and environment variables

---

**Status**: Ready to deploy ✅
