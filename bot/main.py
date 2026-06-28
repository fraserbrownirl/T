import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    ChatAdministratorRights,
)

from bot import onboarding, source_admin, subscriptions
from bot.fanout import close_redis, start_fanout_workers
from bot.scheduler import start_scheduler
from config import settings
from db.session import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


# Updates we want from Telegram. message_reaction_count, my_chat_member, and chat_member
# are not in the Bot API default and must be requested explicitly.
ALLOWED_UPDATES = [
    "message",
    "channel_post",
    "edited_channel_post",
    "callback_query",
    "message_reaction",
    "message_reaction_count",
    "my_chat_member",
    "chat_member",
]


async def configure_default_admin_rights(bot: Bot) -> None:
    """Default permissions presented when a user adds the bot as admin.

    For broadcast channels (source side): everything off.
    For groups/supergroups (reader side): Manage Topics only.
    """
    try:
        await bot.set_my_default_administrator_rights(
            rights=ChatAdministratorRights(
                is_anonymous=False,
                can_manage_chat=True,
                can_delete_messages=False,
                can_manage_video_chats=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_change_info=False,
                can_invite_users=False,
                can_post_messages=False,
                can_edit_messages=False,
                can_pin_messages=False,
                can_post_stories=False,
                can_edit_stories=False,
                can_delete_stories=False,
                can_manage_topics=False,
            ),
            for_channels=True,
        )
        await bot.set_my_default_administrator_rights(
            rights=ChatAdministratorRights(
                is_anonymous=False,
                can_manage_chat=True,
                can_delete_messages=False,
                can_manage_video_chats=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_change_info=False,
                can_invite_users=False,
                can_post_messages=True,
                can_edit_messages=False,
                can_pin_messages=False,
                can_post_stories=False,
                can_edit_stories=False,
                can_delete_stories=False,
                can_manage_topics=True,
            ),
            for_channels=False,
        )
    except TelegramBadRequest as exc:
        logger.warning("default admin rights setup failed: %s", exc)


async def configure_commands(bot: Bot) -> None:
    """Command menu shown to readers in private chat."""
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Set up or check your feed"),
                BotCommand(command="list", description="Channels in your feed"),
                BotCommand(command="pause", description="Stop new posts"),
                BotCommand(command="resume", description="Resume new posts"),
                BotCommand(command="privacy", description="What data I store"),
            ],
            scope=BotCommandScopeAllPrivateChats(),
        )
    except TelegramBadRequest as exc:
        logger.warning("set_my_commands failed: %s", exc)


async def main() -> None:
    bot = Bot(settings.telegram_bot_token)

    await configure_default_admin_rights(bot)
    await configure_commands(bot)

    dp = Dispatcher()
    dp.include_router(onboarding.router)
    dp.include_router(source_admin.router)
    dp.include_router(subscriptions.router)

    fanout_tasks = await start_fanout_workers(bot)
    sched_tasks = start_scheduler(bot)

    logger.info("starting polling with allowed_updates=%s", ALLOWED_UPDATES)
    try:
        await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)
    finally:
        for t in fanout_tasks + sched_tasks:
            t.cancel()
        await close_redis()
        await engine.dispose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
