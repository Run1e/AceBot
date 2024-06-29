import asyncio
import copy
import io
import logging
import textwrap
import traceback
from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from urllib.parse import urlparse

import disnake
from bs4 import BeautifulSoup
from disnake.ext import commands
from disnake.mixins import Hashable
from tabulate import tabulate

from cogs.mixins import AceMixin
from config import BOT_ACTIVITY
from utils.context import AceContext
from utils.converters import MaxValueConverter
from utils.pager import Pager
from utils.string import shorten
from utils.time import pretty_datetime, pretty_timedelta

log = logging.getLogger(__name__)


class Owner(AceMixin, commands.Cog):
    """Commands accessible only to the bot owner."""

    def __init__(self, bot):
        super().__init__(bot)

        self.help_cog = bot.get_cog("AutoHotkeyHelpSystem")
        self.event_counter = Counter()

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""

        # remove ```py\n```
        if content.startswith("```") and content.endswith("```"):
            return "\n".join(content.split("\n")[1:-1])

        # remove `foo`
        return content.strip("` \n")

    @commands.Cog.listener()
    async def on_socket_event_type(self, event_type):
        self.event_counter[event_type] += 1

    @commands.command(hidden=True)
    async def prompt(self, ctx: AceContext, user: disnake.Member = None):
        result = await ctx.prompt(user_override=user)
        await ctx.send(result)

    @commands.command(hidden=True)
    async def adminprompt(self, ctx: AceContext):
        result = await ctx.admin_prompt()
        await ctx.send(result)

    @commands.command()
    async def eval(self, ctx, *, body: str):
        """Evaluates some code."""

        from pprint import pprint

        from tabulate import tabulate

        env = {
            "disnake.": disnake,
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
            "pprint": pprint,
            "tabulate": tabulate,
            "db": self.db,
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f"```py\n{e.__class__.__name__}: {e}\n```")

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f"```py\n{value}{traceback.format_exc()}\n```")
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction("\u2705")
            except:
                pass

            if ret is None:
                if value:
                    if len(value) > 1990:
                        fp = io.BytesIO(value.encode("utf-8"))
                        await ctx.send("Log too large...", file=disnake.File(fp, "results.txt"))
                    else:
                        await ctx.send(f"```py\n{value}\n```")

    @commands.command()
    async def sql(self, ctx, *, query: str):
        """Execute a SQL query."""

        try:
            result = await self.db.fetch(query)
        except Exception as exc:
            raise commands.CommandError(str(exc))

        if not len(result):
            await ctx.send("No rows returned.")
            return

        table = tabulate(result, {header: header for header in result[0].keys()})

        if len(table) > 1994:
            fp = io.BytesIO(table.encode("utf-8"))
            await ctx.send("Too many results...", file=disnake.File(fp, "results.txt"))
        else:
            await ctx.send("```" + table + "```")

    @commands.command()
    async def gateway(self, ctx, *, n=None):
        """Print gateway event counters."""

        table = tabulate(
            tabular_data=[
                (name, format(count, ",d")) for name, count in self.event_counter.most_common(n)
            ],
            headers=("Event", "Count"),
        )

        paginator = commands.Paginator()
        for line in table.split("\n"):
            paginator.add_line(line)

        for page in paginator.pages:
            await ctx.send(page)

    @commands.command()
    async def ping(self, ctx):
        """Check response time."""

        msg = await ctx.send("Wait...")

        await msg.edit(
            content="Response: {}.\nGateway: {}".format(
                pretty_timedelta(msg.created_at - ctx.message.created_at),
                pretty_timedelta(timedelta(seconds=self.bot.latency)),
            )
        )

    @commands.command()
    async def repeat(self, ctx, repeats: int, *, command):
        """Repeat a command."""

        if repeats < 1:
            raise commands.CommandError("Repeat count must be more than 0.")

        msg = copy.copy(ctx.message)
        msg.content = ctx.prefix + command

        new_ctx = await self.bot.get_context(msg, cls=AceContext)

        for i in range(repeats):
            await new_ctx.reinvoke()

    @commands.command(name="reload", aliases=["rl"])
    @commands.bot_has_permissions(add_reactions=True)
    async def _reload(self, ctx):
        """Reload edited extensions."""

        reloaded = self.bot.load_extensions()

        if reloaded:
            log.info("Reloaded cogs: %s", ", ".join(reloaded))
            await ctx.send("Reloaded cogs: " + ", ".join("`{0}`".format(ext) for ext in reloaded))
        else:
            await ctx.send("Nothing to reload.")

    @commands.command()
    async def decache(self, ctx, guild_id: int):
        """Clear cache of table data of a specific guild."""

        configs = (
            self.bot.config,
            self.bot.get_cog("Starboard").config,
            self.bot.get_cog("Moderation").config,
            self.bot.get_cog("Welcome").config,
            self.bot.get_cog("Roles").config,
        )

        cleared = []

        for config in configs:
            if await config.clear_entry(guild_id):
                cleared.append(config)

        await ctx.send(
            "Cleared entries for:\n```\n{0}\n```".format(
                "\n".join(config.table for config in cleared)
            )
        )

    @commands.command()
    @commands.bot_has_permissions(manage_messages=True)
    async def say(self, ctx, channel: disnake.TextChannel, *, content: str):
        """Send a message in a channel."""

        await ctx.message.delete()
        await channel.send(content)

    @commands.command()
    async def status(self, ctx):
        """Refresh the status of the bot in case Discord cleared it."""

        await self.bot.change_presence()
        await self.bot.change_presence(activity=BOT_ACTIVITY)

    @commands.command()
    async def print(self, ctx, *, body: str):
        """Calls eval but wraps code in print()"""

        await ctx.invoke(self.eval, body=f"pprint({body})")


def setup(bot):
    bot.add_cog(Owner(bot))
