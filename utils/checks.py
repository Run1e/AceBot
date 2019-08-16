import discord.utils
from discord.ext import commands

from config import OWNER_ID
from utils.guildconfig import GuildConfig


async def check_perms(ctx, perms, check=all):
	if await ctx.bot.is_owner(ctx.author):
		return True
	author_perms = ctx.channel.permissions_for(ctx.author)
	return check(getattr(author_perms, name, None) == value for name, value in perms.items())


# invoker is either bot owner or someone with manage guild permissions
async def is_mod_pred(ctx):
	# allow bot owner. this is a stupid way of doing it but it makes this function
	# also work with messages instead of contexts.
	if ctx.author.id == OWNER_ID:
		return True

	# allow guild administrators (this includes guild owner)
	if ctx.author.permissions_in(ctx.channel).administrator:
		return True

	# check against mod_role
	gc = await GuildConfig.get_guild(ctx.guild.id)

	# false if not set
	if gc.mod_role_id is None:
		return False

	# if set, see if author has this role
	return not not discord.utils.get(ctx.author.roles, id=gc.mod_role_id)


def is_mod():
	return commands.check(is_mod_pred)
