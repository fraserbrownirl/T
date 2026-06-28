# Privacy Policy

_Last updated: 2026-06-26_

This bot ("the Bot") gives you a personal Telegram feed that re-organises posts from
channels **you are already a member of** into topics inside a forum supergroup that
**you** create and control. This policy explains what data the Bot stores, why, and
for how long. It is provided in addition to, and is governed by, the
[Telegram Privacy Policy](https://telegram.org/privacy), the
[Telegram Terms of Service](https://telegram.org/tos), and the
[Telegram Bot Developer Terms](https://telegram.org/tos/bot-developers).

## Who operates the Bot

The Bot is an independent third-party service and is **not** affiliated with or
operated by Telegram. Contact for privacy requests: **<set your contact here>**.

## What we store and why

We store only what is needed to operate the feed. Specifically:

| Data | Why we store it |
|------|-----------------|
| Your Telegram user ID | Identify your account and link it to your feed |
| Your feed supergroup ID and topic IDs | Know where to deliver your posts |
| Your subscriptions (which channels you added) and pause state | Build and manage your feed |
| Participating channels' ID, title, username | Route posts to subscribers |
| References to source posts: channel + message ID, timestamp, a short text preview, media type | Rank Popular posts and detect duplicates during the active window |
| Aggregate reaction **counts** per post | Rank Popular posts |

We do **not** store full message bodies or media files. Posts are delivered to your
feed by **forwarding** them within Telegram, not by archiving their contents on our
servers. We do not store per-user reaction data, your contacts, your phone number, or
your message history with other people.

## What we never do

- We do **not** sell, rent, or share your data with third parties.
- We do **not** use any content or data to train, fine-tune, or build AI/ML models,
  and we do **not** scrape channels or build datasets. This is prohibited by Telegram
  and by us.
- We only ever deliver a channel's posts to you if you are a **verified member** of
  that channel (checked via Telegram's `getChatMember`). The Bot is not a way to read
  channels you have not joined.
- We respect content protection: posts from channels that enable content protection
  (`protect_content`) are **skipped**, never copied out.

## How long we keep it

- **Source post references and reaction counts:** purged automatically once they age
  out of the ranking window (default 72 hours).
- **Digest bookkeeping:** purged automatically (default 30 days).
- **Subscriptions, feed/topic IDs, your user ID:** kept while your feed is active.
  Removed when you delete the data (see below) or when the subscription/feed is gone.
- If you remove the Bot as administrator from a source channel, that channel and its
  stored posts are deactivated and removed.

## Your choices and rights

- `/list` — see and remove individual channel subscriptions.
- `/pause` and `/resume` — stop or restart delivery at any time.
- `/privacy` — view this policy.
- **Delete everything:** remove the Bot from your feed supergroup and send `/start`,
  or contact us at the address above to request full deletion of your data. We will
  delete your data without undue delay, except where retention is required by law.

Depending on your jurisdiction (e.g. the EU/UK under GDPR), you may have rights to
access, rectify, erase, or restrict processing of your personal data. Use the contact
above to exercise them.

## Security

Data is stored on infrastructure controlled by the Bot operator. We take reasonable
measures to protect it, but no system is perfectly secure. If a breach occurs that
affects your data, we will notify affected users as required by applicable law.

## Changes

We may update this policy. Material changes will be reflected here and the
"Last updated" date will change. Continued use of the Bot after an update constitutes
acceptance of the revised policy.
