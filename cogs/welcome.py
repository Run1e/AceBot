import discord
from discord.ext import commands
from peewee import *

from cogs.utils.strip_markdown import *

db = SqliteDatabase('lib/welcome.db')

class Welcome:
	def __init__(self, bot):
		self.bot = bot

	async def __local_check(self, ctx):
		return ctx.author.permissions_in(ctx.channel).manage_guild or await self.bot.is_owner(ctx.author)

	async def on_member_join(self, member):
		wel_msg = self.get_msg(member.guild.id)
		if wel_msg is None or wel_msg.content is None or wel_msg.channel is None or wel_msg.disabled:
			return

		channel = self.bot.get_channel(wel_msg.channel)
		if channel is None:
			return

		await channel.send(self.format_welcome(member, wel_msg.content))

	def get_msg(self, guild_id):
		try:
			wel_msg = WelcomeMsg.get(guild=guild_id)
			return wel_msg
		except WelcomeMsg.DoesNotExist:
			return None

	async def not_found(self, ctx):
		await ctx.send('You do not have a welcome message set up.')

	def format_welcome(self, member, msg):
		repl = {
			'{user}': member.mention,
			'{guild}': member.guild.name
		}

		for k, v in repl.items():
			msg = msg.replace(k, v)

		return msg

	@commands.group(hidden=True)
	async def welcome(self, ctx):
		pass

	@welcome.group()
	async def enable(self, ctx):
		"""Enable welcome messages."""

		wel_msg, created = WelcomeMsg.get_or_create(guild=ctx.guild.id)

		if not created:
			if wel_msg.disabled:
				wel_msg.disabled = False
				wel_msg.save()

		await ctx.send('Welcome messages enabled.\nUse `.welcome msg <contents>` to set welcome message contents.\nUse `.welcome channel <channel>` to set welcome message channel.')

	@welcome.group()
	async def disable(self, ctx):
		"""Disable welcome messages."""

		try:
			wel_msg = WelcomeMsg.get(guild=ctx.guild.id)
			wel_msg.disabled = True
			wel_msg.save()
			await ctx.send('Welcome messages disabled.')
		except WelcomeMsg.DoesNotExist:
			pass

	@welcome.group()
	async def msg(self, ctx, *, msg: str):
		"""
		Set the welcome message content.

		Shorthands:
		{mention} - mentions the connected user
		{guild} - guild name
		"""

		wel_msg = self.get_msg(ctx.guild.id)
		if wel_msg is None:
			return await self.not_found(ctx)

		wel_msg.content = msg
		wel_msg.save()

		await ctx.send('Welcome message set. Do `.welcome test` to test it.')

	@welcome.group()
	async def channel(self, ctx, *, channel: discord.TextChannel):
		"""Set the channel for welcomes messages to be sent in."""

		wel_msg = self.get_msg(ctx.guild.id)
		if wel_msg is None:
			return await self.not_found(ctx)

		if channel.guild.id != ctx.guild.id:
			return await ctx.send('Invalid channel.')

		wel_msg.channel = channel.id
		wel_msg.save()

		await ctx.send('Welcome messages will be sent in ' + channel.mention)

	@welcome.group()
	async def test(self, ctx):
		"""Test your current welcome message."""

		wel_msg = self.get_msg(ctx.guild.id)
		if wel_msg is None:
			return await self.not_found(ctx)

		if wel_msg.content is None:
			return await ctx.send('No welcome message set yet.')

		test = self.format_welcome(ctx.author, wel_msg.content)

		if wel_msg.channel is None:
			test += '\n\n*Please notice welcome message channel is not set yet.*'

		if wel_msg.disabled:
			test += '\n\n*Please notice welcome messages are disabled.*'

		await ctx.send(test)

	@welcome.group()
	async def raw(self, ctx):
		"""Get raw contents of your welcome message."""

		wel_msg = self.get_msg(ctx.guild.id)
		if wel_msg is None:
			return await self.not_found(ctx)

		await ctx.send(strip_markdown(wel_msg.content))


class WelcomeMsg(Model):
	guild = BigIntegerField(primary_key=True)
	channel = BigIntegerField(null=True)
	content = TextField(null=True)
	disabled = BooleanField(default=False)

	class Meta:
		database = db

def setup(bot):
	db.connect()
	db.create_tables([WelcomeMsg], safe=True)
	bot.add_cog(Welcome(bot))