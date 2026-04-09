import pytest
from pydantic import BaseModel

from ai.openai_responses import OpenAIResponsesClient, ResponsesAPIError


class DemoSchema(BaseModel):
    message: str


def test_extract_output_text_from_responses_api_payload():
    payload = {
        "output": [
            {
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"message":"ok"}',
                    }
                ]
            }
        ]
    }
    assert OpenAIResponsesClient.extract_output_text(payload) == '{"message":"ok"}'


def test_extract_output_text_raises_on_missing_text():
    with pytest.raises(ResponsesAPIError):
        OpenAIResponsesClient.extract_output_text({"output": []})


def test_build_payload_contains_json_schema():
    client = OpenAIResponsesClient()
    payload = client._build_payload(
        model="gpt-4.1-mini",
        schema_model=DemoSchema,
        system_prompt="system",
        user_prompt="user",
        image_data=None,
        image_mime_type="image/png",
        reasoning_effort="medium",
    )
    assert payload["model"] == "gpt-4.1-mini"
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True


def test_build_chat_completions_payload_uses_vision_message_format():
    client = OpenAIResponsesClient()
    payload = client._build_chat_completions_payload(
        model="qwen/qwen3-vl-8b-instruct",
        schema_model=DemoSchema,
        prompt_text="Analyze this homework",
        image_data=b"demo",
        image_mime_type="image/png",
        max_tokens=800,
    )
    assert payload["model"] == "qwen/qwen3-vl-8b-instruct"
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["content"][0] == {"type": "text", "text": "Analyze this homework"}
    assert payload["messages"][0]["content"][1]["type"] == "image_url"
    assert payload["max_tokens"] == 800
    assert "stream" not in payload
    assert payload["response_format"]["type"] == "json_schema"


def test_extract_chat_completion_text_from_response():
    payload = {
        "choices": [
            {
                "message": {
                    "content": '{"message":"ok"}',
                }
            }
        ]
    }
    assert OpenAIResponsesClient.extract_chat_completion_text(payload) == '{"message":"ok"}'


def test_parse_json_text_extracts_fenced_json():
    raw = '```json\n{"message":"ok"}\n```'
    assert OpenAIResponsesClient.parse_json_text(raw) == {"message": "ok"}


def test_coerce_schema_defaults_fills_missing_analyzer_fields():
    parsed = {
        "subject": "Mathematics",
        "topic": "Algebra",
        "task_title": "Solve the equation",
        "reconstructed_task_text": "Solve: 5x = 20",
        "student_answer_text": "x = 4",
    }
    normalized = OpenAIResponsesClient._coerce_schema_defaults(type("AnalyzerOutput", (), {"__name__": "AnalyzerOutput"}), parsed)
    assert normalized["suggested_score"] == 10
    assert "short_feedback" in normalized
    assert normalized["max_score"] == 10
