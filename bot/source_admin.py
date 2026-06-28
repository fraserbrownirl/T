"""Source-side: handle the bot being promoted to (or removed from) admin of a channel,
and ingest channel posts + reactions."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import Bot, Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    ChatMemberUpdated,
    Message,
    MessageReactionCountUpdated,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from bot import copy as copy_strings
from bot.fanout import enqueue_post
from db.models import ChannelPost, ChannelStatus, ParticipatingChannel, PostReaction
from db.session import async_session

logger = logging.getLogger(__name__)
router = Router(name="source_admin")

ADMIN_STATUSES = {"administrator", "creator"}


def _media_type(message: Message) -> str | None:
    if message.photo:
        return "photo"
    if message.video:
        return "video"
    if message.document:
        return "document"
    if message.audio:
        return "audio"
    if message.voice:
        return "voice"
    if message.sticker:
        return "sticker"
    if message.animation:
        return "animation"
    if message.text or message.caption:
        return "text"
    return None


def _text_preview(message: Message) -> str | None:
    text = message.text or message.caption
    return text[:500] if text else None


@router.my_chat_member(F.chat.type == "channel")
async def channel_admin_change(event: ChatMemberUpdated, bot: Bot) -> None:
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    chat = event.chat

    became_admin = old_status not in ADMIN_STATUSES and new_status in ADMIN_STATUSES
    lost_admin = old_status in ADMIN_STATUSES and new_status not in ADMIN_STATUSES

    async with async_session() as db:
        if became_admin:
            stmt = pg_insert(ParticipatingChannel).values(
                chat_id=chat.id,
                username=chat.username,
                title=chat.title or "Untitled",
                owner_user_id=event.from_user.id if event.from_user else None,
                status=ChannelStatus.ACTIVE.value,
            ).on_conflict_do_update(
                index_elements=["chat_id"],
                set_={
                    "username": chat.username,
                    "title": chat.title or "Untitled",
                    "status": ChannelStatus.ACTIVE.value,
                    "revoked_at": None,
                },
            )
            await db.execute(stmt)
            await db.commit()
            logger.info("Channel %s (%s) joined network", chat.id, chat.title)

            if event.from_user:
                try:
                    await bot.send_message(
                        event.from_user.id,
                        copy_strings.OWNER_THANKS.format(title=chat.title or "your channel"),
                        parse_mode="HTML",
                    )
                except TelegramBadRequest:
                    pass

        elif lost_admin:
            channel = await db.scalar(
                select(ParticipatingChannel).where(ParticipatingChannel.chat_id == chat.id)
            )
            if channel:
                channel.status = ChannelStatus.REVOKED.value
                channel.revoked_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info("Channel %s left network", chat.id)


@router.channel_post()
async def channel_post(message: Message) -> None:
    async with async_session() as db:
        channel = await db.scalar(
            select(ParticipatingChannel).where(
                ParticipatingChannel.chat_id == message.chat.id,
                ParticipatingChannel.status == ChannelStatus.ACTIVE.value,
            )
        )
        if not channel:
            return

        stmt = pg_insert(ChannelPost).values(
            channel_id=channel.id,
            message_id=message.message_id,
            posted_at=message.date,
            text_preview=_text_preview(message),
            media_type=_media_type(message),
            media_group_id=message.media_group_id,
            forward_from_chat_id=message.forward_from_chat.id if message.forward_from_chat else None,
        ).on_conflict_do_nothing(index_elements=["channel_id", "message_id"])
        result = await db.execute(stmt)
        await db.commit()

        if result.rowcount == 0:
            return

        post_row = await db.scalar(
            select(ChannelPost).where(
                ChannelPost.channel_id == channel.id,
                ChannelPost.message_id == message.message_id,
            )
        )
        if not post_row:
            return

    await enqueue_post(
        channel_pk=channel.id,
        source_chat_id=channel.chat_id,
        source_title=channel.title,
        message_id=message.message_id,
        media_group_id=message.media_group_id,
    )


@router.edited_channel_post()
async def edited_channel_post(message: Message) -> None:
    # MVP: edits are ignored for the relay (forwards captured at original post time).
    # Logged here so we can revisit if needed.
    logger.debug("edited_channel_post in %s msg=%s", message.chat.id, message.message_id)


@router.message_reaction_count()
async def reaction_count(event: MessageReactionCountUpdated) -> None:
    total = sum(r.total_count for r in event.reactions)
    async with async_session() as db:
        channel = await db.scalar(
            select(ParticipatingChannel).where(ParticipatingChannel.chat_id == event.chat.id)
        )
        if not channel:
            return
        post = await db.scalar(
            select(ChannelPost).where(
                ChannelPost.channel_id == channel.id,
                ChannelPost.message_id == event.message_id,
            )
        )
        if not post:
            return
        stmt = pg_insert(PostReaction).values(
            post_id=post.id,
            total_count=total,
        ).on_conflict_do_update(
            index_elements=["post_id"],
            set_={"total_count": total, "last_seen_at": datetime.now(timezone.utc)},
        )
        await db.execute(stmt)
        await db.commit()
