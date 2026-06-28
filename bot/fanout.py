"""Newest-topic fanout: receive channel posts, deliver to each subscribed user's feed.

Pipeline:
  channel_post handler -> enqueue_post()
    -> (if media_group_id) buffer for album_buffer_seconds, then enqueue as a batch
    -> push fanout jobs onto Redis list `fanout`
  fanout workers (started by start_fanout_workers) pop jobs and call
    bot.forward_messages (album) or bot.forward_message (single).

Content protection: if the source channel has content protection enabled
(`protect_content`), forwarding is rejected by Telegram. We deliberately do NOT
fall back to copy_message in that case. A channel that turns on content protection
has signalled that its posts must not be re-shared outside the channel; copying
them into a reader's feed would override that intent and is hard to square with the
Telegram Bot Developer Terms (5.2 - privileges used only for their original purpose)
and the Content Licensing Terms (the content license is non-transferable and
non-sublicensable). Protected posts are therefore skipped, not copied.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from redis.asyncio import Redis
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy import select

from config import settings
from db.models import SetupState, Subscription, User
from db.session import async_session

logger = logging.getLogger(__name__)

QUEUE_KEY = "fanout"

# Album buffer: messages waiting to be flushed once the buffer window elapses.
_album_buffer: dict[str, list[int]] = defaultdict(list)
_album_meta: dict[str, "AlbumBatch"] = {}
_album_tasks: dict[str, asyncio.Task] = {}

# Per-subscriber rate window (sliding 60s). Keyed by user PK.
_rate_windows: dict[int, list[float]] = defaultdict(list)
_pending_skip_notice: dict[int, int] = defaultdict(int)


@dataclass
class AlbumBatch:
    channel_pk: int
    source_chat_id: int
    source_title: str
    media_group_id: str
    message_ids: list[int] = field(default_factory=list)


_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def enqueue_post(
    *,
    channel_pk: int,
    source_chat_id: int,
    source_title: str,
    message_id: int,
    media_group_id: Optional[str],
) -> None:
    if media_group_id:
        batch = _album_meta.get(media_group_id)
        if not batch:
            batch = AlbumBatch(
                channel_pk=channel_pk,
                source_chat_id=source_chat_id,
                source_title=source_title,
                media_group_id=media_group_id,
            )
            _album_meta[media_group_id] = batch
        batch.message_ids.append(message_id)

        existing = _album_tasks.get(media_group_id)
        if existing and not existing.done():
            return

        async def flush(gid: str = media_group_id) -> None:
            await asyncio.sleep(settings.album_buffer_seconds)
            b = _album_meta.pop(gid, None)
            _album_tasks.pop(gid, None)
            if b and b.message_ids:
                await _enqueue_for_subscribers(
                    channel_pk=b.channel_pk,
                    source_chat_id=b.source_chat_id,
                    source_title=b.source_title,
                    message_ids=sorted(b.message_ids),
                )

        _album_tasks[media_group_id] = asyncio.create_task(flush())
        return

    await _enqueue_for_subscribers(
        channel_pk=channel_pk,
        source_chat_id=source_chat_id,
        source_title=source_title,
        message_ids=[message_id],
    )


async def _enqueue_for_subscribers(
    *,
    channel_pk: int,
    source_chat_id: int,
    source_title: str,
    message_ids: list[int],
) -> None:
    async with async_session() as db:
        rows = (
            await db.execute(
                select(User.id, User.feed_supergroup_id, User.topic_newest_id, User.setup_state)
                .join(Subscription, Subscription.user_id == User.id)
                .where(
                    Subscription.channel_id == channel_pk,
                    Subscription.paused == False,  # noqa: E712
                )
            )
        ).all()

    if not rows:
        return

    redis = get_redis()
    pipe = redis.pipeline()
    for user_pk, feed_id, topic_id, state in rows:
        if state != SetupState.ACTIVE.value:
            continue
        if not feed_id or not topic_id:
            continue
        job = {
            "user_pk": user_pk,
            "feed_chat_id": feed_id,
            "topic_id": topic_id,
            "source_chat_id": source_chat_id,
            "source_title": source_title,
            "message_ids": message_ids,
        }
        pipe.lpush(QUEUE_KEY, json.dumps(job))
    await pipe.execute()


def _check_rate(user_pk: int) -> bool:
    now = time.monotonic()
    window = _rate_windows[user_pk]
    cutoff = now - 60
    while window and window[0] < cutoff:
        window.pop(0)
    if len(window) >= settings.posts_per_minute_cap:
        return False
    window.append(now)
    return True


async def _process_job(bot: Bot, job: dict) -> None:
    user_pk = int(job["user_pk"])
    feed_chat_id = int(job["feed_chat_id"])
    topic_id = int(job["topic_id"])
    source_chat_id = int(job["source_chat_id"])
    source_title = str(job.get("source_title") or "Channel")
    message_ids = [int(m) for m in job["message_ids"]]

    if not _check_rate(user_pk):
        _pending_skip_notice[user_pk] += len(message_ids)
        return

    # Single message
    if len(message_ids) == 1:
        await _deliver_single(bot, feed_chat_id, topic_id, source_chat_id, message_ids[0], source_title)
        await _flush_skip_notice(bot, user_pk, feed_chat_id, topic_id)
        return

    # Album
    await _deliver_album(bot, feed_chat_id, topic_id, source_chat_id, message_ids, source_title)
    await _flush_skip_notice(bot, user_pk, feed_chat_id, topic_id)


def is_forward_restricted(exc: TelegramBadRequest) -> bool:
    """True when Telegram rejected a forward because the source protects its content."""
    msg = (exc.message or "").lower()
    return "forward" in msg and ("restricted" in msg or "protect" in msg or "can't" in msg or "not allowed" in msg)


async def _deliver_single(
    bot: Bot, feed_chat_id: int, topic_id: int, source_chat_id: int, message_id: int, source_title: str
) -> None:
    try:
        await bot.forward_message(
            chat_id=feed_chat_id,
            from_chat_id=source_chat_id,
            message_id=message_id,
            message_thread_id=topic_id,
        )
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after + 1)
        await _deliver_single(bot, feed_chat_id, topic_id, source_chat_id, message_id, source_title)
    except TelegramBadRequest as exc:
        if is_forward_restricted(exc):
            # Source has content protection on: skip rather than copy out. See module docstring.
            logger.info(
                "skipping protected post feed=%s src=%s msg=%s (content protection enabled)",
                feed_chat_id, source_chat_id, message_id,
            )
        else:
            logger.warning("forward_message failed feed=%s src=%s msg=%s: %s",
                           feed_chat_id, source_chat_id, message_id, exc)


async def _deliver_album(
    bot: Bot,
    feed_chat_id: int,
    topic_id: int,
    source_chat_id: int,
    message_ids: list[int],
    source_title: str,
) -> None:
    try:
        await bot.forward_messages(
            chat_id=feed_chat_id,
            from_chat_id=source_chat_id,
            message_ids=message_ids,
            message_thread_id=topic_id,
        )
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after + 1)
        await _deliver_album(bot, feed_chat_id, topic_id, source_chat_id, message_ids, source_title)
    except TelegramBadRequest as exc:
        if is_forward_restricted(exc):
            # Source has content protection on: skip the whole album. See module docstring.
            logger.info(
                "skipping protected album feed=%s src=%s msgs=%s (content protection enabled)",
                feed_chat_id, source_chat_id, message_ids,
            )
        else:
            logger.warning("forward_messages failed feed=%s src=%s msgs=%s: %s",
                           feed_chat_id, source_chat_id, message_ids, exc)


async def _flush_skip_notice(bot: Bot, user_pk: int, feed_chat_id: int, topic_id: int) -> None:
    pending = _pending_skip_notice.get(user_pk, 0)
    if pending <= 0:
        return
    _pending_skip_notice[user_pk] = 0
    try:
        await bot.send_message(
            chat_id=feed_chat_id,
            message_thread_id=topic_id,
            text=f"... {pending} more post(s) were rate-limited this minute.",
        )
    except TelegramBadRequest:
        pass


async def _worker_loop(bot: Bot, worker_id: int) -> None:
    redis = get_redis()
    logger.info("fanout worker %s started", worker_id)
    while True:
        try:
            result = await redis.brpop(QUEUE_KEY, timeout=5)
        except RedisTimeoutError:
            continue
        except Exception as exc:
            logger.warning("fanout worker %s redis error: %s", worker_id, exc)
            await asyncio.sleep(1)
            continue
        if not result:
            continue
        _, raw = result
        try:
            job = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("fanout worker %s bad job: %s", worker_id, raw[:200])
            continue
        try:
            await _process_job(bot, job)
        except Exception:
            logger.exception("fanout worker %s job failed", worker_id)


async def start_fanout_workers(bot: Bot) -> list[asyncio.Task]:
    tasks = [
        asyncio.create_task(_worker_loop(bot, i)) for i in range(settings.fanout_workers)
    ]
    return tasks
