"""OpenAI Responses API analyzer for homework photos."""

from __future__ import annotations

import logging
import os
from typing import Any

from ai.contracts import AcademicClassification, AnalyzerOutput
from ai.grading_guidance import GENERAL_GRADING_GUIDANCE
from ai.openai_responses import OpenAIResponsesClient, ResponsesAPIError

logger = logging.getLogger(__name__)

ANALYZER_REPAIR = "Return valid JSON only. Follow the schema exactly. Do not add prose."


class OpenAIAnalyzer:
    """Analyzer backed by OpenAI Responses API."""

    def __init__(self) -> None:
        self.model = os.getenv("OPENAI_ANALYZER_MODEL", "qwen/qwen3-vl-8b-instruct")
        self.max_score = int(os.getenv("AI_MAX_SCORE", "10"))
        self.client = OpenAIResponsesClient()

    async def classify_image(self, image_data: bytes, image_mime_type: str = "image/jpeg") -> dict[str, Any]:
        """Classify whether the image is a readable academic submission."""
        if not self.client.configured:
            raise ResponsesAPIError("OPENAI_API_KEY is not configured")

        return await self.client.create_json_chat_completion(
            model=self.model,
            schema_model=AcademicClassification,
            prompt_text=(
                "You classify images for a homework grading pipeline. "
                "Reject non-academic, unreadable, blank, or unrelated images. "
                "Accept readable academic content even if it is short, unfinished, or only a single answer sentence."
                "\n\n"
                "Decide whether this image contains enough readable academic content for reliable grading. "
                "If the image shows a school-subject answer, claim, explanation, correction, worksheet, notebook entry, "
                "essay fragment, history statement, literature response, language exercise, science answer, or conceptual explanation, "
                "treat it as academic. "
                "Only set is_academic_submission to false when the image is truly non-academic, unreadable, blank, or lacks enough visible content to grade reliably. "
                "If not academic, explain why briefly."
            ),
            image_data=image_data,
            image_mime_type=image_mime_type,
            repair_instruction=ANALYZER_REPAIR,
            max_tokens=800,
        )

    async def analyze_homework_image(
        self,
        image_data: bytes,
        filename: str,
        image_mime_type: str = "image/jpeg",
        repair_context: str | None = None,
    ) -> dict[str, Any]:
        """Analyze an academic homework image with strict structured output."""
        if not self.client.configured:
            raise ResponsesAPIError("OPENAI_API_KEY is not configured")

        repair_note = ""
        if repair_context:
            repair_note = f"\n\nPrevious analysis was rejected by the validator: {repair_context}"

        result = await self.client.create_json_chat_completion(
            model=self.model,
            schema_model=AnalyzerOutput,
            prompt_text=(
                "You are the primary homework analyzer in a production grading pipeline. "
                "Read the image carefully and grade fairly across academic subjects. "
                "Reconstruct the student's reasoning in order before scoring. "
                "Identify the first real error, not merely a later consequence. "
                "Do not hallucinate unreadable text. Do not grade non-academic images. "
                "Do not blame an earlier step if it is actually correct. "
                "Do not praise correctness if there is a real mistake. "
                "Return only the requested JSON object."
                "\n\n"
                f"Analyze the academic submission in file '{filename}'.{repair_note}\n\n"
                "Requirements:\n"
                "- Detect subject, topic, and task_title.\n"
                "- Reconstruct the task only if it is readable.\n"
                "- Understand the student's answer from the image itself.\n"
                "- reconstructed_task_text must restate the visible task in plain text.\n"
                "- student_answer_text must restate the student's visible answer in plain text.\n"
                "- observed_steps must list the student's visible reasoning steps in order, ending with the final visible answer.\n"
                "- Reconstruct the student's reasoning step by step before assigning a score.\n"
                "- Distinguish correct steps from the first real wrong step.\n"
                "- If there is a real mistake, detailed_mistakes must describe the first real mistake, not a correct earlier step.\n"
                "- For each detailed mistake, explain where it occurs, what is wrong, why it is wrong, what the correct step or claim should be, and how to fix it.\n"
                "- For history, literature, social science, language, biology, geography, economics, and computer science answers, name the first materially false, unsupported, irrelevant, or incomplete part when one exists.\n"
                "- Support mathematics, physics, chemistry, biology, history, geography, literature, "
                "English/language learning, computer science, economics, and similar school subjects.\n"
                f"- Use this shared grading guidance exactly:\n{GENERAL_GRADING_GUIDANCE}\n"
                f"- max_score must be exactly {self.max_score}.\n"
                "- strengths must contain exactly 2 or 3 items.\n"
                "- mistakes must contain 0 to 2 items.\n"
                "- detailed_mistakes count must exactly match mistakes count.\n"
                "- improvement_suggestions must contain exactly 1 item.\n"
                "- next_steps must contain exactly 3 items.\n"
                "- Keep strengths and mistakes non-contradictory.\n"
                "- If a mistake exists, mention it in mistakes and detailed_mistakes.\n"
                "- Do not call a mathematically, logically, or factually correct step wrong.\n"
                "- improvement_suggestions and next_steps must be practical and concise."
            ),
            image_data=image_data,
            image_mime_type=image_mime_type,
            repair_instruction=ANALYZER_REPAIR,
            max_tokens=800,
        )

        if self._has_internal_contradiction(result):
            logger.warning("Analyzer output contradicted itself, retrying via repair instruction")
            result = await self.client.create_json_chat_completion(
                model=self.model,
                schema_model=AnalyzerOutput,
                prompt_text=(
                    "You are the primary homework analyzer in a production grading pipeline. "
                    "Return only valid JSON and remove contradictions between strengths, mistakes, feedback, and score. "
                    "If there is a real mistake, identify the first real wrong step instead of blaming an earlier correct step."
                    "\n\n"
                    f"Re-analyze the academic submission in file '{filename}'. "
                    "Your previous answer was contradictory. "
                    "Return valid JSON only. Follow the schema exactly. Do not add prose. "
                    "Ensure mistakes and detailed_mistakes identify the first real error precisely."
                ),
                image_data=image_data,
                image_mime_type=image_mime_type,
                repair_instruction=ANALYZER_REPAIR,
                max_tokens=800,
            )
            if self._has_internal_contradiction(result):
                raise ResponsesAPIError("Analyzer returned contradictory output after repair")

        return result

    @staticmethod
    def _has_internal_contradiction(result: dict[str, Any]) -> bool:
        mistakes_text = " ".join(result.get("mistakes", [])).lower()
        strengths_text = " ".join(result.get("strengths", [])).lower()
        summary = str(result.get("short_feedback", "")).lower()
        summary_tokens = ("fully correct", "completely correct", "no mistakes", "perfect answer")
        strength_tokens = ("correct final answer", "correct solution", "no mistakes", "perfect work")
        if mistakes_text and any(token in summary for token in summary_tokens):
            return True
        if mistakes_text and any(token in strengths_text for token in strength_tokens):
            return True
        return False


analyzer_service = OpenAIAnalyzer()
