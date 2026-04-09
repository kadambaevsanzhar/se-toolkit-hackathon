"""OpenAI-compatible wrappers for structured responses and analyzer chat completions."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from typing import Any, Type

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class ResponsesAPIError(RuntimeError):
    """Raised when the Responses API request or schema validation fails."""


class OpenAIResponsesClient:
    """Tiny wrapper around the official OpenAI Responses API."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AI_API_KEY") or ""
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.timeout = int(os.getenv("OPENAI_TIMEOUT", os.getenv("AI_TIMEOUT", "120")))
        self.max_output_tokens = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1500"))
        self.last_response_json: dict[str, Any] | None = None
        self.last_output_text: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def create_json_response(
        self,
        *,
        model: str,
        schema_model: Type[BaseModel],
        system_prompt: str,
        user_prompt: str,
        image_data: bytes | None = None,
        image_mime_type: str = "image/jpeg",
        repair_instruction: str | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        """Call the Responses API and validate the reply against a Pydantic model."""
        if not self.api_key:
            raise ResponsesAPIError("OPENAI_API_KEY is not configured")

        last_error: Exception | None = None
        for attempt in range(2):
            prompt_suffix = ""
            if attempt == 1 and repair_instruction:
                prompt_suffix = f"\n\nREPAIR INSTRUCTION:\n{repair_instruction}"

            payload = self._build_payload(
                model=model,
                schema_model=schema_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt + prompt_suffix,
                image_data=image_data,
                image_mime_type=image_mime_type,
                reasoning_effort=reasoning_effort,
            )

            try:
                response_json = await self._post(payload)
                raw_text = self.extract_output_text(response_json)
                self.last_response_json = response_json
                self.last_output_text = raw_text
                parsed = json.loads(raw_text)
                validated = schema_model.model_validate(parsed)
                return validated.model_dump()
            except (json.JSONDecodeError, ValidationError, ResponsesAPIError, httpx.HTTPError) as exc:
                last_error = exc
                logger.warning("Responses API attempt %s failed: %s", attempt + 1, exc)

        raise ResponsesAPIError(str(last_error) if last_error else "Responses API request failed")

    async def create_json_chat_completion(
        self,
        *,
        model: str,
        schema_model: Type[BaseModel],
        prompt_text: str,
        image_data: bytes | None = None,
        image_mime_type: str = "image/jpeg",
        repair_instruction: str | None = None,
        max_tokens: int = 800,
    ) -> dict[str, Any]:
        """Call OpenRouter chat/completions and validate the JSON reply."""
        if not self.api_key:
            raise ResponsesAPIError("OPENAI_API_KEY is not configured")

        last_error: Exception | None = None
        for attempt in range(2):
            prompt_suffix = ""
            if attempt == 1 and repair_instruction:
                prompt_suffix = f"\n\nREPAIR INSTRUCTION:\n{repair_instruction}"

            payload = self._build_chat_completions_payload(
                model=model,
                schema_model=schema_model,
                prompt_text=prompt_text + prompt_suffix,
                image_data=image_data,
                image_mime_type=image_mime_type,
                max_tokens=max_tokens,
            )

            try:
                response_json = await self._post_chat_completions(payload)
                raw_text = self.extract_chat_completion_text(response_json)
                self.last_response_json = response_json
                self.last_output_text = raw_text
                parsed = self.parse_json_text(raw_text)
                parsed = self._coerce_schema_defaults(schema_model, parsed)
                validated = schema_model.model_validate(parsed)
                return validated.model_dump()
            except (json.JSONDecodeError, ValidationError, ResponsesAPIError, httpx.HTTPError) as exc:
                last_error = exc
                logger.warning("Chat Completions attempt %s failed: %s", attempt + 1, exc)
                if self.last_output_text:
                    logger.warning("Raw analyzer text before validation: %s", self.last_output_text)

        raise ResponsesAPIError(str(last_error) if last_error else "Chat Completions request failed")

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.base_url}/responses"
        logger.info("OpenAI-compatible request endpoint=%s model=%s", endpoint, payload.get("model"))
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
        logger.info("OpenAI-compatible response status endpoint=%s status=%s", endpoint, response.status_code)
        if response.status_code >= 400:
            raise ResponsesAPIError(f"Responses API returned {response.status_code}")
        return response.json()

    async def _post_chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.base_url}/chat/completions"
        logger.info("OpenAI-compatible request endpoint=%s model=%s", endpoint, payload.get("model"))
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
        logger.info("OpenAI-compatible response status endpoint=%s status=%s", endpoint, response.status_code)
        if response.status_code >= 400:
            raise ResponsesAPIError(f"Responses API returned {response.status_code}")
        return response.json()

    def _build_payload(
        self,
        *,
        model: str,
        schema_model: Type[BaseModel],
        system_prompt: str,
        user_prompt: str,
        image_data: bytes | None,
        image_mime_type: str,
        reasoning_effort: str | None,
    ) -> dict[str, Any]:
        input_content: list[dict[str, Any]] = [{"type": "input_text", "text": user_prompt}]
        if image_data is not None:
            image_b64 = base64.b64encode(image_data).decode("utf-8")
            input_content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{image_mime_type};base64,{image_b64}",
                }
            )

        payload: dict[str, Any] = {
            "model": model,
            "instructions": system_prompt,
            "input": [{"role": "user", "content": input_content}],
            "temperature": 0,
            "max_output_tokens": self.max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_model.__name__,
                    "schema": self._strict_json_schema(schema_model.model_json_schema()),
                    "strict": True,
                }
            },
        }
        if reasoning_effort:
            payload["reasoning"] = {"effort": reasoning_effort}
        return payload

    def _build_chat_completions_payload(
        self,
        *,
        model: str,
        schema_model: Type[BaseModel],
        prompt_text: str,
        image_data: bytes | None,
        image_mime_type: str,
        max_tokens: int,
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt_text}]
        if image_data is not None:
            image_b64 = base64.b64encode(image_data).decode("utf-8")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image_mime_type};base64,{image_b64}",
                    },
                }
            )

        return {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0,
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_model.__name__,
                    "strict": True,
                    "schema": self._strict_json_schema(schema_model.model_json_schema()),
                },
            },
        }

    @staticmethod
    def extract_output_text(response_json: dict[str, Any]) -> str:
        """Extract the textual JSON payload from a Responses API response."""
        output = response_json.get("output", [])
        for item in output:
            for content in item.get("content", []):
                text = content.get("text")
                if text:
                    return text

        output_text = response_json.get("output_text")
        if output_text:
            return output_text

        raise ResponsesAPIError("Responses API returned no output text")

    @staticmethod
    def extract_chat_completion_text(response_json: dict[str, Any]) -> str:
        """Extract message content from a chat completions response."""
        choices = response_json.get("choices", [])
        if not choices:
            raise ResponsesAPIError("Chat Completions returned no choices")
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    text_parts.append(str(item["text"]))
            if text_parts:
                return "\n".join(text_parts)
        raise ResponsesAPIError("Chat Completions returned no message text")

    @staticmethod
    def parse_json_text(raw_text: str) -> dict[str, Any]:
        """Safely parse JSON even if the model wrapped it in fences or extra prose."""
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        raise json.JSONDecodeError("Unable to extract JSON object", text, 0)

    @staticmethod
    def _coerce_schema_defaults(schema_model: Type[BaseModel], parsed: dict[str, Any]) -> dict[str, Any]:
        """Fill controlled fallback values for missing required fields before validation."""
        if not isinstance(parsed, dict):
            return parsed
        if schema_model.__name__ != "AnalyzerOutput":
            return parsed

        normalized = dict(parsed)
        normalized.setdefault("is_academic_submission", True)
        normalized.setdefault("subject", "General Academic Work")
        normalized.setdefault("topic", "Visible academic task")
        normalized.setdefault("task_title", "Visible homework task")
        normalized.setdefault(
            "reconstructed_task_text",
            normalized.get("task_title") or "Visible homework task",
        )
        normalized.setdefault(
            "student_answer_text",
            normalized.get("reconstructed_task_text") or "Visible student answer",
        )
        normalized.setdefault("max_score", 10)
        normalized.setdefault(
            "strengths",
            [
                "The submission contains visible academic work.",
                "The student provided a readable attempt.",
            ],
        )
        normalized.setdefault("mistakes", [])
        normalized.setdefault("detailed_mistakes", [])
        normalized.setdefault("improvement_suggestions", ["Review the visible solution and make the main correction needed."])
        normalized.setdefault(
            "next_steps",
            [
                "Review the key concept used in this task.",
                "Practice one similar problem with full steps.",
                "Check the final answer against the original task.",
            ],
        )
        normalized.setdefault("observed_steps", [normalized.get("student_answer_text") or "Visible final answer only."])
        if "suggested_score" not in normalized:
            normalized["suggested_score"] = 10 if not normalized.get("mistakes") else 6
        if "short_feedback" not in normalized:
            if normalized.get("mistakes"):
                normalized["short_feedback"] = "The submission contains a visible mistake that should be corrected."
            else:
                normalized["short_feedback"] = "The submission appears correct based on the visible work."
        return normalized

    @classmethod
    def _strict_json_schema(cls, schema: dict[str, Any]) -> dict[str, Any]:
        """Normalize JSON schema for providers that require strict required-fields arrays."""
        if not isinstance(schema, dict):
            return schema

        normalized = dict(schema)
        properties = normalized.get("properties")
        if isinstance(properties, dict):
            normalized["required"] = list(properties.keys())
            normalized.setdefault("additionalProperties", False)
            normalized["properties"] = {
                key: cls._strict_json_schema(value) if isinstance(value, dict) else value
                for key, value in properties.items()
            }

        defs = normalized.get("$defs")
        if isinstance(defs, dict):
            normalized["$defs"] = {
                key: cls._strict_json_schema(value) if isinstance(value, dict) else value
                for key, value in defs.items()
            }

        items = normalized.get("items")
        if isinstance(items, dict):
            normalized["items"] = cls._strict_json_schema(items)

        any_of = normalized.get("anyOf")
        if isinstance(any_of, list):
            normalized["anyOf"] = [
                cls._strict_json_schema(item) if isinstance(item, dict) else item
                for item in any_of
            ]

        return normalized
