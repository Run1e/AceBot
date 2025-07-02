import asyncio
from typing import TYPE_CHECKING

import disnake
from disnake.ext import commands

from utils.string import po
from utils.time import pretty_datetime

if TYPE_CHECKING:
    from ace import AceBot

STATIC_PERMS = ("add_reactions", "manage_messages", "embed_links")
PROMPT_REQUIRED_PERMS = ("embed_links",)
PROMPT_EMOJIS = ("\N{WHITE HEAVY CHECK MARK}", "\N{CROSS MARK}")


async def is_mod_pred(ctx):
    return await ctx.is_mod()


def is_mod():
    return commands.check(is_mod_pred)


async def can_prompt_pred(ctx):
    perms = ctx.perms
    missing_perms = list(perm for perm in PROMPT_REQUIRED_PERMS if not getattr(perms, perm))

    if not missing_perms:
        return True

    raise commands.BotMissingPermissions(missing_perms)


def can_prompt():
    return commands.check(can_prompt_pred)


class PromptView(disnake.ui.View):
    def __init__(self, check_user, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.check_user = check_user
        self.message = None

        self.result = False
        self.event = asyncio.Event()

    async def finish(self, message: disnake.Message):
        self.event.set()

        if message is not None:
            try:
                await message.delete()
            except disnake.HTTPException:
                pass

    async def wait(self):
        await self.event.wait()
        return self.result

    async def on_timeout(self) -> None:
        await self.finish(self.message)

    async def interaction_check(self, interaction: disnake.MessageInteraction):
        return interaction.author == self.check_user

    @disnake.ui.button(
        label="Continue",
        emoji="\N{WHITE HEAVY CHECK MARK}",
        style=disnake.ButtonStyle.primary,
    )
    async def yes(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        self.result = True
        await self.finish(inter.message)

    @disnake.ui.button(label="Abort", emoji="\N{CROSS MARK}", style=disnake.ButtonStyle.secondary)
    async def no(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        self.result = False
        await self.finish(inter.message)


class AceContext(commands.Context):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bot: "AceBot"

    @property
    def db(self):
        return self.bot.db

    @property
    def http(self):
        return self.bot.aiohttp

    @property
    def perms(self):
        return self.channel.permissions_for(self.guild.me)

    @property
    def pretty(self):
        return "{0.display_name} ({0.id}) in {1.name} ({1.id})".format(self.author, self.guild)

    @property
    def stamp(self):
        return "TIME: {}\nGUILD: {}\nCHANNEL: #{}\nAUTHOR: {}\nMESSAGE ID: {}".format(
            pretty_datetime(self.message.created_at),
            po(self.guild),
            po(self.channel),
            po(self.author),
            str(self.message.id),
        )

    async def is_mod(self, member=None):
        """Check if invoker or member has bot moderator rights."""

        member = member or self.author

        # always allow bot owner
        if member.id == self.bot.owner_id:
            return True

        # true if member has administrator perms in this channel
        if self.channel.permissions_for(member).administrator:
            return True

        # only last way member can be mod if they're in the moderator role
        gc = await self.bot.config.get_entry(member.guild.id)

        # false if not set
        if gc.mod_role_id is None:
            return False

        # if set, see if author has this role

        return bool(disnake.utils.get(member.roles, id=gc.mod_role_id))

    async def send_help(self, command=None):
        """Convenience method for sending help."""

        perms = self.perms
        missing_perms = list(perm for perm in STATIC_PERMS if not getattr(perms, perm))

        if missing_perms:
            help_cmd = self.bot.static_help_command
            help_cmd.missing_perms = missing_perms
        else:
            help_cmd = self.bot.help_command

        help_cmd.context = self

        if isinstance(command, commands.Command):
            command = command.qualified_name

        await help_cmd.command_callback(self, command=command)

    async def prompt(self, title=None, prompt=None, user_override=None):
        """Creates a yes/no prompt."""

        perms = self.perms
        if not all(getattr(perms, perm) for perm in PROMPT_REQUIRED_PERMS):
            return False

        e = disnake.Embed(description=prompt or "No description provided.")

        e.set_author(name=title or "Prompt", icon_url=self.bot.user.display_avatar.url)

        view = PromptView(check_user=user_override or self.author, timeout=60.0)

        try:
            message = await self.send(
                content=None if user_override is None else user_override.mention,
                embed=e,
                view=view,
            )

            view.message = message
        except disnake.HTTPException:
            return False

        return await view.wait()

    async def admin_prompt(self, raise_on_abort=True):
        result = await self.prompt(
            title="Warning!",
            prompt=(
                "You are about to do an administrative action on an item you do not own.\n\n"
                "Are you sure you want to continue?"
            ),
        )

        if raise_on_abort and not result:
            raise commands.CommandError("Administrative action aborted.")

        return result
