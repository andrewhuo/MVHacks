from __future__ import annotations

import asyncio
import json
import os
import random
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

FALLBACK_FACTS: list[str] = [
    "Most marine plastic begins on land and reaches the ocean through rivers and stormwater.",
    "Ghost nets can trap fish, turtles, and seabirds for years after being lost.",
    "Microplastics can move from plankton to fish and up the food chain.",
    "River interception systems can reduce downstream ocean trash loads significantly.",
    "Frequent shoreline cleanups remove newly arrived debris before it breaks down.",
    "Single-use packaging reduction is one of the fastest ways to cut litter volume.",
    "Entanglement injuries can reduce feeding success and survival in marine animals.",
    "Street litter often becomes ocean litter when heavy rain overwhelms drainage systems.",
    "Upstream waste sorting improves recycling quality and lowers environmental leakage.",
    "Preventing trash at source is usually cheaper than removing it offshore later.",
]

FALLBACK_QUIZZES: list[dict[str, Any]] = [
    {"id": "q01", "question": "Which path most often carries city plastic to the ocean?", "options": ["Rivers and drains", "Coral reefs", "Sea grass", "Open tides"], "correct": "A"},
    {"id": "q02", "question": "What is ghost gear?", "options": ["Abandoned fishing gear", "A sonar system", "A weather front", "A ship coating"], "correct": "A"},
    {"id": "q03", "question": "Why are microplastics harmful?", "options": ["They are nutritious", "They vanish instantly", "They move through food webs", "They cool oceans"], "correct": "C"},
    {"id": "q04", "question": "Best interception point for floating trash?", "options": ["Deep ocean", "River mouths", "Seafloor trenches", "Open bays only"], "correct": "B"},
    {"id": "q05", "question": "Which animal often mistakes plastic bags for prey?", "options": ["Sea turtles", "Swordfish", "Seals", "Shrimp"], "correct": "A"},
    {"id": "q06", "question": "What reduces plastic leakage long-term?", "options": ["More packaging", "Single-use growth", "Waste reduction", "Offshore dumping"], "correct": "C"},
    {"id": "q07", "question": "Why do repeated cleanups help?", "options": ["Remove newly arriving debris", "Change moon phases", "Reduce wind", "Lower salinity"], "correct": "A"},
    {"id": "q08", "question": "Stormwater can carry litter from where?", "options": ["Roads and sidewalks", "Coral polyps", "Whale pods", "Deep vents"], "correct": "A"},
    {"id": "q09", "question": "Primary risk of entanglement debris?", "options": ["Animal injury", "Warmer water", "Lower oxygen", "Less sunlight"], "correct": "A"},
    {"id": "q10", "question": "Why keep harbors cleaner upstream?", "options": ["Less ocean-bound trash", "More wave height", "Faster currents", "More algae"], "correct": "A"},
]


FALLBACK_TIPS: list[str] = [
    "Carry a reusable bottle and bag to reduce single-use plastic waste.",
    "Pick up five pieces of litter whenever you visit a beach or shoreline.",
    "Secure trash bins so wind and rain cannot wash waste into drains.",
    "Avoid products with microbeads and choose ocean-safe alternatives.",
    "Join a local cleanup event and report heavy litter hotspots.",
    "Sort recyclables correctly to reduce contamination and landfill leakage.",
    "Use refill stations and bulk options to cut packaging waste.",
    "Dispose of fishing line properly to prevent marine entanglement.",
    "Encourage schools and clubs to run monthly cleanup challenges.",
    "Support policies that improve stormwater filters and river trash capture.",
]


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


def choose_fallback_fact(previous_fallback_fact: str = "", previous_fact: str = "") -> tuple[str, str]:
    exclude = {previous_fallback_fact.strip(), previous_fact.strip()}
    candidates = [f for f in FALLBACK_FACTS if f not in exclude]
    chosen = random.choice(candidates if candidates else FALLBACK_FACTS)
    return chosen, chosen


def choose_fallback_tip(previous_fallback_tip: str = "", previous_tip: str = "") -> tuple[str, str]:
    exclude = {previous_fallback_tip.strip(), previous_tip.strip()}
    candidates = [t for t in FALLBACK_TIPS if t not in exclude]
    chosen = random.choice(candidates if candidates else FALLBACK_TIPS)
    return chosen, chosen


def choose_fallback_quiz(
    num_questions: int = 1,
    previous_fallback_quiz_key: str = "",
) -> tuple[list[dict[str, Any]], str]:
    q_count = max(1, min(int(num_questions), len(FALLBACK_QUIZZES)))
    choice = random.sample(FALLBACK_QUIZZES, k=q_count)
    key = "|".join(sorted(str(c.get("id", "")) for c in choice))

    tries = 0
    while key == previous_fallback_quiz_key and tries < 8:
        choice = random.sample(FALLBACK_QUIZZES, k=q_count)
        key = "|".join(sorted(str(c.get("id", "")) for c in choice))
        tries += 1

    cleaned = [
        {
            "question": str(c.get("question", "")),
            "options": list(c.get("options", []))[:4],
            "correct": str(c.get("correct", "A")).upper()[:1],
        }
        for c in choice
    ]
    return cleaned, key


async def generate_ocean_fact_async(previous_fact: str = "") -> str:
    topics = [
        "microplastics",
        "ghost fishing gear",
        "river-to-ocean plastic flow",
        "coral reef impacts",
        "seabird and turtle safety",
        "waste reduction and recycling",
        "coastal cleanup impact",
        "ocean food web contamination",
    ]
    styles = [
        "numerical",
        "cause-and-effect",
        "short practical tip",
        "species-focused",
        "policy-focused",
    ]

    topic = random.choice(topics)
    style = random.choice(styles)
    avoid = previous_fact.strip()

    prompt = (
        "Generate one short, accurate ocean fact in under 22 words. "
        f"Focus on {topic}. Style: {style}. "
        "No hashtags, no emojis. Use a different sentence each call."
    )
    if avoid:
        prompt += f" Do not repeat this sentence: {avoid}"

    fact = (await generate_text(prompt)).strip()
    if fact:
        return fact

    fallback_fact, _ = choose_fallback_fact(previous_fallback_fact="", previous_fact=avoid)
    return fallback_fact


async def generate_ocean_tip_async(previous_tip: str = "") -> str:
    avoid = previous_tip.strip()
    prompt = (
        "Give one short practical action tip to reduce ocean trash, under 20 words. "
        "Actionable and realistic. No hashtags, no emojis."
    )
    if avoid:
        prompt += f" Do not repeat this sentence: {avoid}"

    tip = (await generate_text(prompt)).strip()
    if tip:
        return tip

    fallback_tip, _ = choose_fallback_tip(previous_fallback_tip="", previous_tip=avoid)
    return fallback_tip
