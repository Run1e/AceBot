import discord
from discord.ext import commands

from utils.docs_search import docs_search
from cogs.base import TogglableCogMixin


class AutoHotkey(TogglableCogMixin):
	'''Commands for the AutoHotkey guild.'''
	
	async def __local_check(self, ctx):
		return await self._is_used(ctx)
	
	async def on_message(self, msg):
		if not await self.__local_check(msg) or not await self.bot.blacklist(msg):
			return
		
	async def on_command_error(self, ctx, error):
		if not await self.__local_check(ctx) or not await self.bot.can_run(ctx):
			return

		# command not found? docs search it. only if message string is not *only* dots though
		if isinstance(error, commands.CommandNotFound) and len(ctx.message.content) > 3 and not ctx.message.content.startswith('..'):
			await ctx.invoke(self.docs, search=ctx.message.content[1:])
	
	@commands.command()
	async def docs(self, ctx, *, search):
		'''Search the AutoHotkey documentation.'''
		
		result = docs_search(search)
		embed = discord.Embed()
		if 'fields' in result:
			for field in result['fields']:
				embed.add_field(**field)
		else:
			embed.title = result['title']
			embed.description = result['description']
			if 'url' in result:
				embed.url = result['url']
		
		await ctx.send(embed=embed)
		
def setup(bot):
	bot.add_cog(AutoHotkey(bot))