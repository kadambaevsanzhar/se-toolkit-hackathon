"""AI Service Wrapper for real Qwen API v1 integration."""

import os
import json
import base64
import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

class QwenAIService:
    """Wrapper for real Qwen AI API v1 calls."""

    def __init__(self):
        self.api_key = os.getenv("AI_API_KEY", "")
        self.model = os.getenv("AI_MODEL", "qwen3-coder-plus")
        # AI_BASE_URL should point to the v1 endpoint, e.g., http://host:42006/v1
        self.base_url = os.getenv("AI_BASE_URL", "http://localhost:42006/v1").rstrip("/")
        self.timeout = int(os.getenv("AI_TIMEOUT", "30"))
        self.max_score = int(os.getenv("AI_MAX_SCORE", "10"))

        if not self.api_key:
            logger.warning("AI_API_KEY not set - AI analysis will fail")
        if not self.api_key or self.api_key == "my-secret-qwen-key":
            logger.warning(f"AI_BASE_URL: {self.base_url}, model: {self.model}")

    async def analyze_homework_image(self, image_data: bytes, filename: str) -> Dict[str, Any]:
        """
        Analyze homework image using real Qwen API v1.

        Args:
            image_data: Raw image bytes
            filename: Original filename

        Returns:
            Dict containing AI analysis result with max_score set

        Raises:
            Exception: If API call fails
        """
        if not self.api_key:
            raise ValueError("AI_API_KEY not configured")

        # Convert image to base64
        image_b64 = base64.b64encode(image_data).decode('utf-8')

        # Prepare OpenAI-compatible request payload for v1 API
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": "Analyze this homework submission. Provide ONLY a valid JSON response (no markdown) with these keys: suggested_score (0-10 integer), short_feedback (string, max 200 chars), strengths (array of strings), mistakes (array of strings), improvement_suggestion (string). Do not include any other text."
                        }
                    ]
                }
            ],
            "temperature": 0.1,  # Low temperature for consistent scoring
            "max_tokens": 500
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        endpoint = f"{self.base_url}/chat/completions"
        logger.info(f"Sending homework analysis to {endpoint} for {filename}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload
                )

                if response.status_code != 200:
                    logger.error(f"AI API error: {response.status_code} - {response.text}")
                    raise Exception(f"AI API returned {response.status_code}: {response.text}")

                result = response.json()
                logger.info(f"AI API response received for {filename}")

                # Extract and normalize the analysis result
                analysis = self._extract_analysis_result(result)
                # Add max_score to result
                analysis["max_score"] = self.max_score
                return analysis

        except httpx.TimeoutException:
            logger.error(f"AI API timeout for {filename}")
            raise Exception("AI analysis timeout")
        except Exception as e:
            logger.error(f"AI API error for {filename}: {e}")
            raise

    def _extract_analysis_result(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract analysis result from OpenAI-compatible v1 API response.

        API response structure:
        {
            "choices": [
                {
                    "message": {
                        "content": "JSON string with analysis"
                    }
                }
            ]
        }
        """
        try:
            # Navigate to the choices array
            choices = api_response.get("choices", [])
            if not choices:
                raise ValueError("No choices in API response")

            message = choices[0].get("message", {})
            content = message.get("content", "")

            if not content:
                raise ValueError("Empty content in API response")

            # Parse JSON content
            content_clean = content.strip()
            
            # Try to extract JSON if wrapped in markdown
            if not content_clean.startswith("{"):
                import re
                # Try markdown code block
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content_clean, re.DOTALL)
                if json_match:
                    content_clean = json_match.group(1)
                else:
                    # Try to find JSON object in text
                    json_match = re.search(r'(\{.*\})', content_clean, re.DOTALL)
                    if json_match:
                        content_clean = json_match.group(1)
            
            result = json.loads(content_clean)

            logger.info("Successfully extracted analysis result from AI API response")
            return result

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"Failed to parse AI API response: {e}")
            logger.debug(f"Raw API response: {api_response}")
            raise ValueError(f"Invalid response format from AI API: {e}")

# Global instance
ai_service = QwenAIService()
# Keep backward compatibility
qwen_service = ai_service
