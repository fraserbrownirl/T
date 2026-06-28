# X → Telegram Mirror — Reference

## What runs automatically

- GitHub Actions cron fires every **15 minutes** (independent of user's laptop).
- Each run calls `monitor.py` once: poll X API → send new tweets to Telegram → commit `state/last_seen.json`.
- **Latency:** up to one cron interval (~15 min) after a post appears on X.
- **First run:** records the latest tweet ID without sending history.
- **Mirrored:** original tweets only (no replies, retweets, or quote-tweets).
- **MVP output:** text + `x.com/status/…` link (Telegram may show a link preview).

## GitHub Secrets (required)

| Secret | Description |
|--------|-------------|
| `TWITTER_BEARER_TOKEN` | X Developer app Bearer token (App-only auth) |
| `TWITTER_USERNAME` | Handle to mirror, without `@` |
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Numeric channel/chat ID (channels often `-100…`) |

Never commit secrets to the repository. Use GitHub Actions secrets only.

## X Developer API cost (pay-per-use, 2026)

New developers use pay-per-use credits at [developer.x.com](https://developer.x.com):

| Operation | Approximate cost |
|-----------|------------------|
| User lookup (`/users/by/username`) | ~$0.01 once per run (cache `user_id` in a future optimization) |
| Read tweets (`/users/:id/tweets`) | ~$0.005 per tweet returned |
| Owned reads (OAuth user context, own account) | ~$0.001 per resource |

**Rough monthly cost** for one account polled every 15 min: **~$0.50–3** with Bearer token on a public account; lower with OAuth on own account.

Set a **spending limit** in the X Developer Console.

## Telegram setup notes

1. Bot must be added to the channel as **Administrator** (not merely a member).
2. To find `TELEGRAM_CHAT_ID`:
   - Post any message in the channel.
   - Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser.
   - Find `"chat":{"id":-100…}` in the JSON.
3. If `sendMessage` returns 403, the bot lacks permission or is not an admin.

## GitHub Actions notes

- **`workflow_dispatch`:** manual "Run workflow" button for testing after secrets are set.
- **State commit:** workflow needs `contents: write` to push `state/last_seen.json`.
- **`[skip ci]`** in commit message avoids infinite workflow loops on state-only commits.
- **Inactive repos:** GitHub may disable scheduled workflows on free private repos after ~60 days without activity; push a commit or manually re-enable.
- **Schedule delay:** cron jobs can start a few minutes late during high GitHub load.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Workflow fails on `get_user_id` | Invalid Bearer token or wrong username | Re-copy token; check `TWITTER_USERNAME` has no `@` |
| 402 / 403 from X API | Credits exhausted or app lacks access | Top up credits; verify v2 tweet read access |
| Telegram 400 Bad Request | Wrong `TELEGRAM_CHAT_ID` | Re-fetch from `getUpdates`; use channel ID not username |
| Telegram 403 | Bot not channel admin | Add bot as administrator in channel settings |
| No tweets mirrored but workflow succeeds | First-run seed only | Wait for a **new** post after first successful run |
| State not updating | Telegram send failed | Check logs; state advances only after successful send |
| Duplicate tweets | State file not committed | Ensure workflow has `contents: write` and push succeeded |

## Optional: mirror your own account (OAuth)

The default template uses **Bearer token** (app-only), suitable for any public @handle.

To mirror **your own** account with cheaper owned-read pricing, obtain an OAuth 2.0 user access token from the X Developer Portal and extend `monitor.py` to send `Authorization: Bearer <user_token>` instead of the app Bearer. Document token refresh if you add this path.

## Files in the user's repo

```
monitor.py
requirements.txt
.gitignore
.github/workflows/mirror.yml
state/last_seen.json    # created on first run, updated by Actions
```

Templates live in this skill at `templates/` — copy them into the user's repository during setup.
