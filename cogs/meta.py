import discord, inspect
from discord.ext import commands

from datetime import datetime

from config import feedback_channel


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

	@commands.command()
	async def dbl(self, ctx):
		'''Get link to discordbots.org bot page.'''

		await ctx.send('https://discordbots.org/bot/367977994486022146')
	
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
	
	@commands.command()
	async def support(self, ctx):
		'''Get link to support server.'''
		await ctx.send(self.bot._support_link)
	
	@commands.command(aliases=['fb'])
	@commands.cooldown(rate=1, per=60.0, type=commands.BucketType.user)
	async def feedback(self, ctx, *, feedback: str):
		'''Give me some feedback about the bot!'''
		
		e = discord.Embed(
			title='Feedback',
			description=feedback
		)
		
		e.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
		
		e.add_field(name='Guild', value=f'{ctx.guild.name} ({ctx.guild.id})')
		e.set_footer(text=f'Author ID: {ctx.author.id}')
		
		dest = self.bot.get_channel(feedback_channel)
		
		await dest.send(embed=e)
		await ctx.send('Feedback sent. Thanks for helping improve the bot!')
	
	@commands.command(hidden=True)
	@commands.is_owner()
	async def reply(self, ctx, user: discord.User, *, content):
		content += (
			'\n\n--------------\nThis message was sent in reply to feedback you previously gave. '
			'Please note this conversation is not monitored and replies will not be read. '
			'To get in contact, either use the feedback command again, or join the support server and tag me'
			f' - {ctx.author.mention}\n{self.bot._support_link}'
		)
		
		await user.send(content)
	
	@commands.command(hidden=True)
	async def hello(self, ctx):
		await ctx.send(f'Hello {ctx.author.mention}!')


def setup(bot):
	bot.add_cog(Meta(bot))
