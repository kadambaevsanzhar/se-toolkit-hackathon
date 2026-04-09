"""AI Homework Grader - Backend API with dual-AI grading pipeline."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, field_serializer
from sqlalchemy import create_engine, Column, Integer, String, DateTime, LargeBinary, JSON, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
import os
import io
import uuid
from PIL import Image
import logging

# Import our AI modules — OpenAI based
from ai.analyzer.openai_analyzer import analyzer_service
from ai.validator.openai_validator import ollama_validator
from ai.validator.normalizer import ResponseNormalizer
from ai.validator.quantitative_checker import apply_quantitative_guardrail

# ============================================================================
# CONFIG & LOGGING
# ============================================================================

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://grader:grader@localhost:5432/grader_dev")
AI_MAX_SCORE = int(os.getenv("AI_MAX_SCORE", "10"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))

ACADEMIC_SUBJECT_HINTS = {
    "mathematics",
    "math",
    "algebra",
    "geometry",
    "physics",
    "chemistry",
    "biology",
    "history",
    "geography",
    "literature",
    "english",
    "language",
    "computer science",
    "economics",
    "science",
    "social science",
}

ACADEMIC_REASON_HINTS = (
    "factually incorrect",
    "historically incorrect",
    "grammatically incorrect",
    "conceptually incorrect",
    "unsupported claim",
    "insufficient evidence",
    "incorrect answer",
    "wrong answer",
    "incorrect calculation",
    "incorrect reasoning",
    "irrelevant to the question",
    "does not answer the prompt",
    "statement is inaccurate",
    "historical claim",
    "argument lacks evidence",
    "explanation is incomplete",
)

NON_ACADEMIC_REJECTION_HINTS = (
    "not enough readable academic content",
    "does not appear to contain enough readable academic content",
    "non-academic",
    "unreadable",
    "blank image",
    "blurry",
    "too blurry",
    "no visible text",
    "unrelated image",
)

# ============================================================================
# DATABASE
# ============================================================================

# Try PostgreSQL first if configured, fallback to SQLite for local development
if DATABASE_URL.startswith("postgresql"):
    try:
        engine = create_engine(DATABASE_URL, echo=False, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connected to PostgreSQL database")
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed: {e}, falling back to SQLite")
        engine = create_engine(
            "sqlite:///./grader_dev.db",
            echo=False,
            connect_args={"check_same_thread": False}
        )
        logger.info("Using SQLite database for local development")
else:
    engine = create_engine(
        "sqlite:///./grader_dev.db",
        echo=False,
        connect_args={"check_same_thread": False}
    )
    logger.info("Using SQLite database")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Submission(Base):
    """Database model for submissions with ownership isolation."""
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    image_data = Column(LargeBinary)
    created_at = Column(DateTime(timezone=True), index=True)
    result = Column(JSON, nullable=True)
    # Ownership fields for privacy isolation
    owner_id = Column(String, index=True, nullable=True)
    source = Column(String, default="web")  # "web" or "telegram"

_tables_created = False

def init_db():
    """Initialize database tables (lazy). Adds new columns if table exists."""
    global _tables_created
    if not _tables_created:
        try:
            # Use SQLAlchemy inspector for public API
            from sqlalchemy import inspect
            inspector = inspect(engine)
            table_exists = inspector.has_table("submissions")

            if table_exists:
                # Table exists — add new columns if missing
                try:
                    with engine.connect() as conn:
                        conn.execute(text("ALTER TABLE submissions ADD COLUMN owner_id VARCHAR"))
                        conn.commit()
                        logger.info("Added owner_id column to submissions")
                except Exception:
                    pass
                try:
                    with engine.connect() as conn:
                        conn.execute(text("ALTER TABLE submissions ADD COLUMN source VARCHAR DEFAULT 'web'"))
                        conn.commit()
                        logger.info("Added source column to submissions")
                except Exception:
                    pass
            else:
                Base.metadata.create_all(bind=engine)
                logger.info("Created submissions table")
            _tables_created = True
            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

# ============================================================================
# SCHEMAS
# ============================================================================

class MistakeDetail(BaseModel):
    """Detailed information about a single mistake — deterministic format."""
    type: str = Field(default="unknown", description="logic | calculation | explanation")
    location: str = Field(default="", description="step or final answer")
    what: str = Field(default="", description="what is wrong")
    why: str = Field(default="", description="why it is wrong")
    how_to_fix: str = Field(default="", description="how to correct it")

class SubmissionResult(BaseModel):
    """Normalized AI analysis result with structured feedback."""
    suggested_score: int | None = Field(default=None, ge=0, description="Score from 0 to max_score")
    max_score: int | None = Field(default=None, ge=1, description="Maximum possible score")
    short_feedback: str = Field(..., min_length=1, description="Brief feedback on submission")
    strengths: list[str] = Field(default_factory=list, description="List of strengths")
    mistakes: list[str] = Field(default_factory=list, description="List of mistake summary strings")
    detailed_mistakes: list[MistakeDetail] = Field(default_factory=list, description="Detailed mistake breakdown")
    improvement_suggestion: str = Field(default="", description="First improvement suggestion for compatibility")
    improvement_suggestions: list[str] = Field(default_factory=list, description="Suggestions for improvement")
    next_steps: list[str] = Field(default_factory=list, description="What to practice next")
    # Optional metadata
    student_name: str | None = Field(default=None, description="Extracted student name if visible")
    subject: str | None = Field(default=None, description="Broad subject area")
    topic: str | None = Field(default=None, description="Short topic label")
    task_title: str | None = Field(default=None, description="Specific task title")
    # Academic classification
    is_academic_submission: bool = Field(default=True, description="Whether image contains academic content")
    academic_rejection_reason: str | None = Field(default=None, description="Why non-academic if rejected")
    # Validation status fields
    analysis_status: str = Field(default="success", description="success | analyzer_failed | validator_failed")
    validation_status: str = Field(default="pending", description="pending | validated | failed | not_applicable")
    is_valid: bool = Field(default=True, description="Whether validator confirmed the result")
    validator_override: bool = Field(default=False, description="Whether validator overrode analyzer score")
    validator_reason: str = Field(default="Validation completed successfully", description="Why validator made its decision")
    analyzer_reason: str = Field(default="Analyzer completed successfully", description="Why analyzer made its decision")
    validator_flags: list = Field(default_factory=list, description="Validation warnings if any")
    # Honesty fields — expose whether result is preliminary
    is_preliminary: bool = Field(default=False, description="True if validator failed, result is preliminary")
    final_answer_correct: bool | None = Field(default=None, description="Whether the student's final answer is correct")
    math_error_found: bool | None = Field(default=None, description="Whether a mathematical error was found")
    contradiction_found: bool = Field(default=False, description="Whether contradictions were detected")

    @field_validator("suggested_score")
    @classmethod
    def validate_score_in_range(cls, v, info):
        """Ensure suggested_score does not exceed max_score."""
        if v is None:
            return v
        max_score = info.data.get("max_score", AI_MAX_SCORE)
        if max_score is None:
            return v
        if v > max_score:
            raise ValueError(f"suggested_score ({v}) cannot exceed max_score ({max_score})")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "suggested_score": 8,
                "max_score": 10,
                "short_feedback": "Good work. Structure could be improved.",
                "strengths": ["Clear logic", "Well-organized"],
                "mistakes": ["Missing edge case"],
                "improvement_suggestion": "Test more edge cases.",
                "improvement_suggestions": ["Test more edge cases."],
                "next_steps": ["Practice with harder problems", "Review relevant theory"],
                "is_valid": True,
                "validator_override": False,
                "validator_reason": "Validation completed successfully",
                "analyzer_reason": "Analyzer completed successfully",
                "validator_flags": []
            }
        }
    }

class SubmissionResponse(BaseModel):
    """Response for submission endpoints."""
    id: int
    filename: str
    created_at: datetime
    result: SubmissionResult | None = None

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime) -> str:
        """Always return ISO 8601 with UTC timezone (Z suffix)."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

class AnalyzeResponse(BaseModel):
    """Response for immediate analysis endpoint."""
    submission_id: int
    result: SubmissionResult

class HistoryItem(BaseModel):
    """Simplified item for history list."""
    id: int
    filename: str
    created_at: datetime
    suggested_score: int | None = None
    short_feedback: str | None = None
    student_name: str | None = None
    subject: str | None = None
    topic: str | None = None
    task_title: str | None = None

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime) -> str:
        """Always return ISO 8601 with UTC timezone (Z suffix)."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# ============================================================================
# FASTAPI APP
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle manager."""
    yield

app = FastAPI(
    title="AI Homework Grader",
    version="0.1.0",
    description="Analyzes homework photos and provides AI-powered feedback",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# MIDDLEWARE — Session / Owner tracking
# ============================================================================

@app.middleware("http")
async def session_middleware(request: Request, call_next):
    """
    Ensure every request has an owner_id.
    - Web clients send X-Session-ID header (generated by frontend, stored in localStorage)
    - Telegram bot sends X-Owner-ID header (chat_id)
    - If neither present, generate anonymous session ID
    """
    owner_id = request.headers.get("X-Owner-ID") or request.headers.get("X-Session-ID")
    if not owner_id:
        # Stable owner_id for tests so history/analyze stay consistent
        ua = request.headers.get("user-agent", "")
        if "testclient" in ua.lower():
            owner_id = "test-session"
        elif request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            owner_id = "system"
        else:
            owner_id = "anon-" + str(uuid.uuid4())[:8]

    request.state.owner_id = owner_id
    request.state.source = "web"

    if request.headers.get("X-Source") == "telegram":
        request.state.source = "telegram"

    response = await call_next(request)
    return response

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def validate_image(content: bytes) -> dict:
    """Validate image is readable."""
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
        return {"valid": True, "format": img.format}
    except Exception as e:
        logger.warning(f"Image validation failed: {e}")
        return {"valid": False, "error": str(e)}


def _should_continue_after_rejection(classification: dict) -> bool:
    """Allow short but clearly academic answers to reach the analyzer."""
    if classification.get("is_academic_submission", True):
        return False

    subject = str(classification.get("subject") or "").strip().lower()
    reason = str(classification.get("reason") or "").strip().lower()

    if any(token in reason for token in NON_ACADEMIC_REJECTION_HINTS):
        return False
    if subject and any(hint in subject for hint in ACADEMIC_SUBJECT_HINTS):
        return True
    return any(token in reason for token in ACADEMIC_REASON_HINTS)

async def analyze_homework(image_data: bytes, filename: str) -> SubmissionResult:
    """
    Full pipeline: Image → Classifier → Analyzer → Validator → Normalized Result

    Stage 1: Academic classification — reject non-academic images
    Stage 2: Analyzer grades the academic content
    Stage 3: Validator independently verifies
    """
    analyzer_result = None
    raw_analyzer_output = None

    try:
        # Stage 1: Academic classification
        logger.info(f"[Pipeline] Stage 1: Classifying image for academic content: {filename}")
        classification = await analyzer_service.classify_image(image_data)
        is_academic = classification.get("is_academic_submission", True)
        classification_reason = classification.get("reason", "")

        if not is_academic and _should_continue_after_rejection(classification):
            logger.warning(
                "[Pipeline] Classifier rejected likely academic content; continuing to analyzer. subject=%s reason=%s",
                classification.get("subject"),
                classification_reason,
            )
            is_academic = True

        if not is_academic:
            logger.info(f"[Pipeline] Non-academic image rejected: {classification_reason}")
            return SubmissionResult(**ResponseNormalizer.normalize_rejection(classification))

        logger.info("[Pipeline] Academic content detected")

        # Stage 2: Primary Analyzer
        logger.info(f"[Pipeline] Stage 2: Grading academic content for {filename}")
        raw_analyzer_output = await analyzer_service.analyze_homework_image(image_data, filename)
        analyzer_result = ResponseNormalizer.normalize_analyzer_success(raw_analyzer_output)
        logger.info(
            "[Pipeline] Analyzer result: score=%s subject=%s",
            analyzer_result["suggested_score"],
            analyzer_result.get("subject"),
        )

    except Exception as e:
        logger.error(f"[Pipeline] Analyzer failed for {filename}: {e}")
        return SubmissionResult(**ResponseNormalizer.normalize_analyzer_failure(f"Analyzer failed: {e}"))

    try:
        logger.info(f"[Pipeline] Stage 3: Calling validator AI for {filename}")
        validator_result = await ollama_validator.validate(analyzer_result, image_data, filename)

        if ResponseNormalizer.should_regenerate_from_validator(analyzer_result, validator_result):
            logger.warning("[Pipeline] Validator rejected analyzer output, regenerating analyzer once")
            repaired_analyzer = await analyzer_service.analyze_homework_image(
                image_data,
                filename,
                repair_context=validator_result.get("reason"),
            )
            raw_analyzer_output = repaired_analyzer
            analyzer_result = ResponseNormalizer.normalize_analyzer_success(repaired_analyzer)
            validator_result = await ollama_validator.validate(analyzer_result, image_data, filename)

        final_result = ResponseNormalizer.merge_validator_result(analyzer_result, validator_result)
        if raw_analyzer_output:
            final_result = apply_quantitative_guardrail(final_result, raw_analyzer_output)
        final_result["detailed_mistakes"] = _filter_valid_detailed_mistakes(final_result.get("detailed_mistakes", []))

        logger.info(
            f"[Pipeline] Final result: score={final_result['suggested_score']}, "
            f"validation_status={final_result.get('validation_status')}, "
            f"is_valid={final_result.get('is_valid')}, is_preliminary={final_result.get('is_preliminary')}, "
            f"final_answer_correct={final_result.get('final_answer_correct')}, "
            f"math_error_found={final_result.get('math_error_found')}, "
            f"subject={final_result.get('subject')}, flags={final_result.get('validator_flags')}"
        )
        return SubmissionResult(**final_result)

    except Exception as e:
        logger.warning(f"[Pipeline] Validator exception for {filename}: {e}, returning preliminary result")
        final_result = ResponseNormalizer.merge_validator_result(
            analyzer_result,
            {"validator_failed": True, "reason": f"Validator exception: {e}"},
        )
        final_result["detailed_mistakes"] = _filter_valid_detailed_mistakes(final_result.get("detailed_mistakes", []))
        return SubmissionResult(**final_result)


def _filter_valid_detailed_mistakes(mistakes: list) -> list:
    """Filter out detailed mistakes that have empty required fields."""
    if not mistakes or not isinstance(mistakes, list):
        return []
    valid = []
    required_fields = ["type", "location", "what", "why", "how_to_fix"]
    for m in mistakes:
        if not isinstance(m, dict):
            continue
        if all(m.get(f, "").strip() for f in required_fields):
            valid.append(m)
    return valid

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health = {"status": "ok", "version": "0.1.0"}
    try:
        ollama_healthy = await ollama_validator.health_check()
        health["ollama_validator"] = "healthy" if ollama_healthy else "unavailable"
    except Exception as e:
        health["ollama_validator"] = f"error: {str(e)}"
    return health

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(request: Request, file: UploadFile = File(...)):
    """
    Analyze homework photo and return immediate result.
    Ownership is tracked via X-Session-ID or X-Owner-ID header.
    """
    init_db()

    owner_id = request.state.owner_id
    source = request.state.source
    logger.info(f"[Analyze] owner_id={owner_id}, source={source}, file={file.filename}")

    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="File must be an image (JPEG, PNG, GIF, WebP, etc.)"
        )

    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)
    if file_size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max: {MAX_UPLOAD_SIZE_MB}MB, got {file_size_mb:.1f}MB"
        )

    try:
        analysis_result = await analyze_homework(contents, file.filename)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed")

    db = SessionLocal()
    try:
        submission = Submission(
            filename=file.filename,
            image_data=contents,
            created_at=datetime.now(timezone.utc),
            result=analysis_result.model_dump(),
            owner_id=owner_id,
            source=source
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        logger.info(f"[Analyze] Stored submission {submission.id}, owner={owner_id}")

        return AnalyzeResponse(
            submission_id=submission.id,
            result=analysis_result
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Failed to store submission")
    finally:
        db.close()

@app.post("/submit", response_model=SubmissionResponse)
async def submit_homework(request: Request, file: UploadFile = File(...)):
    """Submit homework photo for async processing."""
    init_db()

    owner_id = request.state.owner_id
    source = request.state.source

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_UPLOAD_SIZE_MB}MB)"
        )

    db = SessionLocal()
    try:
        submission = Submission(
            filename=file.filename,
            image_data=contents,
            created_at=datetime.now(timezone.utc),
            owner_id=owner_id,
            source=source
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        return SubmissionResponse(
            id=submission.id,
            filename=submission.filename,
            created_at=submission.created_at,
            result=None
        )
    finally:
        db.close()

@app.get("/result/{submission_id}", response_model=SubmissionResponse)
async def get_result(request: Request, submission_id: int):
    """Retrieve submission and its analysis result. Owner-isolated."""
    init_db()

    owner_id = request.state.owner_id
    db = SessionLocal()
    try:
        submission = db.query(Submission).filter(
            Submission.id == submission_id,
            Submission.owner_id == owner_id
        ).first()
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        result = None
        if submission.result:
            result = SubmissionResult(**submission.result)

        return SubmissionResponse(
            id=submission.id,
            filename=submission.filename,
            created_at=submission.created_at,
            result=result
        )
    finally:
        db.close()

@app.get("/history", response_model=list[HistoryItem])
async def get_history(request: Request):
    """Retrieve list of current user's submissions only (most recent first)."""
    init_db()

    owner_id = request.state.owner_id
    logger.info(f"[History] Querying for owner_id={owner_id}")
    db = SessionLocal()
    try:
        submissions = db.query(Submission).filter(
            Submission.owner_id == owner_id
        ).order_by(Submission.created_at.desc()).all()

        logger.info(f"[History] Found {len(submissions)} submissions for owner={owner_id}")

        history_items = []
        for submission in submissions:
            suggested_score = None
            short_feedback = None
            subject = None
            topic = None
            task_title = None
            student_name = None

            if submission.result and isinstance(submission.result, dict):
                suggested_score = submission.result.get("suggested_score")
                short_feedback = submission.result.get("short_feedback")
                subject = submission.result.get("subject")
                topic = submission.result.get("topic")
                task_title = submission.result.get("task_title")
                student_name = submission.result.get("student_name")

            history_items.append(HistoryItem(
                id=submission.id,
                filename=submission.filename or "Untitled",
                created_at=submission.created_at,
                suggested_score=suggested_score,
                short_feedback=short_feedback,
                student_name=student_name,
                subject=subject,
                topic=topic,
                task_title=task_title
            ))

        return history_items
    finally:
        db.close()
