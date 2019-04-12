import discord, logging

from discord.ext import commands
from datetime import datetime
from os.path import isfile

from utils.checks import is_manager
from utils.database import db, LogGuild
from utils.lol import bot_deleted

log = logging.getLogger(__name__)

CHANNEL_TYPES = {discord.TextChannel: 'Text', discord.VoiceChannel: 'Voice', discord.CategoryChannel: 'Category'}

LO_COLOR = discord.Embed().color
MID_COLOR = 0xFF8C00
HI_COLOR  = 0xFF4000

def present(string):
	return string.replace('_', ' ').title()


class Logger:
	'''Log interesting events like message deletion.'''

	def __init__(self, bot):
		self.bot = bot

	async def __local_check(self, ctx):
		return await self._check(ctx.guild.id)

	async def _check(self, guild_id):
		return await self.bot.uses_module(guild_id, 'logger')

	def get_message_embed(self, message):
		'''
		Stolen from Rapptz with minor tweaks, thanks!
		https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stars.py#L168-L193
		'''

		embed = discord.Embed(description=message.content)

		if message.embeds:
			data = message.embeds[0]
			if data.type == 'image':
				embed.set_image(url=data.url)

		img = None
		if message.attachments:
			file = message.attachments[0]
			if file.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
				fn = f'images/{str(message.guild.id)}_{str(message.author.id)}_{str(message.id)}_{file.filename}'
				if isfile(fn):
					img = discord.File(open(fn, 'rb'))
				else:
					embed.set_image(url=file.url)
			else:
				embed.add_field(name='Attachment', value=f'[{file.filename}]({file.url})', inline=False)

		embed.set_author(
			name=message.author.display_name,
			icon_url=message.author.avatar_url_as(format='png'),
		)

		embed.set_footer(text=f'ID: {message.id}')
		embed.timestamp = message.created_at

		return embed, img

	def find_changes(self, before, after):

		def formt(b, a):
			if hasattr(a, 'mention'):
				return a.mention
			elif hasattr(a, 'name'):
				return a.name
			elif isinstance(a, bool):
				return 'yes' if a else 'no'
			elif isinstance(a, (int, float)):
				return f'`{str(b)}` -> `{str(a)}`'
			elif isinstance(a, str):
				if b is None or b == '':
					return f'```\n{a}````'
				else:
					return f'```\n{b}```changed to```\n{a}```'
			else:
				return None

		changed = {}

		for attr in dir(before):
			if attr.startswith('_'):
				continue
			b, a = getattr(before, attr), getattr(after, attr)
			if b != a:
				res = formt(b, a)
				if res is None:
					continue
				changed[attr] = res

		return changed

	async def log(self, guild, content=None, embed=None, is_msg=False, **kwargs):
		if isinstance(guild, discord.Guild):
			guild = guild.id

		if is_msg:
			channel_id = await db.scalar('SELECT msg_chan_id FROM logguild WHERE guild_id=$1', guild)
		else:
			channel_id = await db.scalar('SELECT other_chan_id FROM logguild WHERE guild_id=$1', guild)

		channel = self.bot.get_channel(channel_id)
		if channel is None:
			log.warning('Failed finding log channel for logger')
			return

		try:
			await channel.send(content=content, embed=embed, **kwargs)
		except discord.HTTPException as exc:
			log.warning(f'Failed to post in logger: {exc}')

	async def on_guild_channel_create(self, channel):
		if not await self._check(channel.guild.id):
			return

		e = discord.Embed(
			title=f'{CHANNEL_TYPES[type(channel)]} channel created',
			description=f'{channel.mention}'
		)

		e.set_footer(text=f'ID: {channel.id}')
		e.timestamp = datetime.utcnow()
		e.color = MID_COLOR

		await self.log(
			guild=channel.guild,
			embed=e
		)

	async def on_guild_channel_delete(self, channel):
		if not await self._check(channel.guild.id):
			return

		e = discord.Embed(
			title=f'{CHANNEL_TYPES[type(channel)]} channel deleted',
			description=f'#{channel.name}'
		)

		e.set_footer(text=f'ID: {channel.id}')
		e.timestamp = datetime.utcnow()
		e.color = MID_COLOR

		await self.log(
			guild=channel.guild,
			embed=e
		)

	async def on_guild_channel_update(self, before, after):
		if not await self._check(before.guild.id):
			return

		changed = self.find_changes(before, after)

		for attr in list(changed.keys()):
			if attr in ('position',):
				changed.pop(attr)

		if not len(changed):
			return

		e = discord.Embed(
			title='Channel edited',
			description=before.mention
		)

		for attr, res in changed.items():
			e.add_field(
				name=present(attr),
				value=res,
				inline=False
			)

		e.set_footer(text=f'ID: {before.id}')
		e.timestamp = datetime.utcnow()
		e.color = MID_COLOR

		await self.log(
			guild=before.guild,
			embed=e
		)

	async def on_guild_update(self, before, after):
		if not await self._check(before.id):
			return

		changed = self.find_changes(before, after)

		if not len(changed):
			return

		e = discord.Embed(
			title='Guild edited'
		)

		for attr, res in changed.items():
			e.add_field(
				name=present(attr),
				value=res,
				inline=False
			)

		e.set_author(name=after.name, icon_url=after.icon_url)
		e.set_footer(text=f'ID: {before.id}')
		e.timestamp = datetime.utcnow()
		e.color = MID_COLOR

		await self.log(
			guild=after,
			embed=e
		)

	async def on_message_edit(self, before, after):
		if before.author.bot or before.content == after.content:
			return

		if not await self._check(before.guild.id):
			return

		split = False

		if len(before.content) > 1024 or len(after.content) > 1024:
			split = True
			e, img = self.get_message_embed(before)
			new_e, img = self.get_message_embed(after)
			e.title = 'Old message'
			new_e.title = 'New message'
		else:
			e, img = self.get_message_embed(before)
			e.description = None
			e.add_field(name='Old message', value=before.content, inline=False)
			e.add_field(name='New message', value=after.content, inline=False)

		await self.log(
			guild=after.guild,
			content=f'Message edited in {after.channel.mention} (Author ID: {after.author.id})',
			embed=e,
			is_msg=True
		)

		if split:
			await self.log(guild=after.guild, embed=new_e, is_msg=True)

	async def on_message_delete(self, message):
		if message.author.bot or message.channel.id in (509530286481080332, 378602386404409344):
			return

		if not await self._check(message.guild.id):
			return

		if bot_deleted(message.id):  # STUPID STUPID STUPID STUPID STUPIDDDDD
			return

		embed, img = self.get_message_embed(message)
		embed.color = HI_COLOR

		await self.log(
			guild=message.guild,
			content=f'Message deleted in {message.channel.mention} (Author ID: {message.author.id})',
			embed=embed,
			file=img,
			is_msg=True
		)

	async def on_message(self, message):
		if message.author.bot:
			return

		# only store images from the autohotkey guild
		# TODO: delete images after 24hrs, cronjob mby?
		if not await self._check(message.guild.id):
			return

		for attach in message.attachments:
			if hasattr(attach, 'height'):
				await attach.save(open(f'images/{str(message.guild.id)}_{str(message.author.id)}_{str(message.id)}_{attach.filename}', 'wb'))

	async def on_member_join(self, member):
		if not await self._check(member.guild.id):
			return

		e = discord.Embed(
			title='Member joined'
		)

		e.set_author(name=member.name, icon_url=member.avatar_url)
		e.timestamp = datetime.utcnow()
		e.set_footer(text=f'ID: {member.id}')
		e.color = MID_COLOR

		await self.log(guild=member.guild, embed=e)

	async def on_member_remove(self, member):
		if not await self._check(member.guild.id):
			return

		e = discord.Embed(
			title='Member left'
		)

		e.set_author(name=member.name, icon_url=member.avatar_url)
		e.timestamp = datetime.utcnow()
		e.set_footer(text=f'ID: {member.id}')
		e.color = MID_COLOR

		await self.log(guild=member.guild, embed=e)

	async def on_voice_state_update(self, member, before, after):
		if not await self._check(member.guild.id):
			return

		changed = self.find_changes(before, after)

		if not len(changed):
			return

		if 'self_mute' in changed or 'self_deaf' in changed:
			return

		e = discord.Embed(
			title='Member voice state update'
		)

		e.set_author(name=member.name, icon_url=member.avatar_url)
		e.timestamp = datetime.utcnow()
		e.set_footer(text=f'ID: {member.id}')

		# change color to red if moderator action
		if 'mute' in changed or 'deaf' in changed:
			e.color = HI_COLOR

		for attr, res in changed.items():
			e.add_field(name=present(attr), value=res)

		await self.log(guild=member.guild, embed=e)

	async def on_member_ban(self, guild, user):
		if not await self._check(guild.id):
			return

		e = discord.Embed(
			title='Member banned'
		)

		e.set_author(name=user.name, icon_url=user.avatar_url)
		e.timestamp = datetime.utcnow()
		e.set_footer(text=f'ID: {user.id}')
		e.color = HI_COLOR

		await self.log(guild=guild, embed=e)

	async def on_member_unban(self, guild, user):
		if not await self._check(guild.id):
			return

		e = discord.Embed(
			title='Member unbanned'
		)

		e.set_author(name=user.name, icon_url=user.avatar_url)
		e.set_footer(text=f'ID: {user.id}')

		e.timestamp = datetime.utcnow()
		e.color = HI_COLOR

		await self.log(guild=guild, embed=e)

	@commands.group(name='log', hidden=True, invoke_without_command=True)
	async def _log(self, ctx):
		pass

	@_log.command()
	@is_manager()
	async def channel(self, ctx, channel: discord.TextChannel = None):
		'''
		Set the starboard channel.

		Remember only the bot should be allowed to send messages in this channel!
		'''

		async def announce():
			await ctx.send(f'Log channel set to {channel.mention}')

		lg = await LogGuild.query.where(LogGuild.guild_id == ctx.guild.id).gino.first()

		if channel is None:
			if lg is None:
				await ctx.send('No log channel set.')
			else:
				channel = self.bot.get_channel(lg.channel_id)
				if channel is None:
					await ctx.send('Log channel is set, but I didn\'t manage to find the channel.')
				else:
					await announce()
		else:
			if lg is None:
				await LogGuild.create(
					guild_id=ctx.guild.id,
					channel_id=channel.id
				)
			else:
				await lg.update(channel_id=channel.id).apply()

			await announce()


def setup(bot):
	bot.add_cog(Logger(bot))
