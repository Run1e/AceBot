import discord
from discord.ext import commands

from datetime import datetime, timedelta

from utils.fakectx import FakeContext
from cogs.mixins import AceMixin, ToggleMixin

STAR_EMOJI = '\N{WHITE MEDIUM STAR}'
STAR_TTL = timedelta(days=7)
STAR_MINIMUM = 4 # total of 5 stars needed to survive a week


class StarContext:
	def __init__(self, parent, payload, starrer, message=None, star_message=None, record=None):
		self.parent = parent
		self.payload = payload
		self.starrer = starrer
		self.record = record

		self._message = message
		self._star_message = star_message

		if star_message is not None:
			self._star_channel = star_message.channel

	async def get_message(self):
		if self._message is not None:
			return self._message
		elif self._message is None and self.record is None:
			return None
		elif self.record is not None:
			channel = self._star_message.guild.get_channel(self.record.get('channel_id'))
			if channel is None:
				return None

			message = await channel.fetch_message(self.record.get('message_id'))
			self._message = message

			return message

	async def get_star_channel(self):
		if self._star_channel is not None:
			return self._star_channel

		guild = (self._message or self._star_message).guild

		channel_id = await self.parent.db.fetchval(
			'SELECT channel_id FROM starconfig WHERE guild_id=$1',
			guild.id
		)

		if channel_id is None:
			raise commands.CommandError('No starboard channel set up. See `.help star`')

		channel = guild.get_channel(channel_id)
		if channel is None:
			raise commands.CommandError(f'Starboard channel set but not found.\nChannel ID: `{channel_id}`')

		self._star_channel = channel
		return channel

	async def get_star_message(self):
		if self.record is None:
			return None

		try:
			star_channel = await self.get_star_channel()
		except discord.DiscordException:
			return None

		return await star_channel.fetch_message(self.record.get('star_message_id'))


	async def get_author(self):
		if self._message is None:
			await self.get_message()
		return self._message.author


class StarConverter(commands.Converter):
	async def convert(self, ctx, argument):
		pass

class Stars(AceMixin, ToggleMixin, commands.Cog):


	@commands.group(name='star', invoke_without_command=True)
	async def _star(self, ctx):
		'''Star and vote on messages.'''

		await ctx.invoke(self.bot.get_command('help'), command='Star')

	@_star.command()
	async def channel(self, ctx, channel: discord.TextChannel = None):
		if channel is None:
			# echo back currently set starboard channel

			pass

	async def _on_unstar(self, ctx):
		if ctx.record:
			# if starrer is trying to unstar or unstarrer somehow hasn't starred before, do nothing
			if ctx.starrer.id == ctx.record.get('starrer_id') or ctx.starrer.id not in ctx.record.get('starrers'):
				return

			# remove unstarrer from the starrers list
			starrers = list(ctx.record.get('starrers'))
			starrers.remove(ctx.starrer.id)

			# and update message + db
			await self.update_star_count(ctx, len(starrers) + 1)
			await self.db.execute('UPDATE starmessage SET starrers=$1 WHERE id=$2', starrers, ctx.record.get('id'))

		else:
			pass # ???

	async def _on_star(self, ctx):
		if ctx.record:
			# person who has already starred can't re-star.
			if ctx.starrer.id == ctx.record.get('starrer_id') or ctx.starrer.id in ctx.record.get('starrers'):
				return

			# add starrer to the starrers list
			starrers = list(ctx.record.get('starrers'))
			starrers.append(ctx.starrer.id)

			# and update message + db
			await self.update_star_count(ctx, len(starrers) + 1)
			await self.db.execute('UPDATE starmessage SET starrers=$1 WHERE id=$2', starrers, ctx.record.get('id'))

		else:

			# new star. post it and store it
			message = await ctx.get_message() # can technically return None though not here
			star_channel = await ctx.get_star_channel()

			try:
				star_message = await star_channel.send(self.get_header(1), embed=self.get_embed(message, 1))
			except discord.HTTPException:
				raise commands.CommandError('Failed posting to starboard.\nMake sure the bot has permissions to post there.')

			await self.db.execute(
				'''
				INSERT INTO starmessage
				(guild_id, channel_id, author_id, message_id, star_message_id, starred_at, starrer_id, starrers)
				VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
				''',
				message.guild.id, message.channel.id, message.author.id, message.id, star_message.id,
				datetime.utcnow(), ctx.starrer.id, list()
			)

			await star_message.add_reaction(STAR_EMOJI)


	async def _on_star_event(self, payload, event):
		# only listen for star emojis
		if str(payload.emoji) != STAR_EMOJI:
			return

		# attempt to get the message
		channel = self.bot.get_channel(payload.channel_id)
		if channel is None:
			return

		starrer = channel.guild.get_member(payload.user_id)
		if starrer is None or starrer.bot:
			return

		message = await channel.fetch_message(payload.message_id)
		if message is None:
			return

		fake_ctx = FakeContext(guild=channel.guild, author=starrer)

		# run checks
		if not await self.cog_check(fake_ctx):
			return

		if not await self.bot.blacklist(fake_ctx):
			return

		# craft StarContext
		sm = await self.db.fetchrow('SELECT * FROM starmessage WHERE message_id=$1 OR star_message_id=$1', message.id)

		if sm is None:
			if message.author.bot:
				raise commands.CommandError('Can\'t star bot messages.')
			ctx = StarContext(self, payload, starrer, message=message)
		else:
			if message.id == sm.get('message_id'):
				# get star_message first
				ctx = StarContext(self, payload, starrer, star_message=message, record=sm)
			else:
				ctx = StarContext(self, payload, starrer, message=message, record=sm)

		# if successful run the event with the message and starrer id
		try:
			await event(ctx)
		except Exception as exc:
			print(exc)

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):
		await self._on_star_event(payload, self._on_star)

	@commands.Cog.listener()
	async def on_raw_reaction_remove(self, payload):
		await self._on_star_event(payload, self._on_unstar)

	async def update_star_count(self, ctx, stars):
		star_message = await ctx.get_star_message()
		if star_message is None:
			raise commands.CommandError('Failed updating starboard message.')

		embed = star_message.embeds[0]
		embed.colour = self.star_gradient_colour(stars)
		await star_message.edit(content=self.get_header(stars), embed=embed)

	def get_header(self, stars):
		return f'{self.star_emoji(stars)} **{stars}**'

	def get_embed(self, message, stars):
		'''
		Stolen from Rapptz with minor tweaks, thanks!
		https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stars.py#L168-L193
		'''

		embed = discord.Embed(description=message.content)

		if message.embeds:
			data = message.embeds[0]
			if data.type == 'image':
				embed.set_image(url=data.url)

		if message.attachments:
			file = message.attachments[0]
			if file.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
				embed.set_image(url=file.url)
			else:
				embed.add_field(name='Attachment', value=f'[{file.filename}]({file.url})', inline=False)

		embed.set_author(
			name=message.author.display_name,
			icon_url=message.author.avatar_url_as(format='png'),
			url=f'https://discordapp.com/channels/{message.guild.id}/{message.channel.id}/{message.id}'
		)

		embed.set_footer(text=f'ID: {message.id}')
		embed.timestamp = message.created_at
		embed.colour = self.star_gradient_colour(stars)
		return embed

	def star_emoji(self, stars):
		if stars >= 14:
			return '\N{SPARKLES}'
		elif stars >= 8:
			return '\N{DIZZY SYMBOL}'
		elif stars >= 5:
			return '\N{GLOWING STAR}'
		else:
			return '\N{WHITE MEDIUM STAR}'

	def star_gradient_colour(self, stars):
		'''
		Stolen from Rapptz, thanks!
		https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stars.py#L151-L166
		'''

		p = stars / 13
		if p > 1.0:
			p = 1.0

		red = 255
		green = int((194 * p) + (253 * (1 - p)))
		blue = int((12 * p) + (247 * (1 - p)))
		return (red << 16) + (green << 8) + blue


def setup(bot):
	bot.add_cog(Stars(bot))