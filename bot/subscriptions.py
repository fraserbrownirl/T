"""Reader-side: add/remove channels, /list, /pause, /resume, and membership checks."""
from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
)
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from bot import copy as copy_strings
from config import settings
from db.models import ChannelStatus, ParticipatingChannel, SetupState, Subscription, User
from db.session import async_session

logger = logging.getLogger(__name__)
router = Router(name="subscriptions")

MEMBER_STATUSES = {"creator", "administrator", "member"}


async def _get_user(telegram_id: int) -> Optional[User]:
    async with async_session() as db:
        return await db.scalar(select(User).where(User.telegram_id == telegram_id))


async def is_subscriber(bot: Bot, channel_chat_id: int, user_telegram_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel_chat_id, user_id=user_telegram_id)
        return member.status in MEMBER_STATUSES
    except TelegramBadRequest as exc:
        logger.info(
            "get_chat_member failed chat=%s user=%s: %s", channel_chat_id, user_telegram_id, exc
        )
        return False


async def _add_subscription(user: User, channel: ParticipatingChannel) -> str:
    """Insert or revive subscription. Returns one of: 'added', 'already', 'resumed'."""
    async with async_session() as db:
        existing = await db.scalar(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.channel_id == channel.id,
            )
        )
        if existing:
            if existing.paused:
                existing.paused = False
                await db.commit()
                return "resumed"
            return "already"
        db.add(Subscription(user_id=user.id, channel_id=channel.id))
        await db.commit()
        return "added"


async def _try_add_by_channel_chat_id(
    bot: Bot, message: Message, user: User, channel_chat_id: int, source_title_hint: str | None
) -> None:
    async with async_session() as db:
        channel = await db.scalar(
            select(ParticipatingChannel).where(ParticipatingChannel.chat_id == channel_chat_id)
        )

    if not channel or channel.status != ChannelStatus.ACTIVE.value:
        await message.answer(
            copy_strings.ADD_NOT_PARTICIPATING.format(title=source_title_hint or "that channel"),
            parse_mode="HTML",
        )
        return

    is_member = await is_subscriber(bot, channel.chat_id, user.telegram_id)
    if not is_member:
        await message.answer(
            copy_strings.ADD_NOT_MEMBER.format(title=channel.title),
            parse_mode="HTML",
        )
        return

    outcome = await _add_subscription(user, channel)
    if outcome == "already":
        await message.answer(
            copy_strings.ADD_ALREADY_SUBSCRIBED.format(title=channel.title),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            copy_strings.ADD_OK.format(title=channel.title),
            parse_mode="HTML",
        )


@router.message(F.chat.type == "private", F.forward_from_chat)
async def forward_to_add(message: Message, bot: Bot) -> None:
    user = await _get_user(message.from_user.id)
    if not user or user.setup_state == SetupState.AWAITING_SUPERGROUP.value:
        await message.answer(copy_strings.NEED_SUPERGROUP)
        return

    fwd_chat = message.forward_from_chat
    if not fwd_chat:
        await message.answer(copy_strings.ADD_UNKNOWN_CHANNEL)
        return

    await _try_add_by_channel_chat_id(bot, message, user, fwd_chat.id, fwd_chat.title)


async def resolve_deep_link_add(bot: Bot, message: Message, user: User, payload: str) -> None:
    """Called from /start when payload looks like 'add_<channel_pk>'."""
    try:
        channel_pk = int(payload)
    except ValueError:
        await message.answer(copy_strings.ADD_UNKNOWN_CHANNEL)
        return

    async with async_session() as db:
        channel = await db.get(ParticipatingChannel, channel_pk)

    if not channel or channel.status != ChannelStatus.ACTIVE.value:
        await message.answer(copy_strings.ADD_NOT_PARTICIPATING.format(title="that channel"))
        return

    if user.setup_state == SetupState.AWAITING_SUPERGROUP.value:
        await message.answer(copy_strings.NEED_SUPERGROUP)
        return

    await _try_add_by_channel_chat_id(bot, message, user, channel.chat_id, channel.title)


@router.message(Command("list"), F.chat.type == "private")
async def cmd_list(message: Message) -> None:
    user = await _get_user(message.from_user.id)
    if not user:
        await message.answer(copy_strings.NEED_SUPERGROUP)
        return

    async with async_session() as db:
        rows = (
            await db.execute(
                select(Subscription, ParticipatingChannel)
                .join(ParticipatingChannel, Subscription.channel_id == ParticipatingChannel.id)
                .where(Subscription.user_id == user.id)
                .order_by(ParticipatingChannel.title)
            )
        ).all()

    if not rows:
        await message.answer(copy_strings.LIST_EMPTY)
        return

    header = copy_strings.LIST_HEADER.format(count=len(rows), plural="" if len(rows) == 1 else "s")
    lines = [header]
    keyboard_rows = []
    for sub, channel in rows:
        status = " (paused)" if sub.paused else ""
        lines.append(f"- <b>{channel.title}</b>{status}")
        buttons = []
        if sub.paused:
            buttons.append(InlineKeyboardButton(text=f"Resume {channel.title[:20]}", callback_data=f"sub:resume:{sub.id}"))
        else:
            buttons.append(InlineKeyboardButton(text=f"Pause {channel.title[:20]}", callback_data=f"sub:pause:{sub.id}"))
        buttons.append(InlineKeyboardButton(text="Remove", callback_data=f"sub:remove:{sub.id}"))
        keyboard_rows.append(buttons)

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
    )


@router.message(Command("privacy"), F.chat.type == "private")
async def cmd_privacy(message: Message) -> None:
    url = settings.privacy_policy_url.strip()
    if url:
        await message.answer(
            copy_strings.PRIVACY_WITH_URL.format(url=url),
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    else:
        await message.answer(copy_strings.PRIVACY_SUMMARY, parse_mode="HTML")


@router.message(Command("pause"), F.chat.type == "private")
async def cmd_pause(message: Message) -> None:
    user = await _get_user(message.from_user.id)
    if not user:
        await message.answer(copy_strings.NEED_SUPERGROUP)
        return
    async with async_session() as db:
        u = await db.get(User, user.id)
        if u:
            u.setup_state = SetupState.PAUSED.value
            await db.commit()
    await message.answer(copy_strings.PAUSED_OK)


@router.message(Command("resume"), F.chat.type == "private")
async def cmd_resume(message: Message) -> None:
    user = await _get_user(message.from_user.id)
    if not user:
        await message.answer(copy_strings.NEED_SUPERGROUP)
        return
    async with async_session() as db:
        u = await db.get(User, user.id)
        if u and u.feed_supergroup_id:
            u.setup_state = SetupState.ACTIVE.value
            await db.commit()
    await message.answer(copy_strings.RESUMED_OK)


@router.callback_query(F.data.startswith("sub:"))
async def callback_sub(query: CallbackQuery) -> None:
    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer()
        return
    _, action, sub_id_str = parts
    try:
        sub_id = int(sub_id_str)
    except ValueError:
        await query.answer()
        return

    user = await _get_user(query.from_user.id)
    if not user:
        await query.answer("Not set up", show_alert=True)
        return

    async with async_session() as db:
        sub = await db.scalar(
            select(Subscription).where(Subscription.id == sub_id, Subscription.user_id == user.id)
        )
        if not sub:
            await query.answer("Already removed", show_alert=False)
            return

        if action == "remove":
            await db.execute(delete(Subscription).where(Subscription.id == sub_id))
            await db.commit()
            await query.answer("Removed")
        elif action == "pause":
            sub.paused = True
            await db.commit()
            await query.answer("Paused")
        elif action == "resume":
            sub.paused = False
            await db.commit()
            await query.answer("Resumed")
        else:
            await query.answer()


@router.message(F.chat.type == "private", ~F.forward_from_chat, ~F.text.startswith("/"))
async def fallback_private_message(message: Message) -> None:
    if message.forward_origin and not message.forward_from_chat:
        await message.answer(copy_strings.ADD_UNKNOWN_CHANNEL)
        return
    await message.answer(copy_strings.NO_FORWARD)
