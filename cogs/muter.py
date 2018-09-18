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
		self.guilds = (115993023636176902, 367975590143459328,)

		self.counter = {}
		for guild in self.guilds:
			self.counter[guild] = {}

	async def __local_check(self, ctx):
		return ctx.guild.id in self.guilds and ctx.author.permissions_in(ctx.channel).kick_members

	async def on_message(self, message):

		if not isinstance(message.channel, discord.TextChannel) or message.guild.id not in self.guilds or message.author.bot or message.author.permissions_in(message.channel).ban_members:
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
				await ctx.invoke(self.mute, member=message.author)
				self.counter[message.guild.id][message.author.id] = []

			elif total >= self.max_warn:
				await message.channel.send(f'{message.author.mention} Please refrain from abusing mentions, continuing might warrant a server-wide mute.')

	@commands.command(hidden=True)
	async def mute(self, ctx, member: discord.Member):

		# find muted role and add it to user
		role = discord.utils.get(ctx.guild.roles, name='Muted')

		if role is None:
			return await ctx.send('Unable to find `Muted` role.')

		if role in member.roles:
			return await ctx.send('User already muted.')

		try:
			await member.add_roles(role, reason=f'User muted by {ctx.author.name}')
		except Exception as exc:
			await ctx.send('Unable to add role.')
			raise exc

		msg = await ctx.send(f'{member.mention} muted.')

		category = discord.utils.get(ctx.guild.categories, name='Muted')

		if category is None:
			return await msg.edit(content=f'{msg.content} However: `Muted` category not found.')

		try:
			channel = await ctx.guild.create_text_channel(f'muted-{member.id}', category=category)
		except Exception as exc:
			await msg.edit(content=f'{msg.content} However: Failed creating channel.')
			raise exc

		try:
			await channel.set_permissions(member, read_messages=True)
		except Exception as exc:
			await msg.edit(content=f'{msg.content} However: Failed setting permissions of channel.')
			raise exc

		if ctx.author == member:
			muted_by = ctx.guild.owner
		else:
			muted_by = ctx.author

		await channel.send(f'{member.mention}, you have been muted by {muted_by.mention}. You will not be able to access the rest of the server until unmuted.')


	@commands.command(hidden=True)
	async def unmute(self, ctx, member: discord.Member):

		role = discord.utils.get(ctx.guild.roles, name='Muted')

		if role is None:
			return await ctx.send('Unable to find `Muted` role.')

		if role not in member.roles:
			return await ctx.send('User not muted.')

		try:
			await member.remove_roles(role, reason=f'User unmuted by {ctx.author.name}')
		except Exception as exc:
			await ctx.send('Unable to remove role.')
			raise exc

		channel = discord.utils.get(ctx.guild.channels, name=f'muted-{member.id}')

		if channel is not None:
			category = discord.utils.get(ctx.guild.categories, id=channel.category_id)
			if category.name == 'Muted':
				await channel.delete()
			else:
				await channel.send(f"Name of channels category is `{category.name}` and not `Muted`, delete channel manually!")

		if ctx.channel.id != channel.id:
			await ctx.send(f'{member.mention} unmuted.')


def setup(bot):
	bot.add_cog(Muter(bot))
