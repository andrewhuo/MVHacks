from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

# Env var first; hackathon fallback key keeps local testing fast.
API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDeZbXRD3wcPu3bRwCN5ZTWNQRCbM-X1DM").strip()

DEFAULT_MODEL = "gemini-2.0-flash"
API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={api_key}"
)


def _extract_text_from_gemini_response(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        return ""

    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text_chunks: list[str] = []
    for part in parts:
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            text_chunks.append(text.strip())
    return "\n".join(text_chunks)


async def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")

    if sys.platform == "emscripten":
        # Browser / pygbag path: JS fetch is non-blocking and wasm-safe.
        try:
            from js import fetch  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Browser fetch unavailable: {exc}") from exc

        options = {
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": body.decode("utf-8"),
        }
        response = await fetch(url, options)
        ok = bool(getattr(response, "ok", False))
        text = str(await response.text())
        if not ok:
            raise RuntimeError(f"Gemini HTTP error in browser: {text[:200]}")
        return json.loads(text)

    # Desktop fallback: run blocking urllib in a worker thread.
    def _sync_request() -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Gemini HTTP {exc.code}: {detail[:300]}") from exc

    return await asyncio.to_thread(_sync_request)


async def generate_text(prompt: str, model: str = DEFAULT_MODEL) -> str:
    if not API_KEY:
        return ""

    url = API_URL_TEMPLATE.format(model=model, api_key=API_KEY)
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                ]
            }
        ]
    }

    try:
        data = await _post_json(url, payload)
        return _extract_text_from_gemini_response(data)
    except Exception as exc:
        print(f"Gemini request failed: {exc}")
        return ""


async def generate_ocean_cleanup_quiz_async(num_questions: int = 5) -> list[dict[str, Any]]:
    num_questions = max(1, int(num_questions))
    prompt = f"""
Generate {num_questions} multiple-choice questions about ocean trash cleanup.
Return plain text using this exact format per question:
Question: <text>
A) <option>
B) <option>
C) <option>
D) <option>
Correct: <A/B/C/D>
---
Keep questions concise and educational.
""".strip()

    content = await generate_text(prompt)
    if not content:
        return []

    questions: list[dict[str, Any]] = []
    for section in content.split("---"):
        if "Question:" not in section or "Correct:" not in section:
            continue

        question = ""
        options: list[str] = []
        correct = ""

        for raw_line in section.splitlines():
            line = raw_line.strip()
            if line.startswith("Question:"):
                question = line.replace("Question:", "", 1).strip()
            elif line.startswith(("A)", "B)", "C)", "D)")):
                options.append(line[2:].strip())
            elif line.startswith("Correct:"):
                correct = line.replace("Correct:", "", 1).strip().upper()[:1]

        if question and len(options) == 4 and correct in {"A", "B", "C", "D"}:
            questions.append(
                {
                    "question": question,
                    "options": options,
                    "correct": correct,
                }
            )

    return questions[:num_questions]


def generate_ocean_cleanup_quiz(num_questions: int = 5) -> list[dict[str, Any]]:
    """Sync wrapper; in async loops (pygbag) use generate_ocean_cleanup_quiz_async."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return []

    return asyncio.run(generate_ocean_cleanup_quiz_async(num_questions=num_questions))


def display_quiz(questions: list[dict[str, Any]]) -> str:
    if not questions:
        return "No quiz questions available."

    lines = ["Ocean Cleanup Quiz", ""]
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. {q.get('question', '')}")
        opts = q.get("options", [])
        for j, option in enumerate(opts):
            lines.append(f"   {chr(65 + j)}) {option}")
        lines.append(f"   Correct Answer: {q.get('correct', '?')}")
        lines.append("")
    return "\n".join(lines)


async def generate_ocean_fact_async() -> str:
    prompt = "Give one short, accurate ocean cleanup fact in under 22 words. No hashtags, no emojis."
    return await generate_text(prompt)
