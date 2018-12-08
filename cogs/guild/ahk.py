import discord, asyncio
from discord.ext import commands

from utils.docs_search import docs_search
from utils.welcome import welcomify
from cogs.base import TogglableCogMixin

GENERAL_ID = 115993023636176902
STAFF_ID = 311784919208558592
MEMBER_ID = 509526426198999040

WELCOME_MSG = '''
Welcome to our Discord community {user}!
A collection of useful tips are in <#407666416297443328> and recent announcements can be found in <#367301754729267202>.
'''


class AutoHotkey(TogglableCogMixin):
	'''Commands for the AutoHotkey guild.'''

	async def __local_check(self, ctx):
		return await self._is_used(ctx)

	async def on_command_error(self, ctx, error):
		if ctx.guild.id != 115993023636176902:
			return

		# command not found? docs search it. only if message string is not *only* dots though
		if isinstance(error, commands.CommandNotFound) and len(
				ctx.message.content) > 3 and not ctx.message.content.startswith('..'):
			await ctx.invoke(self.docs, search=ctx.message.content[1:])

	@commands.command()
	async def docs(self, ctx, *, search):
		'''Search the AutoHotkey documentation.'''
		embed = discord.Embed()
		results = docs_search(search)

		if not len(results):
			raise commands.CommandError('No documentation pages found.')

		elif len(results) == 1:
			for title, obj in results.items():
				embed.title = obj.get('syntax', title)
				embed.description = obj['desc']
				if 'dir' in obj:
					embed.url = f"https://autohotkey.com/docs/{obj['dir']}"

		else:
			for title, obj in results.items():
				value = obj['desc']
				if 'dir' in obj:
					value += f"\n[Documentation](https://autohotkey.com/docs/{obj['dir']})"
				embed.add_field(
					name=obj.get('syntax', title),
					value=value
				)

		await ctx.send(embed=embed)

	@commands.command(hidden=True)
	@commands.has_role(STAFF_ID)
	async def approve(self, ctx, member: discord.Member):
		'''Approve member.'''

		try:
			member_role = ctx.guild.get_role(MEMBER_ID)
			if member_role is None:
				raise commands.CommandError('Couldn\'t find role.')
			await member.add_roles(
				member_role,
				reason=f'Approved by {ctx.author.name}'
			)
		except Exception as exc:
			raise commands.CommandError('Failed adding member role.\n\nError:\n' + str(exc))

		await asyncio.sleep(3)

		general_channel = ctx.guild.get_channel(GENERAL_ID)

		if general_channel is None:
			raise commands.CommandError('Couldn\'t find the #general channel.')

		await general_channel.send(welcomify(member, ctx.guild, WELCOME_MSG))


def setup(bot):
	bot.add_cog(AutoHotkey(bot))
