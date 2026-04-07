"""AI Homework Grader - Backend API with Qwen AI integration."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine, Column, Integer, String, DateTime, LargeBinary, JSON, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os
import io
from PIL import Image
import logging

# Import our AI modules
from ai_service import ai_service
from ai_validator import AIResponseValidator

# ============================================================================
# CONFIG & LOGGING
# ============================================================================

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://grader:grader@localhost:5432/grader_dev")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:42006/v1")
AI_MODEL = os.getenv("AI_MODEL", "qwen3-coder-plus")
AI_MAX_SCORE = int(os.getenv("AI_MAX_SCORE", "10"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))

# ============================================================================
# DATABASE
# ============================================================================

# Try PostgreSQL first if configured, fallback to SQLite for local development
if DATABASE_URL.startswith("postgresql://"):
    try:
        engine = create_engine(DATABASE_URL, echo=False, connect_args={"connect_timeout": 5})
        # Test connection
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
    # Use SQLite for local development and testing
    engine = create_engine(
        "sqlite:///./grader_dev.db",
        echo=False,
        connect_args={"check_same_thread": False}
    )
    logger.info("Using SQLite database")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Submission(Base):
    """Database model for submissions."""
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    image_data = Column(LargeBinary)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    result = Column(JSON, nullable=True)

_tables_created = False

def init_db():
    """Initialize database tables (lazy)."""
    global _tables_created
    if not _tables_created:
        try:
            Base.metadata.create_all(bind=engine)
            _tables_created = True
            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

# ============================================================================
# SCHEMAS
# ============================================================================

class SubmissionResult(BaseModel):
    """Normalized AI analysis result."""
    suggested_score: int = Field(..., ge=0, description="Score from 0 to max_score")
    max_score: int = Field(default=AI_MAX_SCORE, ge=1, description="Maximum possible score")
    short_feedback: str = Field(..., min_length=1, description="Brief feedback on submission")
    strengths: list = Field(default_factory=list, description="List of strengths")
    mistakes: list = Field(default_factory=list, description="List of areas needing improvement")
    improvement_suggestion: str = Field(default="", description="Suggestion for improvement")
    validator_flags: list = Field(default_factory=list, description="Validation warnings if any")

    @field_validator("suggested_score")
    @classmethod
    def validate_score_in_range(cls, v, info):
        """Ensure suggested_score does not exceed max_score."""
        max_score = info.data.get("max_score", AI_MAX_SCORE)
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

async def analyze_homework(image_data: bytes, filename: str) -> SubmissionResult:
    """
    Analyze homework image using Qwen AI service.

    Args:
        image_data: Raw image bytes
        filename: Original filename

    Returns:
        Normalized SubmissionResult

    Raises:
        Exception: If analysis fails completely
    """
    try:
        # Call AI service (real API v1 endpoint)
        ai_response = await ai_service.analyze_homework_image(image_data, filename)

        # Validate and normalize response
        normalized_response = AIResponseValidator.validate_and_normalize(ai_response)

        # Convert to Pydantic model for final validation
        result = SubmissionResult(**normalized_response)

        logger.info(f"Successfully analyzed {filename}: score={result.suggested_score}")
        return result

    except Exception as e:
        logger.error(f"AI analysis failed for {filename}: {e}")

        # Create safe fallback response
        fallback_data = AIResponseValidator.create_fallback_response(str(e))
        result = SubmissionResult(**fallback_data)

        logger.info(f"Using fallback response for {filename}")
        return result
    
    logger.info(f"Analyzed '{filename}': score={result.suggested_score}")
    return result

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(file: UploadFile = File(...)):
    """
    Analyze homework photo and return immediate result.
    
    - Accepts image file (JPEG, PNG, GIF, WebP, etc.)
    - Performs AI analysis using Qwen API
    - Validates and stores result
    - Returns submission ID and analysis result
    """
    init_db()
    
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
            result=analysis_result.model_dump()
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        logger.info(f"Stored submission {submission.id}")
        
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
async def submit_homework(file: UploadFile = File(...)):
    """Submit homework photo for async processing."""
    init_db()
    
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
        submission = Submission(filename=file.filename, image_data=contents)
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
async def get_result(submission_id: int):
    """Retrieve submission and its analysis result."""
    init_db()
    
    db = SessionLocal()
    try:
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
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
async def get_history():
    """Retrieve list of all previous submissions (most recent first)."""
    init_db()
    
    db = SessionLocal()
    try:
        # Query all submissions ordered by date descending (most recent first)
        submissions = db.query(Submission).order_by(Submission.created_at.desc()).all()
        
        history_items = []
        for submission in submissions:
            # Extract score and short_feedback from result JSON
            suggested_score = None
            short_feedback = None
            
            if submission.result and isinstance(submission.result, dict):
                suggested_score = submission.result.get("suggested_score")
                short_feedback = submission.result.get("short_feedback")
            
            history_items.append(HistoryItem(
                id=submission.id,
                filename=submission.filename or "Untitled",
                created_at=submission.created_at,
                suggested_score=suggested_score,
                short_feedback=short_feedback
            ))
        
        return history_items
    finally:
        db.close()
