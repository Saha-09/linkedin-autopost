"""Pluggable LLM call. Pick a provider via env; all return plain text."""
import os
import time
import requests

_DEFAULT_MODELS = {
    "gemini": "gemini-flash-latest",
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o-mini",
}

TIMEOUT = 180  # newer models can take >60s to respond


def _post(url, **kwargs):
    """POST with a longer timeout and up to 3 tries on timeout/connection errors."""
    last = None
    for attempt in range(3):
        try:
            return requests.post(url, timeout=TIMEOUT, **kwargs)
        except (requests.Timeout, requests.ConnectionError) as e:
            last = e
            print(f"request attempt {attempt+1} failed ({e}); retrying...")
            time.sleep(5)
    raise last


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
        r = _post(url, json=body)
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
        r = _post(url, json=body, headers=headers)
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()

    headers = {"Authorization": f"Bearer {key}"}
    body = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    r = _post(url, json=body, headers=headers)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()
