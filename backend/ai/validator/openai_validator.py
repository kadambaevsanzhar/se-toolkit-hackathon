"""OpenAI Responses API validator for analyzer results."""

from __future__ import annotations

import logging
import os
from typing import Any

from ai.contracts import ValidatorOutput
from ai.grading_guidance import GENERAL_GRADING_GUIDANCE
from ai.openai_responses import OpenAIResponsesClient, ResponsesAPIError

logger = logging.getLogger(__name__)

VALIDATOR_REPAIR = "Return valid JSON only. Follow the schema exactly. Do not add prose."
QUANT_SUBJECTS = {
    "mathematics",
    "math",
    "algebra",
    "geometry",
    "physics",
    "chemistry",
}


class OpenAIValidator:
    """Secondary validator that checks and can override the analyzer."""

    def __init__(self) -> None:
        self.model = os.getenv("OPENAI_VALIDATOR_MODEL", "gpt-4.1-mini")
        self.client = OpenAIResponsesClient()

    async def validate(
        self,
        analyzer_result: dict[str, Any],
        image_data: bytes,
        filename: str,
        image_mime_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        """Validate analyzer output against the image and grading rules."""
        if not analyzer_result:
            return self._validator_failed("No analyzer result")
        if not self.client.configured:
            return self._validator_failed("OPENAI_API_KEY is not configured")

        try:
            parsed = await self.client.create_json_response(
                model=self.model,
                schema_model=ValidatorOutput,
                system_prompt=(
                    "You are the strict secondary AI reviewer in a homework grading pipeline. "
                    "You must verify the analyzer against the original image and override bad grading. "
                    "For quantitative subjects, independently solve the task before deciding. "
                    "For other subjects, judge relevance, correctness, completeness, reasoning, and score fairness. "
                    "Do not merely paraphrase the analyzer. "
                    "Judge whether the analyzer identified the first real error, its location, and its type correctly. "
                    f"Use this shared grading guidance exactly:\n{GENERAL_GRADING_GUIDANCE}"
                ),
                user_prompt=(
                    f"Validate analyzer output for '{filename}'.\n\n"
                    f"Analyzer JSON:\n{analyzer_result}\n\n"
                    "Rules:\n"
                    "- If contradiction_found is true, override must be true.\n"
                    "- If final_answer_correct is false for a quantitative problem, final_score must be <= 4.\n"
                    "- If math_error_found is true, final_score must be <= 6.\n"
                    "- If analyzer subject is meaningfully wrong, set analysis_consistent to false.\n"
                    "- Independently identify the first real wrong step, claim, or inference.\n"
                    "- For non-quantitative subjects, identify the first materially false, unsupported, irrelevant, or incomplete claim instead of giving vague criticism.\n"
                    "- Set error_location_correct to false if the analyzer blamed the wrong place.\n"
                    "- Set error_type_correct to false if the analyzer described the wrong type of error.\n"
                    "- Set explanation_specific_enough to false if the analyzer explanation is vague or misleading.\n"
                    "- If any of error_location_correct, error_type_correct, or explanation_specific_enough is false, override must be true.\n"
                    "- first_wrong_step must name the first real error location when a real mistake exists.\n"
                    "- validated_mistakes must contain 0 to 2 items only.\n"
                    "- validated_detailed_mistakes must exactly match validated_mistakes count.\n"
                    "- validated_summary, validated_mistakes, and validated_detailed_mistakes must match the final decision.\n"
                    "- For decisive errors, validated_detailed_mistakes must explain where the error occurs, what is wrong, why it is wrong, what the correct step or claim should be, and how to fix it.\n"
                    "- Return JSON only."
                ),
                image_data=image_data,
                image_mime_type=image_mime_type,
                repair_instruction=VALIDATOR_REPAIR,
                reasoning_effort="medium",
            )
        except ResponsesAPIError as exc:
            logger.error("Validator failed: %s", exc)
            return self._validator_failed(str(exc))

        return self._post_process(parsed, analyzer_result)

    async def health_check(self) -> bool:
        return self.client.configured

    def _post_process(self, parsed: dict[str, Any], analyzer_result: dict[str, Any]) -> dict[str, Any]:
        max_score = int(analyzer_result.get("max_score", 10))
        final_score = int(parsed["final_score"])
        subject = (parsed.get("subject_confirmed") or analyzer_result.get("subject") or "").strip()
        subject_lower = subject.lower()
        is_quantitative = subject_lower in QUANT_SUBJECTS
        validated_summary = str(parsed.get("validated_summary", "")).lower()
        reason = str(parsed.get("reason", "")).lower()
        validated_mistakes = parsed.get("validated_mistakes", [])
        first_wrong_step = str(parsed.get("first_wrong_step") or "").strip()
        validated_detailed = parsed.get("validated_detailed_mistakes", [])

        if first_wrong_step and validated_detailed:
            first_detail = validated_detailed[0]
            if isinstance(first_detail, dict):
                first_detail = dict(first_detail)
                first_detail["location"] = first_wrong_step
                validated_detailed = [first_detail] + list(validated_detailed[1:])
                parsed["validated_detailed_mistakes"] = validated_detailed

        if parsed.get("contradiction_found"):
            parsed["override"] = True
        if parsed.get("error_location_correct") is False:
            parsed["override"] = True
        if parsed.get("error_type_correct") is False:
            parsed["override"] = True
        if parsed.get("explanation_specific_enough") is False:
            parsed["override"] = True
        if is_quantitative and parsed.get("final_answer_correct") is False:
            final_score = 4
            parsed["override"] = True
        if parsed.get("math_error_found") is True and final_score > 6:
            final_score = 6
            parsed["override"] = True
        if (
            is_quantitative
            and parsed.get("final_answer_correct") is True
            and parsed.get("math_error_found") is False
            and not validated_mistakes
            and final_score < max_score
            and (
                "10 out of 10" in reason
                or "full score" in reason
                or "correct solution" in validated_summary
                or "correctly solved" in validated_summary
            )
        ):
            final_score = max_score
            parsed["override"] = True
        if (
            is_quantitative
            and parsed.get("final_answer_correct") is True
            and parsed.get("math_error_found") is False
            and final_score < min(9, max_score)
        ):
            final_score = min(9, max_score)
            parsed["override"] = True

        parsed["final_score"] = final_score
        return parsed

    @staticmethod
    def _validator_failed(reason: str) -> dict[str, Any]:
        return {
            "is_valid": False,
            "override": False,
            "final_score": 0,
            "reason": reason,
            "validated_summary": "",
            "validated_mistakes": [],
            "validated_detailed_mistakes": [],
            "subject_confirmed": None,
            "analysis_consistent": False,
            "final_answer_correct": None,
            "math_error_found": None,
            "error_location_correct": False,
            "error_type_correct": False,
            "explanation_specific_enough": False,
            "first_wrong_step": None,
            "contradiction_found": False,
            "validator_failed": True,
        }


ollama_validator = OpenAIValidator()
