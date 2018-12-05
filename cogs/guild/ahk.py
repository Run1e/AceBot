import discord
from discord.ext import commands

from utils.docs_search import docs_search
from cogs.base import TogglableCogMixin


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


def setup(bot):
	bot.add_cog(AutoHotkey(bot))
