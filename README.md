# Telegram Personal Feed

A subscriber-only syndication network for Telegram channels, built on the Bot API.

One bot. Two roles:

1. **Channel owners** add the bot as an administrator (no permissions ticked) in their channel. The channel becomes part of the directory.
2. **Readers** create a private forum supergroup and add the same bot as admin (Manage Topics). The bot auto-creates three topics - `Newest`, `Popular`, and `For You` - and delivers content into them.

A reader can mirror a channel only if (a) the channel owner has opted in and (b) the reader is verified as a member of that channel. The bot never sends content to anyone who wasn't already entitled to read it.

No MTProto, no user sessions, no api_id. Everything runs through the Bot API.

## Running locally

```bash
cp .env.example .env
# set TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_USERNAME (from @BotFather)
docker compose up --build
```

That brings up `postgres`, `redis`, `migrate`, and `bot`. The bot starts polling immediately.

## Reader flow

1. Open the bot in Telegram, send `/start`.
2. In Telegram, create a new Group, enable Topics in its settings, then add the bot as administrator with Manage Topics permission.
3. The bot detects the promotion, creates the three topics, and DMs you confirmation.
4. To add a channel: open it in Telegram, forward any post to the bot. If the channel is participating and you're a member, it's added.
5. Run `/list` to see and manage your subscriptions.

## Channel owner flow

1. Open your channel settings -> Administrators -> Add Administrator -> search for the bot.
2. Untick everything (or leave defaults from `setMyDefaultAdministratorRights`). Save.
3. The bot DMs you a thank-you. Subscribers of your channel can now mirror it into their feeds.
4. To opt out, remove the bot as administrator.

## Repository layout

See [AGENTS.md](AGENTS.md) for the full map, design rules, and pitfalls.

## What's not built

- Web/Mini App UI (Telegram-native flow only for now)
- Channel-owner analytics dashboard
- Topical-similarity recommendations (For You uses co-subscription + trending)

## X → Telegram autoshare (agent skill)

This repo includes an **agent skill** at [`skills/x-to-telegram-mirror/`](skills/x-to-telegram-mirror/README.md) for a separate use case: mirror one X account into a Telegram channel via GitHub Actions (BYOK — user's own X Developer API key and BotFather bot).

**You do not configure this on the open-source repo itself.** Clone the repo, open it in Cursor, and ask the agent to set up X→Telegram mirroring — it scaffolds a **new repo for you** from `skills/x-to-telegram-mirror/templates/` and walks you through secrets on **your** GitHub repository.

(Cursor also loads the same skill from `.cursor/skills/x-to-telegram-mirror/`.)
