from discord.ext import commands


async def check_perms(ctx, perms, check=all):
	if await ctx.bot.is_owner(ctx.author):
		return True
	author_perms = ctx.channel.permissions_for(ctx.author)
	return check(getattr(author_perms, name, None) == value for name, value in perms.items())


# invoker is either bot owner or someone with manage guild permissions
def is_mod(**perms):
	async def pred(ctx):
		pass
	return commands.check(pred)
