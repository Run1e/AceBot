import discord
from discord.ext import commands

import datetime

class Muter:
	"""Mute/unmute commands and anti-mention spam."""

	def __init__(self, bot):
		self.bot = bot

		# lifespan for the bot to listen to
		self.lifespan = 90

		# mentions per lifespan that triggers a warning
		self.max_warn = 4

		# --||-- that triggers a mute
		self.max_mute = 6

		# guilds this feature is enabled for
		self.guilds = {
			115993023636176902: {
				'channel': 423143852304760863,
				'ignore_channels': (423143852304760863,)
			}
		}

		self.counter = {}
		for guild in self.guilds:
			self.counter[guild] = {}

	async def __local_check(self, ctx):
		return ctx.guild.id in self.guilds and ctx.author.permissions_in(ctx.channel).ban_members

	async def on_message(self, message):
		# check if we even should
		if not isinstance(message.channel, discord.TextChannel) or message.guild.id not in self.guilds:
			return

		if message.channel.id in self.guilds[message.guild.id]['ignore_channels'] or self.bot.is_owner(message.author):
			return

		if len(message.mentions):
			now = datetime.datetime.now()

			if message.author.id not in self.counter[message.guild.id]:
				self.counter[message.guild.id][message.author.id] = []

			for mention in message.mentions:
				self.counter[message.guild.id][message.author.id].append(now)

			total = 0
			for time in self.counter[message.guild.id][message.author.id]:
				delta = (now - time).total_seconds()
				if delta > self.lifespan:
					self.counter[message.guild.id][message.author.id].remove(time)
					continue
				total += 1

			if total >= self.max_mute:
				ctx = await self.bot.get_context(message)
				await ctx.invoke(self.mute, member=message.author, reason='Auto-mute because of mention abuse.') #<@&311784919208558592>
				self.counter[message.guild.id][message.author.id] = []

			elif total >= self.max_warn:
				await message.channel.send(f"{message.author.mention} Please refrain from using so many mentions, continuing might warrant a server-wide mute.")

	@commands.command(hidden=True)
	async def mute(self, ctx, member: discord.Member, reason: str = None):
		role = discord.utils.get(ctx.guild.roles, name='Muted')
		if role is None:
			return
		await member.add_roles(role)
		serv = self.guilds[ctx.guild.id]
		message = f"{member.mention} muted.{'' if reason is None else ' Reason: ' + reason}"
		if serv['channel'] is None:
			await ctx.send(message)
		else:
			await self.bot.get_channel(self.guilds[ctx.guild.id]['channel']).send(message)

	@commands.command(hidden=True)
	async def unmute(self, ctx, member: discord.Member):
		role = discord.utils.get(ctx.guild.roles, name='Muted')
		if role is None:
			return
		await member.remove_roles(role)
		await ctx.send(f"{member.mention} unmuted.")

def setup(bot):
	bot.add_cog(Muter(bot))