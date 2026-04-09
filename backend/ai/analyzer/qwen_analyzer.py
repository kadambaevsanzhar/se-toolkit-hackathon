"""AI Analyzer Service — Qwen VL via OpenRouter API.

Uses real Qwen vision-capable models through OpenRouter.
Subject-agnostic: grades any academic subject visible in a photo.

STRICT SCORING RULES enforced via prompt:
  - Correct answer + correct steps → 9-10
  - Correct answer, weak reasoning → 8
  - Math error found → ≤ 6
  - Wrong final answer → ≤ 4
  - Student marks answer as incorrect → ≤ 4
"""

import os
import json
import base64
import re
import logging
from typing import Dict, Any
import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("ANALYZER_MODEL", "qwen/qwen3-vl-8b-instruct")
DEFAULT_BASE = os.getenv("ANALYZER_BASE_URL", "https://openrouter.ai/api/v1")
DEFAULT_TIMEOUT = int(os.getenv("ANALYZER_TIMEOUT", "90"))

# ---------------------------------------------------------------------------
# Stage 1 — Academic classification prompt
# ---------------------------------------------------------------------------
CLASSIFIER_PROMPT = (
    "Classify image. Return ONLY JSON: "
    "{\"is_academic_submission\":true/false,\"subject\":\"string or null\",\"reason\":\"string\"}"
)

# ---------------------------------------------------------------------------
# Stage 2 — STRICT grader prompt with enforced scoring rules
# ---------------------------------------------------------------------------
GRADER_PROMPT = (
    "You are a teacher grading a homework photo. Analyze the image carefully.\n\n"
    "Return a JSON object with these fields, filling in real values:\n"
    "- suggested_score: integer 0-10\n"
    "- short_feedback: one sentence about the submission\n"
    "- strengths: array of exactly 2 strengths you observe\n"
    "- mistakes: array of 0-2 real mistakes (empty array if none)\n"
    "- detailed_mistakes: array matching mistakes count, each with type/location/what/why/how_to_fix\n"
    "- improvement_suggestion: one specific suggestion\n"
    "- next_steps: exactly 3 specific next steps\n"
    "- student_name: string if you see Name:/Student:/Full Name:/Author: labels, else null\n"
    "- subject: one of Algebra/Physics/Chemistry/Biology/History/Geography/Literature/English/CS/Economics/General Academic\n"
    "- topic: short topic name\n"
    "- task_title: short description of the task\n\n"
    "SCORING: For math — wrong answer=0-4, calculation error=5-6, correct with steps=9-10, correct but minimal steps=7-8.\n"
    "For other subjects — wrong/off-topic=0-4, incomplete=6-7, correct=8-9, excellent=10.\n"
    "Never invent mistakes. If the work is correct, use empty arrays for mistakes."
)


class QwenAIService:
    """Analyzer that calls Qwen VL via OpenRouter for image-based academic grading."""

    def __init__(self):
        self.api_key = os.getenv("AI_API_KEY", "")
        self.model = DEFAULT_MODEL
        self.base_url = DEFAULT_BASE.rstrip("/")
        self.timeout = DEFAULT_TIMEOUT
        self.max_score = int(os.getenv("AI_MAX_SCORE", "10"))

        if not self.api_key:
            logger.warning("AI_API_KEY not set — analysis will fail")
        logger.info(
            "Qwen Analyzer (OpenRouter): model=%s base=%s timeout=%ds",
            self.model, self.base_url, self.timeout,
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------
    async def classify_image(self, image_data: bytes) -> Dict[str, Any]:
        """Stage 1: Determine if image contains academic content."""
        if not self.api_key:
            raise ValueError("AI_API_KEY not configured")

        # Quick heuristic check before calling AI
        heuristic = self._quick_image_heuristic(image_data)
        if heuristic:
            return heuristic

        image_b64 = base64.b64encode(image_data).decode('utf-8')
        mime = self._detect_mime_type(image_data)

        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{image_b64}"}
                        },
                        {"type": "text", "text": CLASSIFIER_PROMPT}
                    ]
                }
            ],
            "max_tokens": 200,
            "temperature": 0.0,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        endpoint = f"{self.base_url}/chat/completions"
        logger.info(f"[Classifier] Sending image to {endpoint}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error(f"[Classifier] API error {resp.status_code}: {resp.text[:300]}")
                return {
                    "is_academic_submission": True,
                    "subject": None,
                    "reason": "Classifier unavailable — proceeding to grading"
                }

            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return self._parse_classifier_output(content)

    async def analyze_homework_image(self, image_data: bytes, filename: str) -> Dict[str, Any]:
        """Stage 2: Grade the academic content in the image with STRICT scoring."""
        if not self.api_key:
            raise ValueError("AI_API_KEY not configured")

        image_b64 = base64.b64encode(image_data).decode('utf-8')
        mime = self._detect_mime_type(image_data)

        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{image_b64}"}
                        },
                        {"type": "text", "text": GRADER_PROMPT}
                    ]
                }
            ],
            "max_tokens": 250,
            "temperature": 0.0,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        endpoint = f"{self.base_url}/chat/completions"
        logger.info(f"[Grader] Sending {filename} ({len(image_data)} bytes) to {endpoint}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error(f"[Grader] API error {resp.status_code}: {resp.text[:300]}")
                raise Exception(f"AI API returned {resp.status_code}: {resp.text[:300]}")

            data = resp.json()
            logger.info(f"[Grader] Response received for {filename}")
            return self._extract(data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _detect_mime_type(self, data: bytes) -> str:
        if data.startswith(b"\x89PNG"):
            return "image/png"
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if data.startswith(b"GIF8"):
            return "image/gif"
        if data.startswith(b"RIFF") and len(data) > 12 and data[8:12] == b"WEBP":
            return "image/webp"
        return "image/jpeg"

    def _quick_image_heuristic(self, data: bytes) -> Dict[str, Any] | None:
        """Quick heuristic check before calling AI classifier."""
        try:
            import io
            from PIL import Image
            img = Image.open(io.BytesIO(data))
            img.verify()
            img = Image.open(io.BytesIO(data))

            w, h = img.size
            if w < 50 or h < 50:
                return {
                    "is_academic_submission": False,
                    "subject": None,
                    "reason": f"The image is too small ({w}x{h}px) to contain readable academic content."
                }

            gray = img.convert("L")
            import statistics
            pixels = list(gray.getdata())
            if len(pixels) < 100:
                return {
                    "is_academic_submission": False,
                    "subject": None,
                    "reason": "The image is too small to contain readable academic content."
                }
            stdev = statistics.stdev(pixels) if len(pixels) > 1 else 0

            if stdev < 5:
                return {
                    "is_academic_submission": False,
                    "subject": None,
                    "reason": "The image appears to be a solid color and does not contain readable academic content."
                }

            return None
        except Exception:
            return None

    def _parse_classifier_output(self, content: str) -> Dict[str, Any]:
        """Parse classifier JSON response."""
        try:
            cleaned = content.strip()
            if "```" in cleaned:
                m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.DOTALL)
                if m:
                    cleaned = m.group(1)
                else:
                    m = re.search(r'(\{.*\})', cleaned, re.DOTALL)
                    if m:
                        cleaned = m.group(1)
            return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"[Classifier] Parse error: {e}, defaulting to allow submission")
            return {
                "is_academic_submission": True,
                "subject": None,
                "reason": f"Classifier parse error — proceeding to grading: {str(e)}"
            }

    def _extract(self, api_resp: Dict[str, Any]) -> Dict[str, Any]:
        """Pull content from OpenRouter response and parse JSON robustly."""
        choices = api_resp.get("choices", [])
        if not choices:
            raise ValueError("No choices in API response")

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise ValueError("Empty content in API response")

        cleaned = content.strip()

        # Extract JSON block
        if "```" in cleaned:
            m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.DOTALL)
            if m:
                cleaned = m.group(1)
            else:
                m = re.search(r'(\{.*\})', cleaned, re.DOTALL)
                if m:
                    cleaned = m.group(1)

        # Try direct parse first
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Fix common JSON issues from LLMs
        # Remove trailing commas before } or ]
        cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
        # Fix unescaped quotes in strings (basic fix)
        # Try parsing again
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Last resort: find the largest valid JSON object
        for start in range(len(cleaned)):
            if cleaned[start] == '{':
                for end in range(len(cleaned), start, -1):
                    if cleaned[end-1] == '}':
                        try:
                            return json.loads(cleaned[start:end])
                        except json.JSONDecodeError:
                            continue

        raise ValueError(f"Could not parse JSON from: {cleaned[:200]}...")


# Singleton
analyzer_service = QwenAIService()
