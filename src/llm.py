"""Pluggable LLM call. Pick a provider via env; all return plain text.

Keeping this abstracted means you can start on a free tier (Gemini/Groq) and
swap to Claude/OpenAI later by changing two env vars, no code change.
"""
import os
import requests

_DEFAULT_MODELS = {
    "gemini": "gemini-2.0-flash",
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o-mini",
}


def complete(system_prompt: str, user_prompt: str, temperature: float = 0.9) -> str:
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    key = os.environ["LLM_API_KEY"]
    model = os.environ.get("LLM_MODEL") or _DEFAULT_MODELS[provider]

    if provider == "gemini":
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={key}"
        )
        body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        r = requests.post(url, json=body, timeout=60)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    if provider == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
    elif provider == "openai":
        url = "https://api.openai.com/v1/chat/completions"
    elif provider == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")

    if provider == "anthropic":
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        body = {
            "model": model,
            "max_tokens": 1024,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        r = requests.post(url, json=body, headers=headers, timeout=60)
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()

    # OpenAI-compatible (groq / openai)
    headers = {"Authorization": f"Bearer {key}"}
    body = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    r = requests.post(url, json=body, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()
