"""Reader-side: /start, supergroup detection, topic creation."""
from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot, Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import ChatMemberUpdated, Message
from sqlalchemy import select

from bot import copy as copy_strings
from bot.subscriptions import resolve_deep_link_add
from db.models import SetupState, User
from db.session import async_session

logger = logging.getLogger(__name__)
router = Router(name="onboarding")

ADMIN_STATUSES = {"administrator", "creator"}


async def get_or_create_user(telegram_id: int) -> User:
    async with async_session() as db:
        user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
        if user:
            return user
        user = User(telegram_id=telegram_id, setup_state=SetupState.AWAITING_SUPERGROUP.value)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


@router.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message, command: CommandObject, bot: Bot) -> None:
    user = await get_or_create_user(message.from_user.id)

    if command.args and command.args.startswith("add_"):
        await resolve_deep_link_add(bot, message, user, command.args[len("add_"):])
        return

    if user.setup_state == SetupState.ACTIVE.value:
        await message.answer(copy_strings.START_ACTIVE_USER, parse_mode="HTML")
        return
    if user.setup_state == SetupState.PAUSED.value:
        await message.answer(copy_strings.START_PAUSED_USER, parse_mode="HTML")
        return

    await message.answer(copy_strings.START_NEW_USER, parse_mode="HTML")


@router.my_chat_member(F.chat.type == "supergroup")
async def supergroup_admin_change(event: ChatMemberUpdated, bot: Bot) -> None:
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    became_admin = old_status not in ADMIN_STATUSES and new_status in ADMIN_STATUSES
    if not became_admin:
        return

    promoter_id = event.from_user.id if event.from_user else None
    if not promoter_id:
        logger.warning("Bot promoted to admin in %s with no from_user", event.chat.id)
        return

    if not event.chat.is_forum:
        try:
            await bot.send_message(
                promoter_id,
                "I see I've been added to a group, but it doesn't have topics enabled. "
                "Enable Topics in the group's settings, then re-add me as admin so I can set things up.",
            )
        except TelegramBadRequest:
            pass
        return

    async with async_session() as db:
        user = await db.scalar(select(User).where(User.telegram_id == promoter_id))
        if not user:
            user = User(
                telegram_id=promoter_id,
                setup_state=SetupState.AWAITING_SUPERGROUP.value,
            )
            db.add(user)
            await db.flush()

        if user.setup_state == SetupState.ACTIVE.value and user.feed_supergroup_id == event.chat.id:
            return

    await _provision_topics(bot, promoter_id, event.chat.id)


async def _provision_topics(bot: Bot, telegram_user_id: int, supergroup_id: int) -> None:
    new_id = await _create_topic(bot, supergroup_id, copy_strings.TOPIC_NEWEST)
    pop_id = await _create_topic(bot, supergroup_id, copy_strings.TOPIC_POPULAR)
    fyou_id = await _create_topic(bot, supergroup_id, copy_strings.TOPIC_FORYOU)

    if not (new_id and pop_id and fyou_id):
        try:
            await bot.send_message(
                telegram_user_id,
                "I couldn't create the topics. Make sure I have the <b>Manage Topics</b> "
                "permission, then re-add me as admin.",
                parse_mode="HTML",
            )
        except TelegramBadRequest:
            pass
        return

    async with async_session() as db:
        user = await db.scalar(select(User).where(User.telegram_id == telegram_user_id))
        if not user:
            return
        user.feed_supergroup_id = supergroup_id
        user.topic_newest_id = new_id
        user.topic_popular_id = pop_id
        user.topic_foryou_id = fyou_id
        user.setup_state = SetupState.ACTIVE.value
        await db.commit()

    await _post_welcome(bot, supergroup_id, new_id, copy_strings.WELCOME_NEWEST)
    await _post_welcome(bot, supergroup_id, pop_id, copy_strings.WELCOME_POPULAR)
    await _post_welcome(bot, supergroup_id, fyou_id, copy_strings.WELCOME_FORYOU)

    try:
        await bot.send_message(telegram_user_id, copy_strings.SETUP_DONE, parse_mode="HTML")
    except TelegramBadRequest:
        pass


async def _create_topic(bot: Bot, chat_id: int, name: str) -> Optional[int]:
    try:
        topic = await bot.create_forum_topic(chat_id=chat_id, name=name)
        return topic.message_thread_id
    except TelegramBadRequest as exc:
        logger.warning("create_forum_topic failed chat=%s name=%s: %s", chat_id, name, exc)
        return None


async def _post_welcome(bot: Bot, chat_id: int, topic_id: int, text: str) -> None:
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            message_thread_id=topic_id,
            parse_mode="HTML",
        )
    except TelegramBadRequest as exc:
        logger.warning("welcome post failed chat=%s topic=%s: %s", chat_id, topic_id, exc)
