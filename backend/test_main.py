import pytest
from fastapi.testclient import TestClient
from PIL import Image
import io
import os
from main import app, SubmissionResult, SessionLocal, Submission

client = TestClient(app)

@pytest.fixture(scope="session")
def test_image_small():
    """Create a small test image."""
    img = Image.new("RGB", (10, 10), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()

@pytest.fixture(scope="session")
def test_image_large():
    """Create a larger test image."""
    img = Image.new("RGB", (100, 100), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()

class TestHealthEndpoint:
    def test_health_returns_ok(self):
        """Test /health endpoint returns OK status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

class TestAnalyzeEndpoint:
    def test_analyze_accepts_image(self, test_image_small):
        """Test /analyze endpoint accepts valid image."""
        response = client.post(
            "/analyze",
            files={"file": ("test.png", io.BytesIO(test_image_small), "image/png")}
        )
        assert response.status_code == 200
        data = response.json()
        assert "submission_id" in data
        assert "result" in data
        assert data["submission_id"] > 0

    def test_analyze_returns_valid_result(self, test_image_small):
        """Test /analyze returns properly structured result."""
        response = client.post(
            "/analyze",
            files={"file": ("test.png", io.BytesIO(test_image_small), "image/png")}
        )
        assert response.status_code == 200
        data = response.json()
        result = data["result"]
        
        # Validate schema
        assert isinstance(result["suggested_score"], int)
        assert 0 <= result["suggested_score"] <= 10
        assert result["max_score"] == 10
        assert isinstance(result["short_feedback"], str)
        assert len(result["short_feedback"]) > 0
        assert isinstance(result["strengths"], list)
        assert isinstance(result["mistakes"], list)
        assert isinstance(result["improvement_suggestion"], str)
        assert isinstance(result["validator_flags"], list)

    def test_analyze_rejects_non_image(self):
        """Test /analyze rejects non-image files."""
        text_content = b"This is not an image"
        response = client.post(
            "/analyze",
            files={"file": ("test.txt", io.BytesIO(text_content), "text/plain")}
        )
        assert response.status_code == 400
        assert "image" in response.json()["detail"].lower()

    def test_analyze_different_images_produce_consistent_structure(self, test_image_small, test_image_large):
        """Test that different images all produce valid results."""
        response1 = client.post(
            "/analyze",
            files={"file": ("small.png", io.BytesIO(test_image_small), "image/png")}
        )
        response2 = client.post(
            "/analyze",
            files={"file": ("large.png", io.BytesIO(test_image_large), "image/png")}
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        result1 = response1.json()["result"]
        result2 = response2.json()["result"]
        
        # Both should have valid structure
        for result in [result1, result2]:
            assert "suggested_score" in result
            assert "short_feedback" in result

    def test_analyze_stores_in_database(self, test_image_small):
        """Test /analyze stores submission in database."""
        response = client.post(
            "/analyze",
            files={"file": ("test.png", io.BytesIO(test_image_small), "image/png")}
        )
        assert response.status_code == 200
        submission_id = response.json()["submission_id"]
        
        # Verify in DB
        db = SessionLocal()
        try:
            submission = db.query(Submission).filter(Submission.id == submission_id).first()
            assert submission is not None
            assert submission.filename == "test.png"
            assert submission.image_data is not None
            assert submission.result is not None
            assert submission.result["suggested_score"] >= 0
        finally:
            db.close()

class TestSubmissionResultSchema:
    def test_valid_result_accepts_all_fields(self):
        """Test SubmissionResult accepts valid data."""
        result = SubmissionResult(
            suggested_score=8,
            max_score=10,
            short_feedback="Good work!",
            strengths=["A", "B"],
            mistakes=["C"],
            improvement_suggestion="Try harder",
            validator_flags=[]
        )
        assert result.suggested_score == 8
        assert result.short_feedback == "Good work!"

    def test_result_validates_score_range(self):
        """Test SubmissionResult validates score is in range."""
        with pytest.raises(ValueError):
            SubmissionResult(
                suggested_score=15,  # Out of range
                max_score=10,
                short_feedback="Test"
            )

    def test_result_requires_feedback(self):
        """Test SubmissionResult requires non-empty feedback."""
        with pytest.raises(ValueError):
            SubmissionResult(
                suggested_score=5,
                max_score=10,
                short_feedback=""  # Empty not allowed
            )

    def test_result_has_defaults(self):
        """Test SubmissionResult has sensible defaults."""
        result = SubmissionResult(
            suggested_score=5,
            short_feedback="Test"
        )
        assert result.max_score == 10
        assert result.strengths == []
        assert result.improvement_suggestion == ""
        assert result.validator_flags == []

class TestErrorHandling:
    def test_missing_file(self):
        """Test endpoint handles missing file."""
        response = client.post("/analyze")
        assert response.status_code == 422  # Unprocessable entity

    def test_result_endpoint_not_found(self):
        """Test /result returns 404 for unknown ID."""
        response = client.get("/result/99999")
        assert response.status_code == 404

class TestHistoryEndpoint:
    def test_history_returns_list(self, test_image_small):
        """Test /history endpoint returns a list."""
        # First, submit an image
        response = client.post(
            "/analyze",
            files={"file": ("test.png", io.BytesIO(test_image_small), "image/png")}
        )
        assert response.status_code == 200
        
        # Now fetch history
        response = client.get("/history")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_history_items_have_required_fields(self, test_image_small):
        """Test history items have id, filename, created_at, score, feedback."""
        # Submit an image first
        submit_response = client.post(
            "/analyze",
            files={"file": ("homework.png", io.BytesIO(test_image_small), "image/png")}
        )
        assert submit_response.status_code == 200
        
        # Fetch history
        response = client.get("/history")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        
        # Check first item has required fields
        first_item = data[0]
        assert "id" in first_item
        assert "filename" in first_item
        assert "created_at" in first_item
        assert "suggested_score" in first_item
        assert "short_feedback" in first_item
    
    def test_history_orders_by_date_descending(self, test_image_small):
        """Test history is ordered by date (most recent first)."""
        response = client.get("/history")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 1:
            # Check that dates are in descending order
            for i in range(len(data) - 1):
                current_date = data[i]["created_at"]
                next_date = data[i + 1]["created_at"]
                assert current_date >= next_date, "History should be ordered most recent first"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

