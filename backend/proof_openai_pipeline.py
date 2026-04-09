#!/usr/bin/env python3
"""Proof runner for the hardened OpenAI grading pipeline."""

from __future__ import annotations

import asyncio
import io
import json
from contextlib import contextmanager
from typing import Callable

from PIL import Image, ImageDraw

from ai.analyzer.openai_analyzer import analyzer_service
from ai.contracts import AnalyzerOutput, ValidatorOutput
from ai.validator.openai_validator import ollama_validator
from main import analyze_homework


def build_text_image(lines: list[str], path: str) -> bytes:
    image = Image.new("RGB", (1100, 800), color="white")
    draw = ImageDraw.Draw(image)
    y = 40
    for line in lines:
        draw.text((40, y), line, fill="black")
        y += 42
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()
    with open(path, "wb") as handle:
        handle.write(data)
    return data


@contextmanager
def patch_post_once(client, replacement: Callable):
    original = client._post
    state = {"count": 0}

    async def wrapped(payload):
        state["count"] += 1
        if state["count"] == 1:
            return await replacement(payload)
        return await original(payload)

    client._post = wrapped
    try:
        yield
    finally:
        client._post = original


@contextmanager
def patch_post_always(client, replacement: Callable):
    original = client._post

    async def wrapped(payload):
        return await replacement(payload)

    client._post = wrapped
    try:
        yield
    finally:
        client._post = original


async def malformed_json(_payload):
    return {"output": [{"content": [{"type": "output_text", "text": "{bad json"}]}]}


async def run_case(title: str, filename: str, image_data: bytes):
    result = await analyze_homework(image_data, filename)
    print(f"\n=== {title} ===")
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    return result


async def main():
    if not analyzer_service.client.configured:
        raise SystemExit("OPENAI_API_KEY is required for proof_openai_pipeline.py")

    math_ok_1 = build_text_image(
        ["Solve:", "5x = 20", "", "x = 4"],
        "/tmp/proof_math_ok_1.png",
    )
    math_ok_2 = build_text_image(
        ["Solve:", "3x - 4 = 11", "", "3x = 15", "x = 5"],
        "/tmp/proof_math_ok_2.png",
    )
    math_bad = build_text_image(
        ["Solve:", "3x - 4 = 11", "", "3x = 15", "x = 4"],
        "/tmp/proof_math_bad.png",
    )
    history_case = build_text_image(
        [
            "History homework",
            "Question: Why did the Silk Road matter?",
            "Answer:",
            "It connected regions, spread goods and ideas,",
            "and supported cultural exchange.",
        ],
        "/tmp/proof_history.png",
    )
    non_academic = build_text_image(
        ["Vacation photo", "Sunset at the beach", "No homework here"],
        "/tmp/proof_non_academic.png",
    )
    unreadable = Image.effect_noise((600, 400), 100.0)
    buf = io.BytesIO()
    unreadable.save(buf, format="PNG")
    unreadable_data = buf.getvalue()

    print("OLD_PROVIDER_PATH=OpenRouter Qwen analyzer + Ollama validator via chat.completions")
    print("NEW_PROVIDER_PATH=OpenAI Responses API -> analyzer_service / ollama_validator")
    print("\nANALYZER_SCHEMA=")
    print(json.dumps(AnalyzerOutput.model_json_schema(), indent=2))
    print("\nVALIDATOR_SCHEMA=")
    print(json.dumps(ValidatorOutput.model_json_schema(), indent=2))

    await run_case("TEST 1", "proof_math_ok_1.png", math_ok_1)
    analyzer_raw = analyzer_service.client.last_output_text
    validator_raw = ollama_validator.client.last_output_text

    await run_case("TEST 2", "proof_math_ok_2.png", math_ok_2)
    await run_case("TEST 3", "proof_math_bad.png", math_bad)
    await run_case("TEST 4", "proof_history.png", history_case)
    await run_case("TEST 5", "proof_non_academic.png", non_academic)
    await run_case("TEST 6", "proof_unreadable.png", unreadable_data)

    with patch_post_once(analyzer_service.client, malformed_json):
        await run_case("TEST 7_REPAIR_SUCCESS", "proof_math_ok_1.png", math_ok_1)

    with patch_post_always(ollama_validator.client, malformed_json):
        await run_case("TEST 8_VALIDATOR_FAILED", "proof_math_ok_1.png", math_ok_1)

    stable_runs = []
    for idx in range(3):
        stable_runs.append((await analyze_homework(math_ok_2, f"proof_stable_{idx}.png")).model_dump())
    print("\n=== TEST 9_STABILITY ===")
    print(json.dumps(stable_runs, ensure_ascii=False, indent=2))

    with patch_post_always(analyzer_service.client, malformed_json):
        failed = await analyze_homework(math_ok_1, "proof_analyzer_fail.png")
        print("\n=== ANALYZER_FAILED_EXAMPLE ===")
        print(json.dumps(failed.model_dump(), ensure_ascii=False, indent=2))

    print("\n=== ANALYZER_RAW_OUTPUT ===")
    print(analyzer_raw)
    print("\n=== VALIDATOR_RAW_OUTPUT ===")
    print(validator_raw)


if __name__ == "__main__":
    asyncio.run(main())
