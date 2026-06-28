"""Poll X for new tweets and mirror them to a Telegram channel (GitHub Actions cron)."""

import html
import json
import os
import pathlib
import sys
from typing import Any

import requests

TWITTER_API_BASE = "https://api.twitter.com/2"
STATE_DIR = pathlib.Path("state")
STATE_FILE = STATE_DIR / "last_seen.json"


def _env(name: str, *, required: bool = True) -> str:
    val = os.getenv(name)
    if required and not val:
        print(f"Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return val or ""


def get_user_id(username: str, bearer: str) -> str:
    url = f"{TWITTER_API_BASE}/users/by/username/{username}"
    headers = {"Authorization": f"Bearer {bearer}"}
    resp = requests.get(
        url,
        headers=headers,
        params={"user.fields": "id"},
        timeout=20,
    )
    if resp.status_code != 200:
        print(
            f"Error fetching user id for {username}: {resp.status_code} {resp.text}",
            file=sys.stderr,
        )
        sys.exit(1)
    return resp.json()["data"]["id"]


def fetch_original_tweets(
    user_id: str, bearer: str, since_id: str | None
) -> list[dict[str, Any]]:
    url = f"{TWITTER_API_BASE}/users/{user_id}/tweets"
    headers = {"Authorization": f"Bearer {bearer}"}
    params: dict[str, str | int] = {
        "max_results": 20,
        "exclude": "replies,retweets",
        "tweet.fields": "created_at,referenced_tweets",
    }
    if since_id:
        params["since_id"] = since_id

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        print(f"Error fetching tweets: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

    tweets = resp.json().get("data", [])
    originals: list[dict[str, Any]] = []
    for tweet in tweets:
        refs = tweet.get("referenced_tweets", [])
        if any(r.get("type") == "quoted" for r in refs):
            continue
        originals.append(tweet)

    originals.sort(key=lambda t: t["id"])
    return originals


def load_state() -> dict[str, str]:
    if not STATE_FILE.exists():
        return {}
    try:
        with STATE_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, str]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f)
        f.write("\n")


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    resp = requests.post(url, json=payload, timeout=20)
    if resp.status_code != 200:
        print(f"Telegram send error: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)


def format_message(username: str, tweet: dict[str, Any]) -> str:
    tweet_id = tweet["id"]
    body = html.escape(tweet.get("text", ""))
    link = f"https://x.com/{username}/status/{tweet_id}"
    return f"New post from @{html.escape(username)}:\n\n{body}\n\n{link}"


def seed_state(user_id: str, bearer: str) -> None:
    tweets = fetch_original_tweets(user_id, bearer, since_id=None)
    if tweets:
        save_state({"last_seen_id": max(t["id"] for t in tweets)})
        print("Seeded last_seen_id from latest tweet (no messages sent).")
    else:
        print("No tweets found to seed; will retry on next run.")


def main() -> None:
    bearer = _env("TWITTER_BEARER_TOKEN")
    bot_token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    username = _env("TWITTER_USERNAME").lstrip("@")

    state = load_state()
    last_seen_id = state.get("last_seen_id")
    user_id = get_user_id(username, bearer)

    if last_seen_id is None:
        seed_state(user_id, bearer)
        return

    tweets = fetch_original_tweets(user_id, bearer, last_seen_id)
    if not tweets:
        print("No new tweets.")
        return

    for tweet in tweets:
        send_telegram_message(
            bot_token, chat_id, format_message(username, tweet)
        )
        save_state({"last_seen_id": tweet["id"]})
        print(f"Mirrored tweet {tweet['id']} to Telegram.")


if __name__ == "__main__":
    main()
