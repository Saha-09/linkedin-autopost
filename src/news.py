"""Pull recent, India-focused headlines per lane from Google News RSS.

Free, no API key, no auth. Gives each post a concrete, current hook from the
last ~2 days so you're never posting stale or vague takes.
"""
import datetime as dt
import urllib.parse
import xml.etree.ElementTree as ET

import requests

RSS = "https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"


def recent_headlines(query: str, days: int = 2, limit: int = 8) -> list[dict]:
    """Return [{title, source, published, link}] from the last `days` days."""
    url = RSS.format(q=urllib.parse.quote(f"{query} when:{days}d"))
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception:
        return []

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        source_el = item.find("source")
        source = source_el.text.strip() if source_el is not None and source_el.text else ""
        pub_raw = item.findtext("pubDate") or ""
        try:
            pub = dt.datetime.strptime(pub_raw, "%a, %d %b %Y %H:%M:%S %Z").replace(
                tzinfo=dt.timezone.utc)
        except ValueError:
            pub = None
        if pub and pub < cutoff:
            continue
        out.append({"title": title, "source": source,
                    "published": pub.isoformat() if pub else "", "link": link})
        if len(out) >= limit:
            break
    return out


def as_prompt_block(items: list[dict]) -> str:
    if not items:
        return ""
    lines = ["Recent headlines (last 2 days) — pick ONE as a SPRINGBOARD. Do not "
             "report it; interpret what it signals and give your own take. Use the "
             "real company/person names from it:"]
    for it in items:
        src = f" ({it['source']})" if it["source"] else ""
        lines.append(f"- {it['title']}{src}")
    return "\n".join(lines)
