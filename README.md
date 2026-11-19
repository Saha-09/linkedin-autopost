# LinkedIn Autopost — human-in-the-loop content engine

Drafts finance/IB/PE LinkedIn posts in **your** voice every other day, sends each
to Telegram, and posts to your profile **only when you tap Approve**. Built on the
same free stack as your market-brief bot: Python + GitHub Actions + Telegram, zero
hosting cost.

Profile this is wired for: `linkedin.com/in/soumyadeep-saha09`

---

## Why this design (read this first)

**Posting is done through LinkedIn's official API, not by driving the browser.**
That matters:

- Posting to your **own personal profile** uses the `w_member_social` scope, which
  is **self-serve** — you add a product to a LinkedIn app, no partner review.
- Browser-automation tools (bots that click linkedin.com for you) are what trigger
  account restrictions — roughly 1 in 4 users of those get flagged. The API is the
  compliant rail: no simulated session, no scraping.
- LinkedIn's API terms do frown on fully *autonomous* posting. The mitigation is
  the human-in-the-loop: **you approve every post.** An AI that drafts + a human who
  approves sits in the lowest-risk category. This is also exactly what you asked for.

So: the bot never posts on its own. It proposes; you decide.

---

## Architecture

```
every other day (GitHub Actions cron)
        │
        ▼
  news.py ────── pulls last-2-days headlines for the lane (Google News RSS, free)
        │
        ▼
  generate.py ── drafts N posts in your voice (voice_system_prompt.md)
        │         anchors each to a real recent story + relevant hashtags
        │         optionally pulls your market brief as extra source material
        │         runs guardrails (length, banned AI phrases, hashtag cap)
        │         outputs post body + a "tag these" suggestion list
        ▼
  queue/<id>.json  +  Telegram message with [✅ Approve] [🗑️ Skip]
        │
        ▼  (you tap a button on your phone)
  poll.yml every 15 min → approve_poller.py
        │
        ▼
  linkedin_client.py → POST /rest/posts  → live on your profile
```

---

## One-time setup (~30 min, mostly the LinkedIn app)

### 1. Create the LinkedIn app  *(only you can do this — it's your identity)*
1. Go to the LinkedIn Developer Portal → **Create app**. Associate it with a Company
   Page (you can make a throwaway one; the page is just tied to the app, not to your
   posts — posts still go to your personal feed).
2. In the app's **Products** tab, add:
   - **Sign In with LinkedIn using OpenID Connect**
   - **Share on LinkedIn**
   Both are self-serve; no review.
3. In **Auth**, add redirect URL: `http://localhost:8000/callback`. Copy your
   **Client ID** and **Client Secret**.

### 2. Mint your tokens
On your own machine:
```bash
pip install -r requirements.txt
export LINKEDIN_CLIENT_ID=xxxx
export LINKEDIN_CLIENT_SECRET=xxxx
python src/get_token.py
```
It opens the consent screen, then prints `LINKEDIN_ACCESS_TOKEN`,
`LINKEDIN_REFRESH_TOKEN`, and `LINKEDIN_PERSON_URN`. Keep them.

### 3. Create a Telegram bot  *(use a SEPARATE bot from your market-brief one)*
Talk to **@BotFather** → `/newbot` → copy the token. Message your new bot once,
then get your chat id (e.g. open `https://api.telegram.org/bot<TOKEN>/getUpdates`
and read `chat.id`). A separate bot matters because this one *consumes* updates
(button taps); your brief bot only sends, so mixing them would clash.

### 4. Pick an LLM (the drafting brain)
Cheapest path is a **free tier**: Google **Gemini** (`gemini-2.0-flash`) or **Groq**.
Get an API key, set `LLM_PROVIDER` + `LLM_API_KEY`. Want the best humanization?
Point it at Claude (`LLM_PROVIDER=anthropic`) — a few cents per month at this volume.

### 5. Add GitHub secrets
Push this folder to a repo (private is fine). In **Settings → Secrets and variables →
Actions**, add every key from `.env.example`:
`LLM_PROVIDER, LLM_API_KEY, LLM_MODEL, MARKET_BRIEF_URL, TELEGRAM_BOT_TOKEN,
TELEGRAM_CHAT_ID, LINKEDIN_ACCESS_TOKEN, LINKEDIN_REFRESH_TOKEN, LINKEDIN_CLIENT_ID,
LINKEDIN_CLIENT_SECRET, LINKEDIN_PERSON_URN`.

### 6. Test it
Actions tab → **Generate LinkedIn drafts** → **Run workflow**. You should get draft(s)
in Telegram within a minute. Tap Approve; within ≤15 min the poll job posts it.

---

## Day to day
- Alternate mornings you get 2 candidate posts in Telegram.
- Approve the one you like, Skip the rest. Approve none on a dull day — the point is
  consistency *and* control, not posting for its own sake.
- Want to tweak before posting? Skip it, copy the text, edit, paste into LinkedIn
  manually. (A full "Edit in Telegram" flow is a nice v2 — see below.)

## Recent news (automatic)
`news.py` fetches the last 2 days of India-finance headlines per lane from Google
News RSS — free, no key. Each post is anchored to a real current story, so nothing
reads as stale or generic. Setting `MARKET_BRIEF_URL` to your `Saha-09/Market-Brief`
output adds a second, richer source on top.

## Tagging & hashtags — what's automated vs manual
- **Hashtags: automated.** 2–4 per post, mixing broad (#investmentbanking) with
  specific ones built from the actual story (#Reliance, the sector, the ticker).
  Tune the evergreen pool in `config.json`.
- **@mentions (tagging people/company pages): manual, by design.** The API can't
  reliably resolve a person's or company's URN, and auto-tagging strangers is the
  #1 way to get flagged as tag-spam. So each draft comes with a short "worth tagging"
  list. Two ways to use it: (a) tap Approve, then @mention them in the **first
  comment**, or (b) for a high-value story, Skip and post manually so you can @-tag
  in the body (slightly more reach). The bot does the writing; you do the tagging.

## Daily or every other day?
**Start every other day (~3–4 posts/week). Don't go daily yet.** Reasons:
- Your base is still small (a handful of post impressions), and LinkedIn's algorithm
  *punishes* frequent posting with weak early engagement — it reads as low-quality.
  Fewer, stronger posts train it that you're a quality creator in finance.
- Alternate-day is sustainable; daily burns out your ability to actually reply to
  comments in the first hour, which matters far more than frequency.
- Move to daily only once you're consistently getting real comments and your
  connection count is climbing — then raise `drafts_per_run` or change the cron to
  `30 3 * * *`. Until then, consistency + engagement beats volume every time.

## Keeping tokens alive
The access token lasts ~60 days. If your app issued a **refresh token**, the client
auto-refreshes on a 401. If it didn't, just re-run `get_token.py` every ~55 days and
update the two secrets. (v2 idea: a monthly workflow that refreshes and updates the
secret via a GitHub PAT.)

---

## The part most people get wrong: posting ≠ reach

Automating the *posting* is 20% of the game. Visibility to IB/PE/equity recruiters
comes from how LinkedIn's feed actually works:

1. **The first 60 minutes decide everything.** The algorithm shows your post to a
   small test audience; strong early engagement expands reach. So post when your
   target audience is online (weekday mornings IST for India finance; Tue–Thu best),
   and spend 15 min replying to every comment right after. The bot posting at a
   consistent morning slot helps here.
2. **Comment more than you post.** Thoughtful comments on posts by MDs, PE
   principals, and finance creators put you in front of their audience without
   needing your own reach. 5 sharp comments/day > 1 more post. (Keep this manual —
   automated commenting is the banned kind.)
3. **The hook is 80% of performance.** LinkedIn truncates after ~2 lines. The voice
   prompt is tuned to open with a number/claim/contradiction, never a definition.
4. **Don't put links in the post body.** External links suppress reach; put them in
   the first comment instead.
5. **Connection strategy beats raw follower count.** Send personalized connection
   requests (with a note) to people who engage with your posts and to 2nd-degree
   finance folks. ~20–25/day max — above that is restriction territory. Keep this
   manual and human.
6. **Consistency compounds.** Every-other-day for 3 months trains the algorithm that
   you're a reliable creator in the finance niche. Don't post daily and burn out.
7. **Pick a lane and own it.** Your edge is the physics/CS + finance combo — reasoning
   through *mechanisms*, not just reporting news. The topic lanes in `config.json`
   keep you varied but on-brand.

The bot gives you (1), (3), (6), (7) on autopilot. (2) and (5) are the manual levers
that actually pull recruiters in — do those yourself, 15 min/day.

---

## Humanization — why these won't read as AI
Full ruleset in `prompts/voice_system_prompt.md`. The short version: banned AI-tell
phrases (hard-filtered in `config.json` too), forced structural variety (6 post
shapes, never the same twice), mandatory specific numbers, a real point of view, one
honest admission of uncertainty per post, tight length, and max 3 hashtags. The
guardrail step rejects and regenerates any draft that trips a banned phrase.

Still — **read every draft before approving.** You're the final humanizer. If a line
sounds off, it is; skip it.

---

## Costs & limits
- GitHub Actions, Telegram, LinkedIn API, Gemini/Groq free tiers = **₹0/month.**
- LinkedIn personal posting: ~100 API calls/day/member — you'll use ~1.
- This posts **text only**. Image/document posts are a v2 (the API supports them via
  an image-upload step).

## v2 ideas
- "✏️ Edit" button that lets you send a revised version back through Telegram before posting.
- Seed drafts directly from your `Saha-09/Market-Brief` output instead of re-fetching.
- Monthly token-refresh workflow.
- Image posts (charts from your brief) via the LinkedIn image-upload endpoint.
- A weekly "what performed" summary pulled from post analytics.

---

## Off-the-shelf alternative
If you'd rather not run code: **Taplio** or **Buffer** schedule LinkedIn posts via the
official API with approval steps built in (paid). This repo does the same thing for
free, in your voice, on infra you already run — but the managed tools exist if you
want zero maintenance.
