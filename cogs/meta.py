import discord, inspect
from discord.ext import commands

from datetime import datetime

class Meta:
	'''Commands about the bot itself.'''
	
	def __init__(self, bot):
		self.bot = bot
		
	@commands.command(aliases=['join'])
	async def invite(self, ctx):
		'''Get bot invite link.'''
		
		await ctx.send(
			'https://discordapp.com/oauth2/authorize?'
			f'&client_id={self.bot.user.id}'
			'&scope=bot'
			'&permissions=67497025'
		)
		
	@commands.command(aliases=['source'])
	async def code(self, ctx, *, command: str = None):
		'''Show info about a command or get GitHub repo link.'''
		
		if command is None:
			await ctx.send('https://github.com/Run1e/AceBot')
			return
		
		command = self.bot.get_command(command)
		
		if command is None:
			raise commands.CommandError('Couldn\'t find command.')
		
		code = '\n'.join(line[1:] for line in inspect.getsource(command.callback).splitlines())
		code = code.replace('`', '\u200b`')
		await ctx.send(f'```py\n{code}\n```')
			
	@commands.command(hidden=True)
	async def uptime(self, ctx):
		await ctx.send(f'`{str(datetime.now() - self.bot.startup_time).split(".")[0]}`')

	@commands.command(hidden=True)
	async def hello(self, ctx):
		await ctx.send(f'Hello {ctx.author.mention}!')
		

def setup(bot):
	bot.add_cog(Meta(bot))