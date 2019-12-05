import discord
import asyncio

from discord.ext import commands

REQUIRED_PERMS = ('send_messages', 'embed_links', 'add_reactions')

EMOJIS = ('\N{WHITE HEAVY CHECK MARK}', '\N{CROSS MARK}')

ADMIN_PROMPT_ABORTED = commands.CommandError('Administrative action aborted.')


async def prompter(ctx, title=None, prompt=None):
	'''Creates a yes/no prompt.'''

	perms = ctx.guild.me.permissions_in(ctx.channel)
	if not all(getattr(perms, perm) for perm in REQUIRED_PERMS):
		return False

	prompt = prompt or 'No description provided.'
	prompt += '\n\nPress {} to continue, {} to abort.'.format(*EMOJIS)

	e = discord.Embed(description=prompt)

	e.set_author(name=title or 'Prompter', icon_url=ctx.bot.user.avatar_url)

	try:
		msg = await ctx.send(embed=e)
		for emoji in EMOJIS:
			await msg.add_reaction(emoji)
	except discord.HTTPException as e:
		print(e)
		return False

	def check(reaction, user):
		return reaction.message.id == msg.id and user == ctx.author and str(reaction) in EMOJIS

	try:
		reaction, user = await ctx.bot.wait_for('reaction_add', check=check, timeout=60.0)
		return str(reaction) == EMOJIS[0]
	except (asyncio.TimeoutError, discord.HTTPException):
		return False
	finally:
		try:
			await msg.delete()
		except discord.HTTPException:
			pass


async def admin_prompter(ctx):
	return await prompter(
		ctx, title='Warning!',
		prompt=(
			'You are about to do an administrative action on an item you do not own.\n\n'
			'Are you sure you want to continue?'
		)
	)
