"""Thin Telegram wrapper: send a draft with Approve/Skip buttons, read callbacks."""
import os
import requests

BASE = "https://api.telegram.org/bot{token}/{method}"


def _token():
    return os.environ["TELEGRAM_BOT_TOKEN"]


def _call(method, **params):
    r = requests.post(BASE.format(token=_token(), method=method), json=params, timeout=30)
    r.raise_for_status()
    return r.json()


def send_draft(draft_id: str, lane: str, text: str, tags: str = "none"):
    """Send one candidate post with inline Approve/Skip buttons.
    Hashtags are already in `text` and post automatically. `tags` are @mention
    suggestions you add by hand when posting (the API can't tag people reliably)."""
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    header = f"🗞️ Draft [{lane}] — approve to post to LinkedIn:\n\n"
    footer = ""
    if tags and tags.lower() != "none":
        # strip '@' so Telegram doesn't turn names into broken t.me links
        clean = tags.replace("@", "")
        footer = ("\n\n— — —\n👉 Worth @-tagging on LinkedIn (type @ and their name "
                  "in the post or first comment):\n" + clean)
    _call(
        "sendMessage",
        chat_id=chat_id,
        text=header + text + footer,
        reply_markup={
            "inline_keyboard": [[
                {"text": "✅ Approve & Post", "callback_data": f"ok:{draft_id}"},
                {"text": "🗑️ Skip", "callback_data": f"no:{draft_id}"},
            ]]
        },
    )


def get_callbacks(offset: int | None = None):
    """Return (updates, next_offset). Only callback_query updates are relevant."""
    params = {"timeout": 0, "allowed_updates": ["callback_query"]}
    if offset is not None:
        params["offset"] = offset
    res = _call("getUpdates", **params)
    updates = res.get("result", [])
    next_offset = (updates[-1]["update_id"] + 1) if updates else offset
    return updates, next_offset


def answer_callback(callback_id: str, text: str):
    _call("answerCallbackQuery", callback_query_id=callback_id, text=text)


def notify(text: str):
    _call("sendMessage", chat_id=os.environ["TELEGRAM_CHAT_ID"], text=text)
