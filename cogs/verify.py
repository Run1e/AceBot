import discord, asyncio
from discord.ext import commands
from datetime import datetime

from utils.welcome import welcomify

from utils.setup_logger import config_logger
import logging
log = logging.getLogger(__name__)
log = config_logger(log)

VERIFY_GUILD	= 115993023636176902
MANAGE_ROLE 	= 311784919208558592
VERIFY_ROLE 	= 509532095731728394
MEMBER_ROLE 	= 509526426198999040
CATEGORY_ID 	= 509521577235447840
JOIN_CHANNEL 	= 509530286481080332
WELCOME_CHANNEL = 115993023636176902

JOIN_MSG = """Hello {user}!

Before you can enter our AutoHotkey Discord community, please read the <#509531951196012554>. After having done so, please tag staff by typing `@Staff`!"""

WELCOME_MSG = """Welcome to our Discord community {user}!
A collection of useful tips are in <#407666416297443328> and recent announcements can be found in <#367301754729267202>."""

VERIFY_MSG = """Hi there {user}!

For newer accounts we require at least one connected account. Go into your User Settings -> Connections and connect any type of account, then tag us again!"""

class Verify:
	'''System for verifying new users.'''
	
	def __init__(self, bot):
		self.bot = bot
		
	async def __local_check(self, ctx):
		return ctx.guild.id == VERIFY_GUILD and ctx.guild.get_role(MANAGE_ROLE) in ctx.author.roles

	async def on_member_join(self, member):
		if not member.guild.id == VERIFY_GUILD:
			return
		
		log.info(f'Adding verification channel for user {member.name} ({member.id})')
		
		guild = member.guild
		
		category = discord.utils.get(guild.categories, id=CATEGORY_ID)
		if category is None:
			log.error('Category not found')
			return
		
		welcome_channel = guild.get_channel(JOIN_CHANNEL)
		if welcome_channel is None:
			log.error('Welcome channel not found')
			return
		
		verify_role = guild.get_role(VERIFY_ROLE)
		if verify_role is None:
			log.error('Verification role not found')
			return
		
		manage_role = guild.get_role(MANAGE_ROLE)
		if manage_role is None:
			log.error('Manage role not found')
			return
		
		perms = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
		
		overwrites = {
			guild.me: perms,
			manage_role: perms,
			member: perms,
		}
		
		try:
			channel = await guild.create_text_channel(f'welcome-{member.id}', overwrites=overwrites, category=category)
		except Exception as exc:
			log.error(f'Failed creating text channel: {exc}')
			return
		
		try:
			await member.add_roles(verify_role)
		except Exception as exc:
			log.error('Failed adding verify role: {exc}')
			return
		
		now = datetime.now()
		
		age = now - member.created_at
		
		hours = age.seconds // 3600
		minutes = (age.seconds // 60) % 60
		
		topic = f"Username: {member.name}#{member.discriminator}\n" \
				f"Age: {age.days} days, {hours} hours {minutes} minutes\n" \
				f"Avatar: {'no' if member.avatar is None else 'yes'}"
		
		try:
			await channel.edit(topic=topic)
		except Exception as exc:
			log.error(f'Failed editing topic: {exc}')
		
		await asyncio.sleep(3)
		
		try:
			await channel.send(welcomify(member, member.guild, JOIN_MSG))
		except Exception as exc:
			log.error(f'Failed sending welcome message: {exc}')
			
		log.info('Verification channel setup finished')
		
	async def on_member_remove(self, member):
		if not member.guild.id == VERIFY_GUILD:
			return
		
		await self._delete_channel(member)
		
	async def _delete_channel(self, member):
		channel = discord.utils.get(member.guild.channels, name=f'welcome-{member.id}')
		if channel is None:
			return
		
		if channel.category.id == CATEGORY_ID:
			await channel.delete()
			log.info(f'Deleted channel for {member.name} ({member.id})')
		else:
			log.info(f'Failed deleting channel for {member.name} ({member.id})')
	
	@commands.command(hidden=True)
	async def approve(self, ctx):
		'''Approve user.'''
		
		member = ctx.guild.get_member(int(ctx.channel.name[8:]))
		if member is None:
			raise commands.CommandError("Couldn't find user.")
		
		if ctx.channel.category.id != CATEGORY_ID:
			raise commands.CommandError('Category does not match.')
		
		member_role = ctx.guild.get_role(MEMBER_ROLE)
		if member_role is None:
			raise commands.CommandError('Failed getting member role.')
		
		verify_role = ctx.guild.get_role(VERIFY_ROLE)
		if verify_role is None:
			raise commands.CommandError('Failed getting Verification role.')
		
		await member.add_roles(member_role)
		await member.remove_roles(verify_role)
		
		welcome_channel = ctx.guild.get_channel(WELCOME_CHANNEL)
		if welcome_channel is None:
			raise commands.CommandError('Failed getting welcome channel.')
		
		# category check and channel name check has been done. this should be safe
		await ctx.channel.delete()
		
		await asyncio.sleep(3)
		await welcome_channel.send(welcomify(member, ctx.guild, WELCOME_MSG))
		
		log.info(f'Member {member.name} ({member.id}) approved by {ctx.author.name}')
		
	@commands.command(hidden=True)
	async def reject(self, ctx):
		'''Reject user.'''
		
		member = ctx.guild.get_member(int(ctx.channel.name[8:]))
		if member is None:
			raise commands.CommandError("Couldn't find user.")
		
		category = discord.utils.get(ctx.guild.categories, id=CATEGORY_ID)
		if category is None or ctx.channel.category != category:
			raise commands.CommandError('Category does not match.')
		
		await member.kick()
		
		log.info(f'Member {member.id} rejected by {ctx.author.name}')
		
	@commands.group(hidden=True)
	async def verify(self, ctx):
		'''Send verification instructions.'''
		
		member = ctx.guild.get_member(int(ctx.channel.name[8:]))
		if member is None:
			raise commands.CommandError("Couldn't find user.")
		
		await ctx.send(welcomify(member, ctx.guild, VERIFY_MSG))
		await ctx.message.delete()

def setup(bot):
	bot.add_cog(Verify(bot))
