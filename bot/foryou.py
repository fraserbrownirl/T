"""For You topic: recommend participating channels the user isn't yet subscribed to.

Signals (v1):
  - Co-subscription: count of other readers who share >=1 subscription with this user
    and are also subscribed to candidate channel C.
  - Trending: post count + reaction sum over last 24h, used as a tiebreaker / cold start.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select

from bot import copy as copy_strings
from config import settings
from db.models import (
    ChannelPost,
    ChannelStatus,
    DigestRun,
    ParticipatingChannel,
    PostReaction,
    SetupState,
    Subscription,
    User,
)
from db.session import async_session

logger = logging.getLogger(__name__)


async def run_foryou_digest(bot: Bot, bot_username: str | None) -> None:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=24)

    async with async_session() as db:
        users = (
            await db.execute(
                select(User).where(
                    User.setup_state == SetupState.ACTIVE.value,
                    User.feed_supergroup_id.is_not(None),
                    User.topic_foryou_id.is_not(None),
                )
            )
        ).scalars().all()

        trending_rows = (
            await db.execute(
                select(
                    ParticipatingChannel.id,
                    func.count(ChannelPost.id).label("posts"),
                    func.coalesce(func.sum(PostReaction.total_count), 0).label("reactions"),
                )
                .join(ChannelPost, ChannelPost.channel_id == ParticipatingChannel.id, isouter=True)
                .join(PostReaction, PostReaction.post_id == ChannelPost.id, isouter=True)
                .where(
                    ParticipatingChannel.status == ChannelStatus.ACTIVE.value,
                    (ChannelPost.posted_at.is_(None)) | (ChannelPost.posted_at >= window_start),
                )
                .group_by(ParticipatingChannel.id)
            )
        ).all()
        trending = {cid: (int(p or 0), int(r or 0)) for cid, p, r in trending_rows}

        all_subs = (
            await db.execute(select(Subscription.user_id, Subscription.channel_id))
        ).all()

    by_user: dict[int, set[int]] = {}
    by_channel: dict[int, set[int]] = {}
    for uid, cid in all_subs:
        by_user.setdefault(uid, set()).add(cid)
        by_channel.setdefault(cid, set()).add(uid)

    for user in users:
        await _run_one_user(bot, bot_username, user, by_user, by_channel, trending, now, window_start)


async def _run_one_user(
    bot: Bot,
    bot_username: str | None,
    user: User,
    by_user: dict[int, set[int]],
    by_channel: dict[int, set[int]],
    trending: dict[int, tuple[int, int]],
    now: datetime,
    window_start: datetime,
) -> None:
    own_channels = by_user.get(user.id, set())

    candidate_scores: dict[int, float] = {}
    for sub_cid in own_channels:
        co_readers = by_channel.get(sub_cid, set()) - {user.id}
        for reader in co_readers:
            for other_cid in by_user.get(reader, set()):
                if other_cid in own_channels:
                    continue
                candidate_scores[other_cid] = candidate_scores.get(other_cid, 0.0) + 1.0

    for cid, (posts, reacts) in trending.items():
        if cid in own_channels:
            continue
        candidate_scores[cid] = candidate_scores.get(cid, 0.0) + 0.1 * posts + 0.01 * reacts

    if not candidate_scores:
        return

    ranked = sorted(candidate_scores.items(), key=lambda kv: kv[1], reverse=True)
    top_ids = [cid for cid, _ in ranked[: settings.foryou_top_k]]
    if not top_ids:
        return

    async with async_session() as db:
        channels = (
            await db.execute(
                select(ParticipatingChannel).where(
                    ParticipatingChannel.id.in_(top_ids),
                    ParticipatingChannel.status == ChannelStatus.ACTIVE.value,
                )
            )
        ).scalars().all()
    channels_by_id = {c.id: c for c in channels}

    posted = 0
    for cid in top_ids:
        channel = channels_by_id.get(cid)
        if not channel:
            continue
        subscriber_count = len(by_channel.get(cid, set()))
        text = copy_strings.FORYOU_CARD.format(
            title=channel.title,
            description=f"@{channel.username}" if channel.username else "",
            subscriber_count=subscriber_count,
        )
        markup = None
        if bot_username:
            markup = InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Add to feed",
                        url=f"https://t.me/{bot_username}?start=add_{channel.id}",
                    )
                ]]
            )
        try:
            await bot.send_message(
                chat_id=user.feed_supergroup_id,
                message_thread_id=user.topic_foryou_id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup,
            )
            posted += 1
        except TelegramBadRequest as exc:
            logger.warning("foryou post failed user=%s channel=%s: %s", user.id, cid, exc)

    if posted:
        async with async_session() as db:
            db.add(
                DigestRun(
                    user_id=user.id,
                    topic="foryou",
                    window_start=window_start,
                    window_end=now,
                    posted_count=posted,
                )
            )
            await db.commit()
