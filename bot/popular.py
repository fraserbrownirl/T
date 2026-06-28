"""Popular topic: rank recent posts by reaction count, post top K per subscriber."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from sqlalchemy import func, select

from bot import copy as copy_strings
from bot.fanout import is_forward_restricted
from config import settings
from db.models import (
    ChannelPost,
    DigestRun,
    ParticipatingChannel,
    PostReaction,
    SetupState,
    Subscription,
    User,
)
from db.session import async_session

logger = logging.getLogger(__name__)


def _score(reactions: int, channel_median: float, posted_at: datetime, now: datetime) -> float:
    age_hours = max(0.0, (now - posted_at).total_seconds() / 3600.0)
    recency = math.exp(-age_hours / 12.0)
    norm = max(1.0, channel_median)
    return math.log1p(reactions) / math.log1p(norm) * recency


async def run_popular_digest(bot: Bot) -> None:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=settings.popular_window_hours)

    async with async_session() as db:
        users = (
            await db.execute(
                select(User).where(
                    User.setup_state == SetupState.ACTIVE.value,
                    User.feed_supergroup_id.is_not(None),
                    User.topic_popular_id.is_not(None),
                )
            )
        ).scalars().all()

        channel_medians_rows = (
            await db.execute(
                select(
                    ChannelPost.channel_id,
                    func.percentile_cont(0.5).within_group(PostReaction.total_count).label("median"),
                )
                .join(PostReaction, PostReaction.post_id == ChannelPost.id, isouter=True)
                .where(ChannelPost.posted_at >= window_start)
                .group_by(ChannelPost.channel_id)
            )
        ).all()
        channel_median = {cid: float(m or 0) for cid, m in channel_medians_rows}

    for user in users:
        await _run_one_user(bot, user, window_start, now, channel_median)


async def _run_one_user(
    bot: Bot,
    user: User,
    window_start: datetime,
    now: datetime,
    channel_median: dict[int, float],
) -> None:
    async with async_session() as db:
        rows = (
            await db.execute(
                select(
                    ChannelPost.id,
                    ChannelPost.channel_id,
                    ChannelPost.message_id,
                    ChannelPost.posted_at,
                    PostReaction.total_count,
                    ParticipatingChannel.chat_id,
                    ParticipatingChannel.title,
                )
                .join(Subscription, Subscription.channel_id == ChannelPost.channel_id)
                .join(ParticipatingChannel, ParticipatingChannel.id == ChannelPost.channel_id)
                .join(PostReaction, PostReaction.post_id == ChannelPost.id, isouter=True)
                .where(
                    Subscription.user_id == user.id,
                    Subscription.paused == False,  # noqa: E712
                    ChannelPost.posted_at >= window_start,
                    ChannelPost.deleted == False,  # noqa: E712
                )
            )
        ).all()

        already_posted = set(
            (
                await db.execute(
                    select(DigestRun.window_end).where(
                        DigestRun.user_id == user.id,
                        DigestRun.topic == "popular",
                        DigestRun.created_at >= now - timedelta(days=2),
                    )
                )
            ).scalars().all()
        )

    if not rows:
        return

    scored = []
    for post_id, channel_id, msg_id, posted_at, reactions, src_chat_id, title in rows:
        r = int(reactions or 0)
        if r <= 0:
            continue
        scored.append(
            (
                _score(r, channel_median.get(channel_id, 0.0), posted_at, now),
                post_id,
                channel_id,
                msg_id,
                src_chat_id,
                title,
                r,
            )
        )

    if not scored:
        return

    scored.sort(reverse=True)
    top = scored[: settings.popular_top_k]

    posted = 0
    for _, _post_id, _channel_id, msg_id, src_chat_id, title, r in top:
        try:
            # Forward (not copy) so we respect content protection: a protected source
            # rejects the forward and we skip it, instead of copying its content out.
            await bot.forward_message(
                chat_id=user.feed_supergroup_id,
                from_chat_id=src_chat_id,
                message_id=msg_id,
                message_thread_id=user.topic_popular_id,
            )
            await bot.send_message(
                chat_id=user.feed_supergroup_id,
                message_thread_id=user.topic_popular_id,
                text=copy_strings.POPULAR_HEADER.format(title=title, reactions=r),
                parse_mode="HTML",
            )
            posted += 1
        except TelegramRetryAfter as exc:
            import asyncio
            await asyncio.sleep(exc.retry_after + 1)
        except TelegramBadRequest as exc:
            if is_forward_restricted(exc):
                logger.info(
                    "popular: skipping protected post user=%s msg=%s (content protection enabled)",
                    user.id, msg_id,
                )
            else:
                logger.warning("popular post failed user=%s msg=%s: %s", user.id, msg_id, exc)

    if posted:
        async with async_session() as db:
            db.add(
                DigestRun(
                    user_id=user.id,
                    topic="popular",
                    window_start=window_start,
                    window_end=now,
                    posted_count=posted,
                )
            )
            await db.commit()
