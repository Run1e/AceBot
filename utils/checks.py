import discord.utils
from discord.ext import commands

from config import OWNER_ID

BOT_INSTANCE = None


def set_bot(bot):
	global BOT_INSTANCE
	BOT_INSTANCE = bot


async def check_perms(ctx, perms, check=all):
	if await ctx.bot.is_owner(ctx.author):
		return True
	author_perms = ctx.channel.permissions_for(ctx.author)
	return check(getattr(author_perms, name, None) == value for name, value in perms.items())


async def is_mod_pred_meta(member, channel):
	# allow bot owner. this is a stupid way of doing it but it makes this function
	# also work with messages instead of contexts.
	if member.id == OWNER_ID:
		return True

	# allow guild administrators (this includes guild owner)
	if member.permissions_in(channel).administrator:
		return True

	gc = await BOT_INSTANCE.config.get_entry(member.guild.id)

	# false if not set
	if gc.mod_role_id is None:
		return False

	# if set, see if author has this role
	return not not discord.utils.get(member.roles, id=gc.mod_role_id)


async def is_mod_pred(ctx):
	return await is_mod_pred_meta(ctx.author, ctx.channel)


def is_mod():
	return commands.check(is_mod_pred)


async def is_mutable(member):
	return member.guild.channels and await is_mod_pred_meta(member, member.guild.channels[0])
