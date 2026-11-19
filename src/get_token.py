"""One-time, LOCAL helper to complete LinkedIn OAuth and print your tokens.

Run this on your own machine (not in CI). It opens the LinkedIn consent screen,
catches the redirect on localhost, exchanges the code, and prints the values you
paste into .env / GitHub secrets — including your LINKEDIN_PERSON_URN.

Prereqs in your LinkedIn Developer app:
  - Products added: "Sign In with LinkedIn using OpenID Connect" + "Share on LinkedIn"
  - Authorized redirect URL: http://localhost:8000/callback
Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in your environment first.
"""
import os
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

CLIENT_ID = os.environ["LINKEDIN_CLIENT_ID"]
CLIENT_SECRET = os.environ["LINKEDIN_CLIENT_SECRET"]
REDIRECT = "http://localhost:8000/callback"
SCOPES = "openid profile w_member_social"
AUTH = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO = "https://api.linkedin.com/v2/userinfo"

_code = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(q)
        if "code" in params:
            _code["value"] = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Done. You can close this tab and return to the terminal.")
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, *a):  # silence
        pass


def main():
    url = AUTH + "?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT,
        "scope": SCOPES,
        "state": "xyz",
    })
    print("Opening browser for consent...\nIf it doesn't open, visit:\n", url)
    webbrowser.open(url)

    server = HTTPServer(("localhost", 8000), Handler)
    while "value" not in _code:
        server.handle_request()

    tok = requests.post(TOKEN, data={
        "grant_type": "authorization_code",
        "code": _code["value"],
        "redirect_uri": REDIRECT,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }, timeout=30).json()

    access = tok.get("access_token")
    refresh = tok.get("refresh_token", "")
    if not access:
        print("Token exchange failed:", tok, file=sys.stderr)
        sys.exit(1)

    me = requests.get(USERINFO, headers={"Authorization": f"Bearer {access}"}, timeout=30).json()
    sub = me.get("sub")

    print("\n" + "=" * 60)
    print("Paste these into your .env / GitHub secrets:\n")
    print(f"LINKEDIN_ACCESS_TOKEN={access}")
    print(f"LINKEDIN_REFRESH_TOKEN={refresh}")
    print(f"LINKEDIN_PERSON_URN=urn:li:person:{sub}")
    print("=" * 60)
    print("\nNote: access token lasts ~60 days. If no refresh token appears above,")
    print("re-run this script before it expires to mint a fresh one.")


if __name__ == "__main__":
    main()
