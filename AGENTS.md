# AGENTS.md

## Project
AI Homework Photo Feedback Checker

## Objective
Build a minimal but reliable full-stack application that:
1. accepts one homework photo from web UI,
2. sends it to an AI analysis service,
3. returns a suggested score and short feedback,
4. validates the returned result,
5. stores submissions and results,
6. shows the result in the UI,
7. supports a Telegram bot in a later phase,
8. runs locally and via Docker Compose.

## Product scope

### MVP must include
- Web upload of one image
- Backend endpoint for image submission
- AI analysis wrapper
- Suggested score
- Short feedback
- Validation layer
- Result page
- PostgreSQL persistence
- Docker Compose
- Basic README

### V2 may include
- Telegram bot
- History page
- Rubric input
- Better result formatting
- Error handling improvements
- Deployment hardening

## Non-goals
- No auth
- No user accounts
- No advanced OCR pipeline
- No complex rubric editor
- No teacher dashboard
- No multi-image submissions
- No premature abstractions
- No microservices beyond what is explicitly requested

## Required stack
- Backend: FastAPI + Pydantic + SQLAlchemy
- Frontend: React + Vite
- Database: PostgreSQL
- Bot: Python Telegram bot
- Runtime: Docker Compose

## Repository rules
- Keep architecture simple and reviewable
- Prefer explicit code over abstractions
- Keep files small
- Use environment variables for secrets
- Add comments only where needed
- Keep API responses typed and stable
- Use clear folder names
- Do not add unnecessary dependencies
- Do not refactor unrelated code

## Data contract for AI result
The backend should normalize AI output to this shape:

{
  "suggested_score": 0,
  "max_score": 10,
  "short_feedback": "",
  "strengths": [],
  "mistakes": [],
  "improvement_suggestion": "",
  "validator_flags": []
}

## Validation rules
- suggested_score must be numeric
- suggested_score must be between 0 and max_score
- short_feedback must be non-empty
- strengths and mistakes may be empty in MVP but should be arrays
- improvement_suggestion should be present in V2
- invalid AI responses must be normalized or rejected with a clear error

## Engineering workflow
For every stage:
1. Inspect the current repo
2. State the plan briefly
3. Make minimal changes
4. Run relevant checks
5. Fix failures
6. Report exactly what changed
7. Report remaining risks

## Required checks after changes
### Backend changes
- run backend tests if present
- run FastAPI import check
- run linter if configured

### Frontend changes
- install dependencies if needed
- run build
- run linter if configured

### Compose changes
- validate docker compose file
- ensure services reference the right env vars

## Definition of done
A stage is done only if:
- code is written
- relevant checks pass
- there is no obvious broken import
- there is no placeholder left in the main path
- the change is documented in a short report

## Self-check protocol
Before claiming success, always verify:
- the code runs
- the API contract matches the frontend expectations
- required environment variables are documented
- Docker files are syntactically valid
- README instructions are consistent with the actual project

## Stop conditions
If blocked by a missing secret, unsupported model, or impossible ambiguity:
- do not continue guessing
- write a concise blocker report
- list the exact missing item
- propose the smallest safe fallback

## Output style
After each task, report:
1. Files changed
2. Commands run
3. Check results
4. Remaining risks
5. Next recommended step