import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import main
from main import SubmissionResult, app

client = TestClient(app)


@pytest.fixture(scope="session")
def test_image_small():
    img = Image.new("RGB", (24, 24), color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def stub_pipeline(monkeypatch):
    async def fake_analyze(_image_data: bytes, filename: str):
        return SubmissionResult(
            analysis_status="success",
            validation_status="validated",
            is_preliminary=False,
            suggested_score=9,
            max_score=10,
            short_feedback=f"Validated result for {filename}",
            strengths=["Correct method"],
            mistakes=[],
            detailed_mistakes=[],
            improvement_suggestion="Keep showing your steps.",
            improvement_suggestions=["Keep showing your steps."],
            next_steps=["Try a slightly harder problem."],
            subject="Mathematics",
            topic="Linear equations",
            task_title="Solve for x",
            is_valid=True,
            validator_reason="Validator confirmed the analysis.",
            analyzer_reason="Analyzer completed successfully.",
            validator_flags=[],
        )

    monkeypatch.setattr(main, "analyze_homework", fake_analyze)


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestAnalyzeEndpoint:
    def test_analyze_accepts_image(self, test_image_small):
        response = client.post(
            "/analyze",
            files={"file": ("test.png", io.BytesIO(test_image_small), "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "submission_id" in data
        assert "result" in data

    def test_analyze_returns_normalized_result(self, test_image_small):
        response = client.post(
            "/analyze",
            files={"file": ("test.png", io.BytesIO(test_image_small), "image/png")},
        )
        result = response.json()["result"]
        assert result["analysis_status"] == "success"
        assert result["validation_status"] == "validated"
        assert result["is_preliminary"] is False
        assert result["suggested_score"] == 9
        assert result["subject"] == "Mathematics"
        assert result["improvement_suggestions"] == ["Keep showing your steps."]

    def test_analyze_rejects_non_image(self):
        response = client.post(
            "/analyze",
            files={"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")},
        )
        assert response.status_code == 400


class TestSubmissionResultSchema:
    def test_valid_result_accepts_all_fields(self):
        result = SubmissionResult(
            suggested_score=8,
            max_score=10,
            short_feedback="Good work!",
            strengths=["A"],
            mistakes=["B"],
            improvement_suggestion="Try harder",
            improvement_suggestions=["Try harder"],
            validator_flags=[],
        )
        assert result.suggested_score == 8
        assert result.improvement_suggestions == ["Try harder"]

    def test_result_validates_score_range(self):
        with pytest.raises(ValueError):
            SubmissionResult(
                suggested_score=15,
                max_score=10,
                short_feedback="Test",
            )

    def test_result_requires_feedback(self):
        with pytest.raises(ValueError):
            SubmissionResult(
                suggested_score=5,
                max_score=10,
                short_feedback="",
            )


class TestHistoryEndpoint:
    def test_history_returns_list(self, test_image_small):
        client.post(
            "/analyze",
            files={"file": ("test.png", io.BytesIO(test_image_small), "image/png")},
        )
        response = client.get("/history")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
