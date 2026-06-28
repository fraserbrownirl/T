---
name: x-to-telegram-mirror
description: >-
  Sets up automatic X (Twitter) to Telegram channel mirroring via GitHub Actions
  cron and official X Developer API v2. Guides X Developer API key, BotFather bot
  token, channel ID, and GitHub Actions secrets. Use when the user wants to
  autoshare X posts to Telegram, mirror tweets to a channel, or set up
  x-to-telegram with BYOK credentials.
---

# X → Telegram Mirror (GitHub Actions)

Guide the user through BYOK setup: their X Developer API key, their BotFather bot, and a GitHub Actions cron that mirrors **one X account → one Telegram channel**. No Docker, no VPS, no shared API keys.

**Outcome:** new original tweets appear in their Telegram channel automatically (~15 min delay). Laptop can be off.

Read [reference.md](reference.md) for costs, troubleshooting, and limits.

## How this open-source repo works

**This repository ships an agent skill + templates — not a running mirror.**

- Templates live at `skills/x-to-telegram-mirror/templates/` in this repo (also mirrored under `.cursor/skills/x-to-telegram-mirror/` for Cursor).
- **Do not** add GitHub Secrets to the upstream/open-source repo.
- **Do not** commit `monitor.py` or workflows into this repo for production use.
- When a user wants X → Telegram mirroring, the agent scaffolds files into **the user's own new GitHub repository** (or a directory they choose), and they add secrets **only on that repo**.

If the user is cloning this repo to get the skill, point them to invoke this skill in Cursor/Claude — the agent will create their personal mirror repo from templates.

## Before you start

Confirm with the user:

1. Which **@handle** to mirror (`TWITTER_USERNAME`, no `@`).
2. They will create a **new GitHub repo** (recommended name e.g. `my-x-telegram-mirror`) under their account — separate from any open-source upstream they cloned the skill from.
3. They accept **~$0.50–3/month** X API credits (pay-per-use) for polling a public account.

Tell them credentials go only into **their repo's** GitHub Actions secrets, never into the open-source skill repo and never committed to git.

## Agent workflow

Execute these phases in order. Pause for user input when secrets or channel IDs are needed.

### Phase 1 — Create the user's mirror repository

1. Ask where to scaffold (default: **new empty GitHub repo** the user creates, or a local folder they will push).
2. Copy templates from **this skill's** `templates/` into **that target repo** (not into an open-source upstream unless the user explicitly owns it and wants it there):

| Template | Destination in user's repo |
|----------|----------------------------|
| `templates/monitor.py` | `monitor.py` |
| `templates/requirements.txt` | `requirements.txt` |
| `templates/gitignore` | `.gitignore` |
| `templates/mirror.yml` | `.github/workflows/mirror.yml` |
| `templates/state/.gitkeep` | `state/.gitkeep` |

3. Add a short `README.md` in the user's repo (setup summary + link to add four GitHub Secrets).
4. Commit and push to **the user's repo** before Phase 4 — the workflow must exist on their default branch.

### Phase 2 — X Developer API (user BYOK)

Walk the user through [developer.x.com](https://developer.x.com):

1. Sign in → **Developer Console** → create a **Project** and **App** (if they do not have one).
2. Enable **pay-per-use** credits and set a **spending limit**.
3. Under the app **Keys and tokens**, generate or copy the **Bearer Token** (App-only).
4. Ensure the app can call v2 endpoints: `GET /2/users/by/username/:username` and `GET /2/users/:id/tweets`.

They will add these as secrets on **their mirror repo** in Phase 4:

- `TWITTER_BEARER_TOKEN` — Bearer token
- `TWITTER_USERNAME` — handle to mirror, **without** `@`

Do not ask the user to paste the Bearer token into chat if they prefer not to; they add it directly in GitHub UI on **their repo**.

### Phase 3 — Telegram BotFather (user BYOK)

1. Open [@BotFather](https://t.me/BotFather) in Telegram.
2. Send `/newbot` → follow prompts → copy the **bot token** (`TELEGRAM_BOT_TOKEN`).
3. Create a **Telegram channel** (or use an existing one).
4. **Channel settings → Administrators → Add administrator** → select the bot.
5. Post any test message in the channel.
6. Find the channel ID via `https://api.telegram.org/bot<TOKEN>/getUpdates` → `"chat":{"id":-100…}` → `TELEGRAM_CHAT_ID`.

### Phase 4 — GitHub Actions secrets (user's repo only)

In **the user's mirror repo** (not the open-source skill upstream):

**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Source |
|--------|--------|
| `TWITTER_BEARER_TOKEN` | X Developer Console |
| `TWITTER_USERNAME` | @handle to mirror |
| `TELEGRAM_BOT_TOKEN` | BotFather |
| `TELEGRAM_CHAT_ID` | getUpdates |

Ensure **Actions** are enabled on **their repo**.

### Phase 5 — Test run

On **the user's mirror repo**:

1. **Actions** → **X to Telegram Mirror** → **Run workflow** (`workflow_dispatch`).
2. Expected **first run:** log says `Seeded last_seen_id from latest tweet (no messages sent).`; `state/last_seen.json` is committed.
3. After they post on X: within ~15 min, Telegram receives text + link.

If the workflow fails, use [reference.md](reference.md) troubleshooting table.

### Phase 6 — Handoff

Tell the user:

- Cron runs **every 15 minutes** on GitHub's servers (their repo's Actions).
- Only **new original tweets** after setup are mirrored (not replies, RTs, or quotes).
- Keep **X API credits** topped up in their Developer Console.
- To change account: update `TWITTER_USERNAME` secret, delete `state/last_seen.json`, re-run workflow to re-seed.

## Security rules

- Never add production secrets to the open-source skill/template repository.
- Never commit `.env` or Bearer tokens to any tracked file.
- Never log secrets in workflow output.
- Templates read credentials from GitHub Secrets at runtime on **the user's repo** only.

## Customization

- **Cron interval:** edit `cron: "*/15 * * * *"` in `.github/workflows/mirror.yml`.
- **Include replies/RTs:** adjust `exclude` in `monitor.py` (not recommended for channel mirrors).

## Template source

`monitor.py` is based on [cosineai-x-telegram-notifier](https://github.com/EleftheriaBatsou/cosineai-x-telegram-notifier) with per-tweet state persistence (advance `last_seen_id` only after successful Telegram send).
