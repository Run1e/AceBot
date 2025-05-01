import logging
import re

import disnake
from disnake.ext import commands

from cogs.mixins import AceMixin
from ids import AHK_GUILD_ID
from utils.context import is_mod
from utils.converters import LengthConverter

log = logging.getLogger(__name__)

DELETE_EMOJI = "\N{Put Litter in Its Place Symbol}"
DEFAULT_LANG = "py"


class LangConverter(LengthConverter):
    async def convert(self, ctx, argument):
        argument = await super().convert(ctx, argument)

        if argument != disnake.utils.escape_markdown(argument):
            raise commands.BadArgument("No markdown allowed in the codebox language.")

        return argument


lang_converter = LangConverter(1, 32)


class Highlighter(AceMixin, commands.Cog):
    """Create highlighted code-boxes with one command."""

    @commands.command(aliases=["h1"])
    @commands.bot_has_permissions(manage_messages=True, add_reactions=True)
    async def hl(self, ctx, *, code):
        """Highlight some code."""

        await ctx.message.delete()

        # include spaces/tabs at the beginning
        code = ctx.message.content[len(ctx.prefix) + 3 :]

        # don't allow three backticks in a row, alternative is to throw error upon this case
        code = code.replace("``", "`\u200b`")

        # replace triple+ newlines with double newlines
        code = re.sub("\n\n+", "\n\n", code)

        # trim start and finish
        code = code.strip()

        # get the language this user should use
        lang = (
            await self.db.fetchval(
                "SELECT lang FROM highlight_lang WHERE guild_id=$1 AND (user_id=$2 OR user_id=$3)",
                ctx.guild.id,
                0,
                ctx.author.id,
            )
            or DEFAULT_LANG
        )

        code = "```{}\n{}\n```".format(lang, code)
        code += "*Paste by {0} - Click {1} to delete.*".format(ctx.author.mention, DELETE_EMOJI)

        if len(code) > 2000:
            raise commands.CommandError("Code contents too long to paste.")

        ar = disnake.ui.ActionRow()
        ar.add_button(
            0,
            style=disnake.ButtonStyle.secondary,
            label="🗑️",
            custom_id=f"hldeletebutton_{ctx.author.id}",
        )
        await ctx.send(code, components=[ar])

    @commands.Cog.listener()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if inter.guild_id is None:
            return

        if not inter.component.custom_id.startswith("hldeletebutton"):
            return

        try:
            author_id: str = int(inter.component.custom_id.split("_")[1])
        except ValueError:
            return

        if author_id != inter.author.id:
            await inter.response.send_message(
                "Sorry, this button is not for you!",
                ephemeral=True,
                delete_after=12,
            )
            return

        await inter.message.delete()

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def lang(self, ctx, *, language: lang_converter = None):
        """Set your preferred highlighting language in this server."""

        if language is None:
            server_lang = await self.db.fetchval(
                "SELECT lang FROM highlight_lang WHERE guild_id=$1 AND user_id=$2",
                ctx.guild.id,
                0,
            )

            user_lang = await self.db.fetchval(
                "SELECT lang FROM highlight_lang WHERE guild_id=$1 AND user_id=$2",
                ctx.guild.id,
                ctx.author.id,
            )

            e = disnake.Embed(description="Do `.lang clear` to clear preference.")

            e.add_field(
                name="Server setting",
                value=f'`{DEFAULT_LANG + " (default)" if server_lang is None else server_lang}`',
            )

            e.add_field(
                name="Personal setting",
                value="Not set" if user_lang is None else f"`{user_lang}`",
            )

            await ctx.send(embed=e)
            return

        if language == "clear":
            ret = await self.db.execute(
                "DELETE FROM highlight_lang WHERE guild_id=$1 AND user_id=$2",
                ctx.guild.id,
                ctx.author.id,
            )

            await ctx.send(
                "No preference previously set" if ret == "DELETE 0" else "Preference cleared."
            )
        else:
            await self.db.execute(
                "INSERT INTO highlight_lang (guild_id, user_id, lang) VALUES ($1, $2, $3) ON CONFLICT "
                "(guild_id, user_id) DO UPDATE SET lang=$3",
                ctx.guild.id,
                ctx.author.id,
                language,
            )

            await ctx.send(f"Set your specific highlighting language to '{language}'.")

    @commands.command(aliases=["guildlang"])
    @is_mod()
    async def serverlang(self, ctx, *, language: lang_converter):
        """Set a guild-specific highlighting language. Can be overridden individually by users."""

        if language == "clear":
            ret = await self.db.execute(
                "DELETE FROM highlight_lang WHERE guild_id=$1 AND user_id=$2",
                ctx.guild.id,
                0,
            )

            await ctx.send(
                "No preference previously set" if ret == "DELETE 0" else "Preference cleared."
            )
        else:
            await self.db.execute(
                "INSERT INTO highlight_lang (guild_id, user_id, lang) VALUES ($1, $2, $3) ON CONFLICT "
                "(guild_id, user_id) DO UPDATE SET lang=$3",
                ctx.guild.id,
                0,
                language,
            )

            await ctx.send(f"Set server-specific highlighting language to '{language}'.")

    @commands.command(aliases=["p"], hidden=True)
    async def paste(self, ctx):
        """Legacy, not removed because some people still use it instead of the newer tags in the tag system."""

        msg = "To paste code snippets directly into the chat, use the highlight command:\n```.hl *paste code here*```"

        if ctx.guild.id == AHK_GUILD_ID:
            msg += (
                "\nIf you have a larger script you want to share, paste it to the AutoHotkey pastebin instead:\n"
                "https://p.autohotkey.com/"
            )

        await ctx.send(msg)


def setup(bot):
    bot.add_cog(Highlighter(bot))
