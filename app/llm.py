"""
Generates reply text using Groq's chat completions API.
"""

import os
import asyncio
import httpx

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Kept simple on purpose: just an instruction + the email itself.
# You can extend this later with company info, tone, rules, etc.
SYSTEM_INSTRUCTION = (
    "You are an email assistant. Write a short, professional, clear reply "
    "to the email below. Do not invent facts you don't know (like specific "
    "dates or commitments) — if information is missing, ask a brief "
    "clarifying question instead of guessing."
)


async def _call_groq(subject: str, body: str, temperature: float) -> str:
    prompt = f"Subject: {subject}\n\nBody:\n{body}"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 500,
                "temperature": temperature,
            },
        )

    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


async def generate_reply(subject: str, body: str) -> str:
    """Generate a single reply (used by the original single-draft flow)."""
    return await _call_groq(subject, body, temperature=0.7)


async def generate_reply_variations(subject: str, body: str, count: int = 3) -> list[str]:
    """
    Generate several different reply drafts for the same email, so a human
    can pick the best one instead of getting just one AI guess.

    Each call uses a different "temperature" (how much randomness/creativity
    the model uses) so the versions actually read differently from each
    other, rather than being near-identical.
    """
    temperatures = [0.3, 0.7, 1.0][:count]
    # pad with 0.7 if someone asks for more than 3 variations
    while len(temperatures) < count:
        temperatures.append(0.7)

    tasks = [_call_groq(subject, body, temp) for temp in temperatures]
    return await asyncio.gather(*tasks)

