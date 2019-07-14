import discord
from discord.ext import commands

from datetime import datetime, timedelta

from utils.fakectx import FakeContext
from utils.guildconfig import GuildConfig
from cogs.mixins import AceMixin

STAR_EMOJI = '\N{WHITE MEDIUM STAR}'
STAR_TTL = timedelta(days=7)
STAR_LIMIT = 4 # total of 5 stars needed to survive a week


class StarContext:
	def __init__(self, starrer, message=None, star_message=None, record=None):
		self.starrer = starrer
		self.record = record

		self._message = message
		self._star_message = star_message


	async def get_message(self):
		if self._message is not None:
			return self._message

		not_found_error = commands.CommandError('Could not find original message.')

		if self.record is None:
			raise not_found_error

		channel = self._star_message.guild.get_channel(self.record.get('channel_id'))
		if channel is None:
			raise commands.CommandError('Could not find channel original message was posted in.')

		try:
			message = await channel.fetch_message(self.record.get('message_id'))
		except discord.HTTPException:
			raise not_found_error

		self._message = message
		return message

	async def get_star_message(self):
		if self.record is None:
			return None

		message = await self.star_channel.fetch_message(self.record.get('star_message_id'))
		return message

	async def get_author(self):
		if self._message is None:
			await self.get_message()
		return self._message.author


class StarConverter(commands.Converter):
	async def convert(self, ctx, argument):
		pass

class Stars(AceMixin, commands.Cog):
	'''Classic Starboard.'''

	SB_NOT_SET_ERROR = commands.CommandError('No starboard channel has been set yet.')
	SB_NOT_FOUND_ERROR = commands.CommandError('Starboard channel previously set but not found, please set it again.')

	@commands.group(name='star', invoke_without_command=True)
	async def _star(self, ctx):
		'''Star and vote on messages.'''

		await ctx.invoke(self.bot.get_command('help'), command='Star')

	@_star.command()
	async def channel(self, ctx, channel: discord.TextChannel = None):
		'''Set the starboard channel. Remember only the bot should be allowed to send messages in this channel!'''

		gc = await GuildConfig.get_guild(ctx.guild.id)

		if channel is None:
			channel_id = gc.star_channel_id
			if channel_id is None:
				raise self.SB_NOT_SET_ERROR

			channel = ctx.guild.get_channel(channel_id)
			if channel is None:
				raise self.SB_NOT_FOUND_ERROR

		else:
			await gc.set('star_channel_id', channel.id)

		await ctx.send(f'Starboard channel set to {channel.mention}')

	@_star.command(aliases=['threshold'])
	async def limit(self, ctx, limit: int = None):
		'''Set the minimum amount of stars needed for a starred message to remain on the starboard after a week has passed'''

		gc = await GuildConfig.get_guild(ctx.guild.id)

		if limit is None:
			limit = gc.star_limit or STAR_LIMIT
		else:
			await gc.set('star_limit', limit)

		await ctx.send(f'Starboard star limit set to `{limit}`')

	async def _on_star(self, ctx):
		if ctx.record:

			# original starrer can't restar
			if ctx.starrer.id == ctx.record.get('starrer_id'):
				return

			# star message author can't star
			if ctx.starrer.id == ctx.record.get('user_id'):
				return

			# can't restar if already starred
			if await self.db.fetchval('SELECT user_id FROM starrers WHERE star_id=$1 AND user_id=$2',
				ctx.record.get('id'), ctx.starrer.id):
				return

			# insert into starrers table
			await self.db.execute(
				'INSERT INTO starrers (star_id, user_id) VALUES ($1, $2)',
				ctx.record.get('id'), ctx.starrer.id
			)

			# and update the starred message
			starrer_count = await self.db.fetchval(
				'SELECT COUNT(*) FROM starrers WHERE star_id=$1',
				ctx.record.get('id')
			)

			# and update message + db
			await self.update_star_count(ctx, starrer_count + 1)

		else:
			# new star. post it and store it

			# can technically return None though not here, hopefully
			message = await ctx.get_message()

			if message.author == ctx.starrer:
				raise commands.CommandError('You can\'t star your own message.')

			# TODO: make sure this line works
			if message.channel.is_nsfw() and not ctx.star_channel.is_nsfw():
				raise commands.CommandError('Can\'t star message from nsfw channel into non-nsfw starboard.')

			try:
				star_message = await ctx.star_channel.send(self.get_header(1), embed=self.get_embed(message, 1))
			except discord.HTTPException:
				raise commands.CommandError('Failed posting to starboard.\nMake sure the bot has permissions to post there.')

			# TODO: clean this one up
			await self.db.execute(
				'''
				INSERT INTO starmessage
				(guild_id, channel_id, user_id, message_id, star_message_id, starred_at, starrer_id)
				VALUES ($1, $2, $3, $4, $5, $6, $7)
				''',
				message.guild.id, message.channel.id, message.author.id, message.id, star_message.id,
				datetime.utcnow(), ctx.starrer.id
			)

			await star_message.add_reaction(STAR_EMOJI)

	async def _on_unstar(self, ctx):
		if ctx.record:
			result = await self.db.execute(
				'DELETE FROM starrers WHERE star_id=$1 AND user_id=$2',
				ctx.record.get('id'), ctx.starrer.id
			)

			# if nothing was deleted, the star message doesn't need to be updated
			if result == 'DELETE 0':
				return

			starrer_count = await self.db.fetchval(
				'SELECT COUNT(*) FROM starrers WHERE star_id=$1',
				ctx.record.get('id')
			)

			# and update message + db
			await self.update_star_count(ctx, starrer_count + 1)

		else:
			pass # ???

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

		# run checks
		fake_ctx = FakeContext(guild=channel.guild, author=starrer)

		if not await self.bot.blacklist(fake_ctx):
			return

		message = await channel.fetch_message(payload.message_id)
		if message is None:
			return

		# craft StarContext
		sm = await self.db.fetchrow('SELECT * FROM starmessage WHERE message_id=$1 OR star_message_id=$1', message.id)

		try:
			if sm is None:
				# new star... make sure it's not attempting to star a bot message
				if message.author.bot:
					raise commands.CommandError('Can\'t star bot messages.')
				ctx = StarContext(starrer, message=message)
			else:
				if message.id == sm.get('message_id'):
					ctx = StarContext(starrer, message=message, record=sm)
				else:
					ctx = StarContext(starrer, star_message=message, record=sm)


			# insert star_channel
			gc = GuildConfig.get_guild(payload.guild_id)
			star_channel_id = gc.star_channel_id
			if star_channel_id is None:
				raise self.SB_NOT_SET_ERROR

			star_channel = message.guild.get_channel(star_channel_id)
			if star_channel is None:
				raise self.SB_NOT_FOUND_ERROR

			ctx.star_channel = star_channel

			await event(ctx)
		except commands.CommandError as exc:
			await channel.send(embed=discord.Embed(description=str(exc)), delete_after=10)


	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):
		await self._on_star_event(payload, self._on_star)

	@commands.Cog.listener()
	async def on_raw_reaction_remove(self, payload):
		await self._on_star_event(payload, self._on_unstar)

	@commands.Cog.listener()
	async def on_raw_message_delete(self, payload):
		sm = await self.db.fetchrow(
			'SELECT * FROM starmessage WHERE message_id=$1 OR star_message_id=$1',
			payload.message_id
		)

		if sm is None:
			return

		# delete from db
		await self.db.execute('DELETE FROM starmessage WHERE id=$1', sm.get('id'))

		if payload.message_id == sm.get('star_message_id'):
			return

		# original message was deleted, attempt to delete the starred message

		guild = self.bot.get_guild(payload.guild_id)
		if guild is None:
			return

		gc = GuildConfig.get_guild(guild.id)
		star_channel_id = gc.star_channel_id
		if star_channel_id is None:
			return

		star_channel = guild.get_channel(star_channel_id)
		if star_channel is None:
			return

		try:
			star_message = await star_channel.fetch_message(sm.get('star_message_id'))
		except discord.HTTPException:
			return

		await star_message.delete()

	@commands.Cog.listener()
	async def on_raw_bulk_message_delete(self, payload):
		# TODO: finish this

		sms = await self.db.fetch(
			'SELECT * FROM starmessage WHERE message_id=ANY($1::bigint[]) OR star_message_id=ANY($1::bigint[])',
			list(payload.message_id)
		)

		if len(sms) == 0:
			return

		ids = list(sm.get('id') for sm in sms)

		print(ids)

		# delete from db
		await self.db.execute('DELETE FROM starmessage WHERE id=ANY($1::integer[])', )

		guild = self.bot.get_guild(payload.guild_id)
		if guild is None:
			return

		gc = GuildConfig.get_guild(payload.guild_id)
		star_channel_id = gc.star_channel_id
		if star_channel_id is None:
			return

		# if the deleted messages were in the starboard channel there's no need
		# to go on trying to delete them
		if star_channel_id == payload.channel_id:
			return

		star_channel = guild.get_channel(star_channel_id)
		if star_channel is None:
			return

		to_delete = []

		async for sm in sms:
			try:
				message = await star_channel.fetch_message(sm.get('star_message_id'))
			except discord.HTTPException:
				continue

			to_delete.append(message)

		try:
			await star_channel.delete_messages(to_delete)
		except discord.HTTPException:
			pass

	async def update_star_count(self, ctx, stars):
		try:
			star_message = await ctx.get_star_message()
		except discord.HTTPException:
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