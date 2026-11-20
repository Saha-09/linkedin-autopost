"""Generate post drafts in Soumyadeep's voice, run guardrails, queue them,
and send to Telegram for approval. Triggered by the scheduled workflow.
"""
import json
import os
import pathlib
import random
import re
import time

import requests

import llm
import news
import telegram_client as tg

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUEUE = ROOT / "queue"
STATE = QUEUE / "state.json"
VOICE = (ROOT / "prompts" / "voice_system_prompt.md").read_text(encoding="utf-8")
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


# ---------- Unicode bold (LinkedIn has no real bold) ----------
def _bold_char(c: str) -> str:
    if "A" <= c <= "Z":
        return chr(0x1D400 + (ord(c) - ord("A")))
    if "a" <= c <= "z":
        return chr(0x1D41A + (ord(c) - ord("a")))
    if "0" <= c <= "9":
        return chr(0x1D7CE + (ord(c) - ord("0")))
    return c


def apply_bold(text: str) -> str:
    """Convert **marked** spans to Unicode bold characters."""
    return re.sub(r"\*\*(.+?)\*\*", lambda m: "".join(_bold_char(c) for c in m.group(1)), text)


def strip_bold_markers(text: str) -> str:
    return text.replace("**", "")


# ---------- state ----------
def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"recent_lanes": [], "last_update_id": None}


def save_state(state: dict):
    STATE.write_text(json.dumps(state, indent=2))


def pick_lane(state: dict) -> dict:
    """Weighted pick, avoiding the last 2 lanes so topics don't repeat."""
    lanes = CONFIG["topic_lanes"]
    recent = set(state.get("recent_lanes", [])[-2:])
    pool = [l for l in lanes if l["name"] not in recent] or lanes
    weights = [l.get("weight", 1) for l in pool]
    return random.choices(pool, weights=weights, k=1)[0]


def fetch_brief() -> str:
    url = os.environ.get("MARKET_BRIEF_URL", "").strip()
    if not url:
        return ""
    try:
        return requests.get(url, timeout=20).text[:6000]
    except Exception:
        return ""


def passes_checks(text: str) -> tuple[bool, str]:
    c = CONFIG["checks"]
    words = len(text.split())
    if words > c["max_words"]:
        return False, f"too long ({words}w)"
    if words < c["min_words"]:
        return False, f"too short ({words}w)"
    if text.count("#") > c["max_hashtags"]:
        return False, "too many hashtags"
    low = text.lower()
    for p in c["ban_phrases"]:
        if p in low:
            return False, f"ban phrase: {p}"
    return True, "ok"


def build_user_prompt(lane: dict, brief: str, headlines_block: str) -> str:
    today = time.strftime("%d %b %Y")
    parts = [
        f"Today is {today}. Write ONE LinkedIn post in the '{lane['name']}' lane.",
        f"Lane focus: {lane['desc']}.",
        "Follow the standard structure and style exactly. Make it post-ready.",
    ]
    if headlines_block:
        parts.append(headlines_block)
    if brief:
        parts.append("Extra source — today's market brief:\n\n" + brief)
    if not headlines_block and not brief:
        parts.append("No fresh sources available. Use a widely-known current theme in "
                     "this lane and keep figures qualitative.")
    pool = CONFIG.get("tagging", {}).get("evergreen_pool", [])
    if pool:
        parts.append("Broad hashtags you may blend with specific ones: " + ", ".join(pool))
    return "\n\n".join(parts)


def split_post_and_tags(raw: str) -> tuple[str, str]:
    if "---TAGS---" in raw:
        body, _, tags = raw.partition("---TAGS---")
        return body.strip(), tags.strip()
    return raw.strip(), "none"


def main():
    state = load_state()
    brief = fetch_brief()
    n = CONFIG["drafts_per_run"]
    sent = 0

    for _ in range(n):
        lane = pick_lane(state)
        headlines = news.recent_headlines(lane.get("news_query", lane["desc"]))
        headlines_block = news.as_prompt_block(headlines)
        user_prompt = build_user_prompt(lane, brief, headlines_block)

        body, tags = "", "none"
        for attempt in range(3):  # retry if guardrails reject
            raw = llm.complete(VOICE, user_prompt, temperature=0.95)
            raw_body, tags = split_post_and_tags(raw)
            ok, reason = passes_checks(strip_bold_markers(raw_body))
            if ok:
                body = apply_bold(raw_body)  # render bold only after checks pass
                break
            print(f"[{lane['name']}] rejected ({reason}), retry {attempt+1}")
        else:
            print(f"[{lane['name']}] skipped after retries")
            continue

        draft_id = f"{int(time.time())}{random.randint(10,99)}"
        (QUEUE / f"{draft_id}.json").write_text(json.dumps({
            "id": draft_id, "lane": lane["name"], "text": body, "tags": tags,
            "created": time.time(), "posted": False,
        }, indent=2))
        tg.send_draft(draft_id, lane["name"], body, tags)
        state.setdefault("recent_lanes", []).append(lane["name"])
        sent += 1

    state["recent_lanes"] = state.get("recent_lanes", [])[-10:]
    save_state(state)
    print(f"Sent {sent} draft(s) for approval.")


if __name__ == "__main__":
    main()
