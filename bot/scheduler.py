"""Periodic background tasks: Popular digest, For You digest, membership reverification,
and data-retention purging."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from sqlalchemy import delete, select

from bot.foryou import run_foryou_digest
from bot.popular import run_popular_digest
from bot.subscriptions import is_subscriber
from config import settings
from db.models import ChannelPost, DigestRun, ParticipatingChannel, Subscription, User
from db.session import async_session

logger = logging.getLogger(__name__)


async def _periodic(name: str, interval: int, coro_factory) -> None:
    await asyncio.sleep(min(interval, 60))
    while True:
        try:
            logger.info("scheduler: running %s", name)
            await coro_factory()
        except Exception:
            logger.exception("scheduler: %s failed", name)
        await asyncio.sleep(interval)


async def _membership_reverify(bot: Bot) -> None:
    async with async_session() as db:
        rows = (
            await db.execute(
                select(
                    Subscription.id,
                    Subscription.user_id,
                    Subscription.channel_id,
                    User.telegram_id,
                    ParticipatingChannel.chat_id,
                    ParticipatingChannel.title,
                )
                .join(User, User.id == Subscription.user_id)
                .join(ParticipatingChannel, ParticipatingChannel.id == Subscription.channel_id)
            )
        ).all()

    removed = 0
    for sub_id, _user_pk, _channel_pk, telegram_id, channel_chat_id, _title in rows:
        ok = await is_subscriber(bot, channel_chat_id, telegram_id)
        if ok:
            continue
        async with async_session() as db:
            await db.execute(delete(Subscription).where(Subscription.id == sub_id))
            await db.commit()
        removed += 1
        try:
            await bot.send_message(
                telegram_id,
                f"I removed <b>{_title}</b> from your feed because you're no longer a member of it.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    if removed:
        logger.info("membership reverify removed %s stale subscriptions", removed)


async def _purge_expired_data() -> None:
    """Delete source content and bookkeeping we no longer need to operate the feed.

    `channel_posts` rows (and their `post_reactions`, via ON DELETE CASCADE) are kept
    only long enough to power the Popular / For You windows; older rows are removed.
    This keeps storage to what is essential for operation, per Bot Developer Terms
    4.2 (delete when retention is unnecessary) and 4.3 (no aggregation beyond what the
    service needs).
    """
    now = datetime.now(timezone.utc)

    if settings.post_retention_hours > 0:
        post_cutoff = now - timedelta(hours=settings.post_retention_hours)
        async with async_session() as db:
            result = await db.execute(
                delete(ChannelPost).where(ChannelPost.posted_at < post_cutoff)
            )
            await db.commit()
        if result.rowcount:
            logger.info("retention: purged %s expired channel_posts", result.rowcount)

    if settings.digest_run_retention_days > 0:
        run_cutoff = now - timedelta(days=settings.digest_run_retention_days)
        async with async_session() as db:
            result = await db.execute(
                delete(DigestRun).where(DigestRun.created_at < run_cutoff)
            )
            await db.commit()
        if result.rowcount:
            logger.info("retention: purged %s expired digest_runs", result.rowcount)


def start_scheduler(bot: Bot) -> list[asyncio.Task]:
    bot_username = settings.telegram_bot_username.lstrip("@") or None

    tasks = [
        asyncio.create_task(
            _periodic("popular", settings.popular_interval_seconds, lambda: run_popular_digest(bot))
        ),
        asyncio.create_task(
            _periodic(
                "foryou",
                settings.foryou_interval_seconds,
                lambda: run_foryou_digest(bot, bot_username),
            )
        ),
        asyncio.create_task(
            _periodic(
                "membership_reverify",
                settings.membership_recheck_interval_seconds,
                lambda: _membership_reverify(bot),
            )
        ),
        asyncio.create_task(
            _periodic(
                "retention_purge",
                settings.retention_interval_seconds,
                _purge_expired_data,
            )
        ),
    ]
    return tasks
