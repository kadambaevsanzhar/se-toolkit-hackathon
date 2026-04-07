"""AI Response Validator and Normalizer."""

import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)
DEFAULT_MAX_SCORE = int(os.getenv("AI_MAX_SCORE", "10"))

class AIResponseValidator:
    """Validates and normalizes AI analysis responses."""

    @staticmethod
    def validate_and_normalize(ai_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate AI response and normalize to expected format.

        Args:
            ai_response: Raw response from AI service

        Returns:
            Normalized response matching SubmissionResult schema

        Raises:
            ValueError: If response cannot be safely normalized
        """
        if not isinstance(ai_response, dict):
            raise ValueError("AI response must be a dictionary")

        normalized = {}

        # Validate and normalize max_score first so score clamping matches bounds
        max_score = ai_response.get("max_score", 10)
        try:
            max_score_int = int(float(max_score))
            if max_score_int < 1:
                logger.warning(f"AI max_score {max_score_int} < 1, defaulting to 10")
                max_score_int = 10
        except (ValueError, TypeError):
            logger.warning(f"AI max_score '{max_score}' not numeric, defaulting to 10")
            max_score_int = 10

        normalized["max_score"] = max_score_int

        # Validate and normalize suggested_score
        suggested_score = ai_response.get("suggested_score")
        if suggested_score is None:
            logger.warning("AI response missing suggested_score, defaulting to 5")
            normalized["suggested_score"] = min(5, max_score_int)
        else:
            try:
                score = float(suggested_score)
                score_int = int(score)
                if score_int < 0:
                    logger.warning(f"AI suggested_score {score_int} below 0, clamping")
                    score_int = 0
                elif score_int > max_score_int:
                    logger.warning(f"AI suggested_score {score_int} exceeds max_score {max_score_int}, clamping")
                    score_int = max_score_int
                normalized["suggested_score"] = score_int
            except (ValueError, TypeError):
                logger.warning(f"AI suggested_score '{suggested_score}' not numeric, defaulting to 5")
                normalized["suggested_score"] = min(5, max_score_int)

        # Ensure suggested_score <= max_score
        if normalized["suggested_score"] > normalized["max_score"]:
            logger.warning(f"suggested_score {normalized['suggested_score']} > max_score {normalized['max_score']}, adjusting")
            normalized["suggested_score"] = normalized["max_score"]

        # Validate and normalize short_feedback
        short_feedback = ai_response.get("short_feedback", "").strip()
        if not short_feedback:
            logger.warning("AI response missing or empty short_feedback, providing default")
            short_feedback = "Analysis completed. Please review the submission."
        elif len(short_feedback) > 500:
            logger.warning(f"AI short_feedback too long ({len(short_feedback)}), truncating")
            short_feedback = short_feedback[:497] + "..."
        normalized["short_feedback"] = short_feedback

        # Validate and normalize arrays
        normalized["strengths"] = AIResponseValidator._normalize_array(
            ai_response.get("strengths", []),
            "strengths"
        )

        normalized["mistakes"] = AIResponseValidator._normalize_array(
            ai_response.get("mistakes", []),
            "mistakes"
        )

        normalized["validator_flags"] = AIResponseValidator._normalize_array(
            ai_response.get("validator_flags", []),
            "validator_flags"
        )

        # Validate and normalize improvement_suggestion
        improvement_suggestion = ai_response.get("improvement_suggestion", "")
        if isinstance(improvement_suggestion, str) and len(improvement_suggestion) > 1000:
            logger.warning(f"AI improvement_suggestion too long ({len(improvement_suggestion)}), truncating")
            improvement_suggestion = improvement_suggestion[:997] + "..."
        elif not isinstance(improvement_suggestion, str):
            logger.warning(f"AI improvement_suggestion not string, converting")
            improvement_suggestion = str(improvement_suggestion)
        normalized["improvement_suggestion"] = improvement_suggestion

        # Add validation flags if we had to normalize
        if normalized != ai_response:
            normalized["validator_flags"].append("response_normalized")

        logger.info("AI response validated and normalized successfully")
        return normalized

    @staticmethod
    def _normalize_array(value: Any, field_name: str) -> List[str]:
        """Normalize array fields to list of strings."""
        if value is None:
            return []

        if isinstance(value, list):
            # Convert all items to strings, filter out empty ones
            normalized = []
            for item in value:
                if item is not None:
                    item_str = str(item).strip()
                    if item_str:
                        normalized.append(item_str)
            return normalized
        else:
            # Try to convert single value to list
            if isinstance(value, str) and value.strip():
                # Split on common separators
                if "," in value:
                    return [s.strip() for s in value.split(",") if s.strip()]
                elif ";" in value:
                    return [s.strip() for s in value.split(";") if s.strip()]
                else:
                    return [value.strip()]
            elif value:
                return [str(value)]
            else:
                return []

    @staticmethod
    def create_fallback_response(error_message: str = "AI analysis failed") -> Dict[str, Any]:
        """
        Create a safe fallback response when AI analysis completely fails.

        Args:
            error_message: Description of the failure

        Returns:
            Safe fallback response
        """
        return {
            "suggested_score": 0,
            "max_score": DEFAULT_MAX_SCORE,
            "short_feedback": f"Unable to analyze submission: {error_message}",
            "strengths": ["Submission received"],
            "mistakes": ["Analysis could not be completed"],
            "improvement_suggestion": "Please try submitting again or contact support.",
            "validator_flags": ["analysis_failed", "fallback_response"]
        }
