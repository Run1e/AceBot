import disnake
from ace import AceBot
from cogs.mixins import AceMixin
from disnake.ext import commands
from utils.commanderrorlogic import CommandErrorLogic
from utils.context import AceContext
from utils.time import pretty_seconds


class ErrorHandler(commands.Cog, AceMixin):
	@commands.Cog.listener()
	async def on_command_error(self, ctx: AceContext, exc):
		'''Handle command errors.'''
		async with CommandErrorLogic(ctx, exc) as handler:
			if isinstance(exc, commands.CommandInvokeError):
				if isinstance(exc.original, disnake.HTTPException):
					self.bot.log.debug('Command failed with %s', str(exc.original))
					return
				handler.oops()

			elif isinstance(exc, commands.ConversionError):
				handler.oops()

			elif isinstance(exc, commands.UserInputError):
				handler.set(
					title=str(exc),
					description='Usage: `{0.prefix}{1.qualified_name} {1.signature}`'.format(ctx, ctx.command),
				)

			elif isinstance(exc, commands.DisabledCommand):
				handler.set(description='Sorry, command has been disabled by owner. Try again later!')

			elif isinstance(exc, commands.CommandOnCooldown):
				handler.set(
					title='You are on cooldown.',
					description='Try again in {0}.'.format(pretty_seconds(exc.retry_after)),
				)

			elif isinstance(exc, commands.BotMissingPermissions):
				handler.set(description=str(exc))

			elif isinstance(exc, (commands.CheckFailure, commands.CommandNotFound)):
				return

			elif isinstance(exc, commands.CommandError):
				handler.set(description=str(exc))

			elif isinstance(exc, disnake.DiscordException):
				handler.oops()


def setup(bot: AceBot):
	bot.add_cog(ErrorHandler(bot))
