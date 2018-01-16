import discord
from discord.ext import commands

class Muter:
	"""Mute/unmute commands and anti-mention spam."""

	def __init__(self, bot):
		self.bot = bot
		self.guilds = (115993023636176902,)

	async def __local_check(self, ctx):
		return ctx.guild.id in self.guilds and ctx.author.permissions_in(ctx.channel).ban_members

	async def on_message(self, message):
		if message.guild.id not in self.guilds:
			return

		if len(message.mentions) > 4:
			ctx = await self.bot.get_context(message)
			await ctx.invoke(self.mute, member=message.author, reason='Misuse of mentions. A <@&311784919208558592> member will have to assess the situation.')

	@commands.command(hidden=True)
	async def mute(self, ctx, member: discord.Member, reason: str = None):
		role = discord.utils.get(ctx.guild.roles, name='Muted')
		await member.add_roles(role)
		await ctx.send(f"{member.mention} muted{'.' if reason is None else ': ' + reason}")

	@commands.command(hidden=True)
	async def unmute(self, ctx, member: discord.Member):
		role = discord.utils.get(ctx.guild.roles, name='Muted')
		await member.remove_roles(role)
		await ctx.send(f"{member.mention} unmuted.")

def setup(bot):
	bot.add_cog(Muter(bot))