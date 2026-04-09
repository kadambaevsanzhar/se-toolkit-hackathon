"""Shared AI contracts for analyzer, validator, and normalization."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


SUPPORTED_ACTION = "Please upload a clear photo of homework or a written academic answer."


class DetailedMistake(BaseModel):
    type: str = Field(min_length=1, max_length=50)
    location: str = Field(min_length=1, max_length=200)
    what: str = Field(min_length=1, max_length=500)
    why: str = Field(min_length=1, max_length=500)
    how_to_fix: str = Field(min_length=1, max_length=500)


class AcademicClassification(BaseModel):
    is_academic_submission: bool
    subject: str | None = Field(default=None, max_length=100)
    reason: str = Field(min_length=1, max_length=300)
    supported_action: str = Field(default=SUPPORTED_ACTION, min_length=1, max_length=300)


class AnalyzerOutput(BaseModel):
    is_academic_submission: Literal[True] = True
    student_name: str | None = Field(default=None, max_length=120)
    subject: str = Field(min_length=1, max_length=100)
    topic: str = Field(min_length=1, max_length=120)
    task_title: str = Field(min_length=1, max_length=200)
    reconstructed_task_text: str = Field(min_length=1, max_length=500)
    student_answer_text: str = Field(min_length=1, max_length=500)
    observed_steps: list[str] = Field(default_factory=list, min_length=1, max_length=8)
    suggested_score: int = Field(ge=0, le=10)
    max_score: int = Field(ge=1, le=10)
    short_feedback: str = Field(min_length=1, max_length=400)
    strengths: list[str] = Field(default_factory=list, min_length=2, max_length=3)
    mistakes: list[str] = Field(default_factory=list, max_length=2)
    detailed_mistakes: list[DetailedMistake] = Field(default_factory=list, max_length=2)
    improvement_suggestions: list[str] = Field(default_factory=list, min_length=1, max_length=1)
    next_steps: list[str] = Field(default_factory=list, min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_list_contract(self):
        if len(self.mistakes) != len(self.detailed_mistakes):
            raise ValueError("detailed_mistakes must exactly match mistakes count")
        return self


class ValidatorOutput(BaseModel):
    is_valid: bool
    override: bool
    final_score: int = Field(ge=0, le=10)
    reason: str = Field(min_length=1, max_length=500)
    validated_summary: str = Field(min_length=1, max_length=400)
    validated_mistakes: list[str] = Field(default_factory=list, max_length=2)
    validated_detailed_mistakes: list[DetailedMistake] = Field(default_factory=list, max_length=2)
    subject_confirmed: str | None = Field(default=None, max_length=100)
    analysis_consistent: bool
    final_answer_correct: bool | None
    math_error_found: bool | None
    error_location_correct: bool
    error_type_correct: bool
    explanation_specific_enough: bool
    first_wrong_step: str | None = Field(default=None, max_length=200)
    contradiction_found: bool

    @model_validator(mode="after")
    def validate_mistake_contract(self):
        if len(self.validated_mistakes) != len(self.validated_detailed_mistakes):
            raise ValueError("validated_detailed_mistakes must exactly match validated_mistakes count")
        return self
