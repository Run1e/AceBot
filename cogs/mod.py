import discord
from discord.ext import commands

from cogs.base import TogglableCogMixin


class Moderator(TogglableCogMixin):
	'''Commands accessible to members with Ban Members permissions.'''
	
	async def __local_check(self, ctx):
		return await self._is_used(ctx) and ctx.author.permissions_in(ctx.channel).ban_members
	
	@commands.command()
	async def info(self, ctx, user: discord.User = None):
		'''Display information about user or self.'''
		
		if user is None:
			user = ctx.author
		
		await ctx.send(user)
	
	@commands.command()
	@commands.bot_has_permissions(manage_messages=True)
	async def clear(self, ctx, message_count: int = None, user: discord.User = None):
		'''Clear messages, either from user or indiscriminately.'''
		
		if message_count is None:
			return await ctx.send('Please choose a message count.')
		
		if message_count > 100:
			return await ctx.send('Please choose a message count below 100.')
		
		if user is not None:
			check = lambda msg: msg.author == user
		else:
			check = None
		
		await ctx.message.delete()
		deleted = await ctx.channel.purge(limit=message_count, check=check)
		
		await ctx.send(f'\U0000274C Deleted {len(deleted)} messages.', delete_after=5)


def setup(bot):
	bot.add_cog(Moderator(bot))
