"""Post to your own LinkedIn personal profile via the official REST Posts API.

Uses the w_member_social scope (self-serve, no partner review). This is the
compliant rail: no browser session, no scraping, no simulated clicks.
"""
import os
import requests

API = "https://api.linkedin.com/rest/posts"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

# Characters LinkedIn's "little text" commentary treats as reserved; escape them.
_RESERVED = r"\|{}@[]()<>#*_~"


def _escape(text: str) -> str:
    out = []
    for ch in text:
        if ch in _RESERVED:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def refresh_access_token() -> str | None:
    """Try to refresh the 60-day token. Returns new token or None if no
    refresh token is configured (some self-serve apps aren't issued one)."""
    refresh = os.environ.get("LINKEDIN_REFRESH_TOKEN", "").strip()
    if not refresh:
        return None
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": os.environ["LINKEDIN_CLIENT_ID"],
            "client_secret": os.environ["LINKEDIN_CLIENT_SECRET"],
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("access_token")


def post_text(text: str, version: str = "202610") -> str:
    """Publish a public text post as the authenticated member.
    Returns the post URN on success; raises on failure."""
    token = os.environ["LINKEDIN_ACCESS_TOKEN"]
    author = os.environ["LINKEDIN_PERSON_URN"]  # urn:li:person:XXXX

    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": version,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    body = {
        "author": author,
        "commentary": _escape(text),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    r = requests.post(API, json=body, headers=headers, timeout=30)

    # 401 → token likely expired; try one refresh then retry once.
    if r.status_code == 401:
        new_token = refresh_access_token()
        if new_token:
            headers["Authorization"] = f"Bearer {new_token}"
            r = requests.post(API, json=body, headers=headers, timeout=30)

    if r.status_code not in (200, 201):
        raise RuntimeError(f"LinkedIn post failed {r.status_code}: {r.text}")
    return r.headers.get("x-restli-id", "posted")
