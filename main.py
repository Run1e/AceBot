import asyncio
import logging.handlers
import os

import asyncpg
import coloredlogs
import disnake
from disnake.ext.commands import CommandSyncFlags

from ace import AceBot
from config import BOT_INTENTS, BOT_TOKEN, LOG_LEVEL, TEST_GUILDS


def setup_logger():
    # init first log file
    if not os.path.isfile("logs/log.log"):
        # we have to make the logs dir before we log to it
        if not os.path.exists("logs"):
            os.makedirs("logs")
        open("logs/log.log", "w+")

    # set logging levels for various libs
    logging.getLogger("disnake").setLevel(logging.INFO)
    logging.getLogger("websockets").setLevel(logging.INFO)
    logging.getLogger("asyncpg").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.INFO)

    # we want out logging formatted like this everywhere
    fmt = logging.Formatter(
        "{asctime} [{levelname}] {name}: {message}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{",
    )

    coloredlogs.install(
        level=logging.DEBUG,
        fmt="{asctime} [{levelname}] {name}: {message}",
        style="{",
        level_styles=dict(
            debug=dict(color=12),
            info=dict(color=15),
            warning=dict(bold=True, color=13),
            critical=dict(bold=True, color=9),
        ),
    )

    file = logging.handlers.TimedRotatingFileHandler(
        "logs/log.log", when="midnight", encoding="utf-8-sig"
    )
    file.setFormatter(fmt)
    file.setLevel(logging.INFO)

    # get the __main__ logger and add handlers
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    root.addHandler(file)

    return logging.getLogger(__name__)


def setup():
    # create folders
    for path in ("data", "error", "feedback", "ahk_eval"):
        if not os.path.exists(path):
            log.info("Creating folder: %s", path)
            os.makedirs(path)

    # misc. monkey-patching
    class Embed(disnake.Embed):
        def __init__(self, color=disnake.Color.blue(), **attrs):
            attrs["color"] = color
            super().__init__(**attrs)

    disnake.Embed = Embed

    def patched_execute(old):
        async def new(
            self,
            query,
            args,
            limit,
            timeout,
            return_status=False,
            ignore_custom_codec=False,
            record_class=None,
        ):
            log.debug(query)
            return await old(
                self,
                query,
                args,
                limit,
                timeout,
                return_status=return_status,
                ignore_custom_codec=ignore_custom_codec,
                record_class=record_class,
            )

        return new

    asyncpg.Connection._execute = patched_execute(asyncpg.Connection._execute)

    # create allowed mentions
    allowed_mentions = disnake.AllowedMentions(
        everyone=False,
        users=True,
        roles=False,
        replied_user=True,
    )

    command_sync_flags = CommandSyncFlags(
        allow_command_deletion=True,
        sync_commands=True,
        sync_commands_debug=True,
        sync_global_commands=True,
        sync_guild_commands=True,
        sync_on_cog_actions=False,
    )

    # init bot
    log.info("Initializing bot")
    bot = AceBot(
        loop=loop,
        intents=BOT_INTENTS,
        allowed_mentions=allowed_mentions,
        command_sync_flags=command_sync_flags,
        test_guilds=TEST_GUILDS,
    )

    return bot


if __name__ == "__main__":
    log = setup_logger()
    loop = asyncio.get_event_loop()

    bot = setup()
    bot.run(BOT_TOKEN)
