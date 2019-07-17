import discord.utils
from discord.ext import commands

from utils.guildconfig import GuildConfig

async def check_perms(ctx, perms, check=all):
	if await ctx.bot.is_owner(ctx.author):
		return True
	author_perms = ctx.channel.permissions_for(ctx.author)
	return check(getattr(author_perms, name, None) == value for name, value in perms.items())


# invoker is either bot owner or someone with manage guild permissions
async def is_mod_pred(ctx):
	# allow guild owner
	if ctx.guild.owner == ctx.author:
		return True

	# TODO: allow administrators

	# allow bot owner
	if await ctx.bot.is_owner(ctx.author):
		return True

	# last to check is mod_role
	gc = await GuildConfig.get_guild(ctx.guild.id)

	# if no mod role is set, no one else should have mod perms
	if gc.mod_role_id is None:
		return False

	# if set, see if author has this role
	return not not discord.utils.find(lambda role: role.id == gc.mod_role_id, ctx.author.roles)

def is_mod():
	return commands.check(is_mod_pred)
