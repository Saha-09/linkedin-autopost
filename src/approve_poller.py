"""Poll Telegram for Approve/Skip taps and act on them.

Runs on a short cron (e.g. every 15 min). When you tap:
  ✅ Approve → posts the queued draft to LinkedIn via the official API
  🗑️ Skip    → discards the draft
Idempotent: a draft is posted at most once (file marked posted / removed).
"""
import json
import pathlib
import time

import linkedin_client
import telegram_client as tg

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUEUE = ROOT / "queue"
STATE = QUEUE / "state.json"
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
VERSION = CONFIG["linkedin_version"]


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {"last_update_id": None}


def save_state(s: dict):
    STATE.write_text(json.dumps(s, indent=2))


def draft_path(draft_id: str) -> pathlib.Path:
    return QUEUE / f"{draft_id}.json"


def main():
    state = load_state()
    updates, next_offset = tg.get_callbacks(state.get("last_update_id"))

    for u in updates:
        cb = u.get("callback_query")
        if not cb:
            continue
        data = cb.get("data", "")
        cb_id = cb["id"]
        action, _, draft_id = data.partition(":")
        p = draft_path(draft_id)

        if not p.exists():
            tg.answer_callback(cb_id, "That draft is no longer in the queue.")
            continue

        draft = json.loads(p.read_text())
        if draft.get("posted"):
            tg.answer_callback(cb_id, "Already posted.")
            continue

        if action == "no":
            p.unlink()
            tg.answer_callback(cb_id, "Skipped. 🗑️")
            tg.notify(f"Draft [{draft['lane']}] skipped.")
        elif action == "ok":
            try:
                urn = linkedin_client.post_text(draft["text"], version=VERSION)
                draft["posted"] = True
                draft["urn"] = urn
                p.write_text(json.dumps(draft, indent=2))
                tg.answer_callback(cb_id, "Posted to LinkedIn ✅")
                tg.notify(f"✅ Posted to LinkedIn ({draft['lane']}).")
            except Exception as e:
                tg.answer_callback(cb_id, "Post failed — check logs.")
                tg.notify(f"⚠️ LinkedIn post failed: {e}")

    state["last_update_id"] = next_offset
    save_state(state)

    # Housekeeping: drop posted drafts older than 2 days.
    cutoff = time.time() - 2 * 86400
    for f in QUEUE.glob("*.json"):
        if f.name == "state.json":
            continue
        try:
            d = json.loads(f.read_text())
            if d.get("posted") and d.get("created", 0) < cutoff:
                f.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
