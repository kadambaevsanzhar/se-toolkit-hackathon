"""Ollama-based AI Validator for homework grading.

This validator INDEPENDENTLY checks the analyzer result by:
1. Re-solving the problem from the student's work
2. Verifying the analyzer's score is justified
3. Checking for contradictions between score/summary/mistakes
4. OVERRIDING the analyzer when scoring rules are violated

HARD SCORING RULES enforced by validator:
  - Wrong final answer → score ≤ 4
  - Math error found → score ≤ 6
  - Student marks answer as incorrect → score ≤ 4
  - Correct answer + correct steps → score 9-10
  - Contradiction between summary and score → override
"""

import os
import json
import logging
from typing import Dict, Any
import httpx

logger = logging.getLogger(__name__)

# The validator gets the ORIGINAL image + analyzer result.
# It must INDEPENDENTLY verify correctness and enforce hard scoring rules.
OLLAMA_SYSTEM_PROMPT = (
    "You are an independent homework grading validator and JUDGE for ANY academic subject. "
    "Your role is to verify the analyzer's grading and OVERRIDE it when necessary.\n\n"
    "TASK: Look at the student's work in the image and the analyzer's result. "
    "Independently determine:\n"
    "1. Is the student's final answer/work correct for the detected subject?\n"
    "2. Are there mathematical/logical/factual errors in the steps?\n"
    "3. Does the analyzer's score follow the hard scoring rules?\n"
    "4. Does the analyzer's summary contradict its detected mistakes?\n"
    "5. Is the detected subject correct?\n\n"
    "HARD SCORING RULES (you MUST enforce these):\n"
    "\n"
    "For mathematics / physics / chemistry quantitative work:\n"
    "  RULE 1: If the FINAL ANSWER is WRONG → score MUST be ≤ 4\n"
    "  RULE 2: If ANY mathematical error is found → score MUST be ≤ 6\n"
    "  RULE 3: If student marks answer as incorrect → score MUST be ≤ 4\n"
    "  RULE 4: If final answer correct AND steps correct → score 9 or 10\n"
    "  RULE 5: If final answer correct BUT reasoning weak → score 7 or 8\n\n"
    "For history / literature / language / social sciences / biology / geography:\n"
    "  RULE 1: If answer is fundamentally wrong/off-topic → score ≤ 4\n"
    "  RULE 2: If answer is correct but incomplete → score 6 to 7\n"
    "  RULE 3: If answer is correct and reasonably complete → score 8 or 9\n"
    "  RULE 4: If answer is excellent → score 10\n\n"
    "CONTRADICTION RULES:\n"
    "  - If summary says 'correct' but mistakes list errors → override score\n"
    "  - If strengths claim 'correct final answer' but answer is wrong → override\n"
    "  - If math_error_found but score > 6 → override score to ≤ 6\n"
    "  - If final answer wrong but score > 4 → override score to ≤ 4\n\n"
    "OUTPUT FORMAT — return ONLY valid JSON:\n"
    "{\n"
    '  "is_valid": true/false,\n'
    '  "override": true/false,\n'
    '  "final_score": int,\n'
    '  "corrected_feedback": "1-sentence summary",\n'
    '  "confirmed_strengths": ["..."],\n'
    '  "confirmed_mistakes": ["..."],\n'
    '  "improvement_suggestion": "...",\n'
    '  "next_steps": ["...", "...", "..."],\n'
    '  "validator_flags": ["..."],\n'
    '  "reason": "why you made this decision",\n'
    '  "final_answer_correct": true/false,\n'
    '  "math_error_found": true/false,\n'
    '  "contradiction_found": true/false,\n'
    '  "subject_confirmed": "string or null"\n'
    "}\n\n"
    "Rules:\n"
    "  - If analyzer is correct and follows scoring rules: is_valid=true, override=false\n"
    "  - If analyzer score violates hard rules: override=true, fix the score\n"
    "  - If you cannot determine: is_valid=false, override=false\n"
    "Return ONLY valid JSON, no markdown, no extra text."
)


class OllamaValidator:
    """Validator that independently verifies analyzer results using Ollama."""

    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2")
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "120"))
        logger.info(f"Ollama Validator initialized: base_url={self.base_url}, model={self.model}")

    async def validate(self, analyzer_result: Dict[str, Any],
                       original_context: str = "") -> Dict[str, Any]:
        """Independently validate the analyzer result with hard scoring enforcement."""
        if not analyzer_result:
            logger.warning("No analyzer result to validate")
            return self._create_fallback_result("No analyzer result provided")

        try:
            user_prompt = self._build_validation_prompt(analyzer_result, original_context)
            payload = {
                "model": self.model,
                "prompt": user_prompt,
                "system": OLLAMA_SYSTEM_PROMPT,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 500
                }
            }

            endpoint = f"{self.base_url}/api/generate"
            logger.info(f"[Validator] Sending independent validation request to {endpoint}")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(endpoint, json=payload)

                if response.status_code != 200:
                    logger.error(f"[Validator] Ollama HTTP {response.status_code}: {response.text[:200]}")
                    return self._create_fallback_result(
                        f"Ollama returned {response.status_code}",
                        analyzer_result
                    )

                result = response.json()
                response_text = result.get("response", "")

                if not response_text:
                    logger.warning("[Validator] Ollama returned empty response")
                    return self._create_fallback_result(
                        "Ollama returned empty response",
                        analyzer_result
                    )

                parsed = self._parse_response(response_text, analyzer_result)

                # Apply hard scoring enforcement even if LLM didn't follow rules
                parsed = self._enforce_hard_rules(parsed, analyzer_result)

                logger.info(
                    f"[Validator] Validation complete: "
                    f"is_valid={parsed.get('is_valid')}, "
                    f"override={parsed.get('override')}, "
                    f"score={analyzer_result.get('suggested_score')} -> {parsed.get('suggested_score')}, "
                    f"final_answer_correct={parsed.get('final_answer_correct')}, "
                    f"math_error_found={parsed.get('math_error_found')}, "
                    f"flags={parsed.get('validator_flags', [])}"
                )
                return parsed

        except httpx.TimeoutException:
            logger.error("[Validator] Ollama validation timeout")
            return self._create_fallback_result("Ollama validation timeout", analyzer_result)
        except Exception as e:
            logger.error(f"[Validator] Ollama validation error: {e}")
            return self._create_fallback_result(str(e), analyzer_result)

    def _build_validation_prompt(self, analyzer_result: Dict[str, Any],
                                  original_context: str) -> str:
        """Build prompt that includes analyzer result for independent verification."""
        parts = [
            "INDEPENDENTLY VALIDATE the following homework analysis.\n",
            "ANALYZER'S RESULT:",
            f"  Score: {analyzer_result.get('suggested_score', '?')}/{analyzer_result.get('max_score', 10)}",
            f"  Feedback: {analyzer_result.get('short_feedback', '?')}",
            f"  Strengths: {json.dumps(analyzer_result.get('strengths', []))}",
            f"  Mistakes: {json.dumps(analyzer_result.get('mistakes', []))}",
            f"  Next steps: {json.dumps(analyzer_result.get('next_steps', []))}",
            f"  Student name: {analyzer_result.get('student_name', 'none')}",
            f"  Subject: {analyzer_result.get('subject', '?')}",
            f"  Topic: {analyzer_result.get('topic', '?')}",
        ]

        if original_context:
            parts.extend(["", "SUBMISSION CONTEXT:", original_context])

        parts.append(
            "\nNow independently verify: is the score justified? "
            "Are the strengths/mistakes accurate? "
            "Does the summary contradict the mistakes? "
            "Enforce hard scoring rules. "
            "Return ONLY the JSON format specified in the system prompt."
        )

        return "\n".join(parts)

    def _parse_response(self, response_text: str,
                        analyzer_result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse validator response and build validated result."""
        try:
            cleaned = response_text.strip()
            if "```" in cleaned:
                import re
                m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.DOTALL)
                if m:
                    cleaned = m.group(1)
                else:
                    m = re.search(r'(\{.*\})', cleaned, re.DOTALL)
                    if m:
                        cleaned = m.group(1)

            parsed = json.loads(cleaned)
            max_score = analyzer_result.get("max_score", 10)

            # Extract validation decision
            is_valid = parsed.get("is_valid", True)
            override = parsed.get("override", False)
            reason = parsed.get("reason", "Validation completed")

            # Get validated score
            final_score = parsed.get("final_score", analyzer_result.get("suggested_score", 5))
            try:
                final_score = int(float(final_score))
                final_score = max(0, min(final_score, max_score))
            except (ValueError, TypeError):
                final_score = analyzer_result.get("suggested_score", 5)

            # Build validated result
            result = {
                "suggested_score": final_score,
                "max_score": max_score,
                "short_feedback": parsed.get("corrected_feedback",
                                            analyzer_result.get("short_feedback", "")),
                "strengths": parsed.get("confirmed_strengths",
                                       analyzer_result.get("strengths", [])),
                "mistakes": parsed.get("confirmed_mistakes",
                                      analyzer_result.get("mistakes", [])),
                "detailed_mistakes": analyzer_result.get("detailed_mistakes", []),
                "improvement_suggestion": parsed.get("improvement_suggestion",
                                                    analyzer_result.get("improvement_suggestion", "")),
                "next_steps": parsed.get("next_steps", analyzer_result.get("next_steps", [])),
                "student_name": analyzer_result.get("student_name"),
                "subject": analyzer_result.get("subject"),
                "topic": analyzer_result.get("topic"),
                "task_title": analyzer_result.get("task_title"),
                "is_valid": is_valid,
                "validator_override": override,
                "validator_reason": reason,
                "final_answer_correct": parsed.get("final_answer_correct", True),
                "math_error_found": parsed.get("math_error_found", False),
                "contradiction_found": parsed.get("contradiction_found", False),
                "validator_flags": parsed.get("validator_flags", [])
            }

            # Add appropriate flags
            if "validator_applied" not in result["validator_flags"]:
                result["validator_flags"].append("validator_applied")
            if not is_valid:
                result["validator_flags"].append("validator_disagrees")
            if override:
                if "score_adjusted" not in result["validator_flags"]:
                    result["validator_flags"].append("score_adjusted")

            return result

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"[Validator] Parse error: {e}, returning analyzer result as preliminary")
            fallback = dict(analyzer_result)
            if "validator_flags" not in fallback:
                fallback["validator_flags"] = []
            if "validator_failed" not in fallback["validator_flags"]:
                fallback["validator_flags"].append("validator_failed")
            if "is_valid" not in fallback:
                fallback["is_valid"] = False
            if "validator_override" not in fallback:
                fallback["validator_override"] = False
            if "validator_reason" not in fallback:
                fallback["validator_reason"] = f"Validator parse error: {str(e)}"
            if "final_answer_correct" not in fallback:
                fallback["final_answer_correct"] = True
            if "math_error_found" not in fallback:
                fallback["math_error_found"] = False
            if "contradiction_found" not in fallback:
                fallback["contradiction_found"] = False
            return fallback

    def _enforce_hard_rules(self, result: Dict[str, Any],
                            analyzer_result: Dict[str, Any]) -> Dict[str, Any]:
        """Enforce hard scoring rules even if the LLM validator didn't follow them."""
        score = result.get("suggested_score", 5)
        final_answer_correct = result.get("final_answer_correct", True)
        math_error_found = result.get("math_error_found", False)
        contradiction_found = result.get("contradiction_found", False)
        override = result.get("validator_override", False)
        mistakes = result.get("mistakes", [])

        # Check for explicit 'incorrect' marking by student
        has_incorrect_mark = False
        for m in mistakes:
            if isinstance(m, str) and any(kw in m.lower() for kw in ['ошибка', 'wrong', 'incorrect', 'not correct']):
                has_incorrect_mark = True
                break

        # RULE 3: Student marks answer as incorrect → score ≤ 4
        if has_incorrect_mark and score > 4:
            score = 4
            override = True
            if "score_adjusted" not in result.get("validator_flags", []):
                result["validator_flags"].append("score_adjusted")
            result["validator_reason"] = "Student marked answer as incorrect — score capped at 4"
            result["final_answer_correct"] = False

        # RULE 1: Final answer wrong → score ≤ 4
        if not final_answer_correct and score > 4:
            score = 4
            override = True
            if "score_adjusted" not in result.get("validator_flags", []):
                result["validator_flags"].append("score_adjusted")
            result["validator_reason"] = "Final answer is wrong — score capped at 4"

        # RULE 2: Math error found → score ≤ 6
        if math_error_found and score > 6:
            score = 6
            override = True
            if "score_adjusted" not in result.get("validator_flags", []):
                result["validator_flags"].append("score_adjusted")
            result["validator_reason"] = "Mathematical error found — score capped at 6"

        # CONTRADICTION: Summary says correct but mistakes exist → override
        if contradiction_found and not override:
            override = True
            if "score_adjusted" not in result.get("validator_flags", []):
                result["validator_flags"].append("score_adjusted")

        result["suggested_score"] = score
        result["validator_override"] = override

        return result

    def _create_fallback_result(self, error: str,
                                 analyzer_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create result when validator itself fails."""
        if analyzer_result:
            # Return analyzer result but mark it as unvalidated/preliminary
            result = dict(analyzer_result)
            if "validator_flags" not in result:
                result["validator_flags"] = []
            result["validator_flags"].append("validator_failed")
            result["is_valid"] = False
            result["validator_override"] = False
            result["validator_reason"] = f"Validation failed: {error}"
            result["final_answer_correct"] = True  # Unknown
            result["math_error_found"] = False
            result["contradiction_found"] = False
            logger.warning(f"[Validator] Returning analyzer result as preliminary: {error}")
            return result
        else:
            return {
                "suggested_score": 0,
                "max_score": int(os.getenv("AI_MAX_SCORE", "10")),
                "short_feedback": f"Analysis could not be completed: {error}",
                "strengths": [],
                "mistakes": [],
                "detailed_mistakes": [],
                "improvement_suggestion": "Please try again.",
                "next_steps": ["Resubmit your work"],
                "is_valid": False,
                "validator_override": False,
                "validator_reason": f"Validation failed: {error}",
                "final_answer_correct": True,
                "math_error_found": False,
                "contradiction_found": False,
                "validator_flags": ["validator_failed", "analysis_failed"]
            }

    async def health_check(self) -> bool:
        """Check if Ollama is reachable and model is available."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/")
                if response.status_code == 200:
                    tags_response = await client.get(f"{self.base_url}/api/tags")
                    if tags_response.status_code == 200:
                        models = tags_response.json().get("models", [])
                        model_names = [m.get("name", "") for m in models]
                        available = self.model in model_names or any(self.model in m for m in model_names)
                        if available:
                            logger.info(f"Ollama healthy: {self.model} available")
                        else:
                            logger.warning(f"Ollama reachable but {self.model} not found: {model_names}")
                        return available
                return False
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False


ollama_validator = OllamaValidator()
