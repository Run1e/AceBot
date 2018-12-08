import discord, asyncio
from discord.ext import commands

from utils.database import WelcomeMsg
from utils.strip_markdown import strip_markdown
from utils.welcome import welcomify
from utils.checks import is_manager
from cogs.base import TogglableCogMixin


class Welcome(TogglableCogMixin):
	'''Make the bot send welcome messages to new users.'''
	
	_sleep = 3 # seconds
	
	async def __local_check(self, ctx):
		return await self._is_used(ctx)
	
	async def get_welcome(self, guild_id):
		welc = await WelcomeMsg.query.where(
			WelcomeMsg.guild_id == guild_id
		).gino.first()
		
		if welc is not None:
			return welc
		
		return await WelcomeMsg.create(
			guild_id=guild_id,
			channel_id=None,
			content='Hello {user} and welcome to {guild}!',
		)
	
	async def on_member_join(self, member):
		if not await self._is_used(member):
			return
			
		guild = member.guild
			
		welc = await self.get_welcome(guild.id)
		
		channel = guild.get_channel(welc.channel_id)

		if channel is None:
			return
		
		await asyncio.sleep(self._sleep)
		
		await channel.send(welcomify(member, guild, welc.content))
	
	@commands.group()
	@is_manager()
	async def welcome(self, ctx):
		'''Welcome your users with a message!'''
	
		if ctx.invoked_subcommand is not None:
			return
		
		help_text = await self.bot.formatter.format_help_for(ctx, ctx.command)
		await ctx.send('\n'.join(help_text[0].split('\n')[:-3]) + '```')
	
	@welcome.command()
	async def msg(self, ctx, *, content: commands.clean_content):
		'''
		Set a new welcome message.

		To insert a user mention, put {user} in your welcome message. {guild} does the same for the server name!
		'''
		
		welc = await self.get_welcome(ctx.guild.id)
		
		await welc.update(
			content=content
		).apply()
		
		await ctx.send('New welcome message set. Do `.welcome test` to test!')
		
	@welcome.command()
	async def test(self, ctx):
		'''Test the welcome message.'''
		
		await self.on_member_join(ctx.author)
		
	@welcome.command()
	async def raw(self, ctx):
		'''Get welcome message stripped of markdown.'''
		
		welc = await self.get_welcome(ctx.guild.id)
		
		await ctx.send(strip_markdown(welc.content))
		
	@welcome.command()
	async def channel(self, ctx, channel: discord.TextChannel = None):
		'''Set or print the target channel.'''
		
		welc = await self.get_welcome(ctx.guild.id)
		
		if channel is None:
			if welc.channel_id is None:
				return await ctx.send('Channel has not been set.')
			else:
				channel = ctx.guild.get_channel(welc.channel_id)
				if channel is None:
					return await ctx.send('Channel ID is invalid.')
		else:
			await welc.update(
				channel_id=channel.id
			).apply()
		
		await ctx.send(f'Channel is set to: {channel.mention} ({channel.id})')
		
	
def setup(bot):
	bot.add_cog(Welcome(bot))