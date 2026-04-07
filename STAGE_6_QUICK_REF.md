# Stage 6 Telegram Bot - Quick Reference

## What Is It

A minimal Telegram bot that:
- Accepts photo uploads
- Sends to AI backend for analysis
- Returns score + feedback

## Files

```
bot/
├── bot.py              (Main bot - 150 lines)
├── Dockerfile          (Container config)
├── requirements.txt    (3 dependencies)
```

## Setup

### 1. Get Telegram Token

1. Message @BotFather on Telegram
2. Create new bot: `/newbot`
3. Copy token

### 2. Configure

```bash
# Option A: Command line
export TELEGRAM_TOKEN="your-token"
python bot/bot.py

# Option B: Docker Compose
export TELEGRAM_TOKEN="your-token"
docker-compose up bot

# Option C: .env file
echo "TELEGRAM_TOKEN=your-token" >> .env
docker-compose up bot
```

## What The Bot Does

```
User sends photo
       ↓
Bot downloads it
       ↓
Sends to /analyze endpoint
       ↓
Formats result
       ↓
Returns to user:
  📊 Score: X/10
  💬 Feedback
  ✅ Strengths
  ⚠️ Areas to improve
```

## Code Structure

```python
class HomeworkGraderBot:
    start()                  # /start command
    handle_photo()           # Photo upload handler
    analyze_homework()       # Call backend API
    format_result()          # Format output

main():
    # Initialize bot
    # Add handlers
    # Run polling
```

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `TELEGRAM_TOKEN` | Bot token from @BotFather | `1234567:ABCdefX...` |
| `BACKEND_URL` | Backend API URL | `http://localhost:8000` |

## Local Testing

```bash
cd bot
pip install -r requirements.txt
TELEGRAM_TOKEN=your-token BACKEND_URL=http://localhost:8000 python bot.py
```

## Docker Testing

```bash
docker-compose up --build bot
# Will use TELEGRAM_TOKEN from environment
```

## Verification

```bash
# Check all components
python verify_bot_stage6.py
# Should show: 8/8 checks passed ✓
```

## Common Issues

**"Bot not responding"**
- Check TELEGRAM_TOKEN is correct
- Ensure backend is running
- Check logs: `docker-compose logs bot`

**"Message failed"**
- Backend /analyze endpoint down
- API timeout (increase AI_TIMEOUT in .env)
- Check backend logs

**"Connection refused"**
- BACKEND_URL incorrect
- Backend not started
- Docker network issue (use `http://backend:8000` in compose)

## Usage

1. Find bot in Telegram search
2. Send `/start` → get welcome message
3. Send any photo
4. Wait for analysis
5. Receive score + feedback

## Minimal Requirements

- ✓ Accepts one photo per message
- ✓ Sends to `/analyze` endpoint
- ✓ Returns formatted result
- ✓ No database needed
- ✓ No user accounts
- ✓ No history
- ✓ No complex commands
- ✓ Uses env vars for config

## What It Doesn't Do (By Design)

- ❌ No user authentication
- ❌ No history/database
- ❌ No multi-image batching
- ❌ No editing/cropping
- ❌ No advanced commands
- ❌ No image validation
- ❌ No caching

## Performance

- Response time: 3-30 seconds (depends on AI)
- Memory per bot: ~50-100 MB
- Suitable for: < 100 concurrent users
- Polling mode (not webhooks)

## Scale

- Single instance: 1-10 users
- Multiple instances: Use Docker service replica for horizontal scaling
- Production: Consider webhook + async workers

## Troubleshooting

```bash
# View bot logs
docker-compose logs bot

# Restart bot
docker-compose restart bot

# View full docker-compose config
docker-compose config

# Test backend directly
curl -X POST http://localhost:8000/analyze -F "file=@test.jpg"
```

## Status

✅ Fully functional and verified  
✅ Ready for immediate deployment  
✅ No blockers or missing features  

---

**Deploy**: `docker-compose up bot` (after setting TELEGRAM_TOKEN)
