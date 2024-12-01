import traceback
from datetime import datetime
from pprint import saferepr

import disnake
from disnake.ext import commands


class CommandErrorLogic:
    def __init__(self, ctx, exc):
        self.bot = ctx.bot
        self.ctx = ctx
        self.exc = exc

        self.embed = None
        self.save = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # if an error was never set, do nothing
        if self.embed is None:
            return

        # first try to send error
        try:
            ctx = self.ctx
            e = self.embed

            perms = ctx.perms if isinstance(ctx, commands.Context) else ctx.permissions

            if perms.embed_links:
                if self.save:
                    e.description += self.support_text(True)
                await ctx.send(embed=e)
            else:
                content = str()
                if isinstance(e.title, str):
                    content += e.title
                elif isinstance(e.author.name, str):
                    content += e.author.name

                if isinstance(e.description, str) and len(e.description):
                    content += "\n\n" + e.description

                if self.save:
                    content += self.support_text(False)

                await ctx.send(content)

        except disnake.HTTPException:
            pass

        # after doing that, save and raise if it's an oops
        finally:
            if self.save:
                self.save_error()
                raise self.exc

    @staticmethod
    def new_embed(**kwargs):
        return disnake.Embed(color=0x36393E, **kwargs)

    def support_text(self, embeddable):
        support_link = self.bot.support_link

        content = "\n\nYou can join the support server "

        if embeddable:
            return content + "[here]({0})!".format(support_link)
        else:
            return content + "here: <{0}>".format(support_link)

    def set(self, **kwargs):
        self.embed = self.new_embed(**kwargs)

    def oops(self):
        desc = (
            "An exception occured while processing the command.\n"
            "My developer has been notified and the issue will hopefully be fixed soon!"
        )

        e = self.new_embed(description=desc)
        e.set_author(name="Oops!", icon_url=self.bot.user.display_avatar.url)

        self.save = True
        self.embed = e

    def save_error(self):
        ctx = self.ctx
        exc = self.exc

        timestamp = str(datetime.utcnow()).split(".")[0].replace(" ", "_").replace(":", "")
        filename = str(ctx.message.id) + "_" + timestamp + ".error"

        try:
            raise exc
        except:
            tb = traceback.format_exc()

        content = (
            "{0.stamp}\n\nMESSAGE CONTENT:\n{0.message.content}\n\n"
            "COMMAND: {0.command.qualified_name}\nARGS: {1}\nKWARGS: {2}\n\n{3}"
        ).format(ctx, saferepr(ctx.args[2:]), saferepr(ctx.kwargs), tb)

        with open("data/error/{0}".format(filename), "w", encoding="utf-8-sig") as f:
            f.write(content)
