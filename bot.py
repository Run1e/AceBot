import discord, aiohttp, time, json
from discord.ext import commands

nick = 'Ace'
status = '.help for commands'

description = """
A.C.E. - Autonomous Command Executor

Written by: RUNIE 🔥#9646
Avatar artwork: Vinter Borge
Contributors: Cap'n Odin #8812 and GeekDude #2532
"""

extensions = (
	'cogs.admin',
	'cogs.commands',
	'cogs.highlighter',
	'cogs.tags',
	'cogs.reps',
	'cogs.votes',
	'cogs.muter',
	'cogs.guilds.autohotkey',
	'cogs.guilds.dwitter'
)

class AceBot(commands.Bot):
	def __init__(self):

		# load config file
		with open('lib/config.json', 'r') as f:
			self.config = json.loads(f.read())

		# init bot
		super().__init__(command_prefix=self.config['prefix'], description=description)

		self.owner_id = 265644569784221696
		self.session = aiohttp.ClientSession(loop=self.loop)

		with open('lib/ignore.json', 'r') as f:
			self.ignore_users = json.loads(f.read())

		# check for ignored users and bots
		self.add_check(self.blacklist_ctx)

		# print before invoke
		self.before_invoke(self.before_command)

	async def request(self, method, url, **args):
		try:
			async with self.session.request(method, url, **args) as resp:
				if resp.status != 200:
					return None
				if resp.content_type == 'application/json':
					return await resp.json()
				else:
					return await resp.text()
		except:
			return None

	async def before_command(self, ctx):
		print(f'\nServer: {ctx.guild.name}\nUser: {ctx.message.author.name}\nCommand: {ctx.command.name}')

	async def blacklist_ctx(self, ctx):
		return not self.blacklist(ctx.author)

	def blacklist(self, author):
		return author.id in self.ignore_users or author.bot

	async def on_ready(self):
		if not hasattr(self, 'uptime'):
			self.uptime = time.time()

		await self.user.edit(username=nick)
		await self.change_presence(game=discord.Game(name=status))

		for extension in extensions:
			print(f'Loading extension: {extension}')
			self.load_extension(extension)

		print(f'\nLogged in as: {self.user.name} - {self.user.id}\ndiscord.py {discord.__version__}')
		print(f'\nConnected to {len(self.guilds)} servers:')
		print('\n'.join(f'{guild.name} - {guild.id}' for guild in self.guilds))

	async def on_command_error(self, ctx, error):
		if isinstance(error, commands.CommandNotFound):
			return

		# if isinstance(error, commands.CommandInvokeError):
		#	return print(error)

		errors = {
			commands.DisabledCommand: 'Command has been disabled.',
			commands.MissingPermissions: 'Invoker is missing permissions to run this command.',
			commands.BotMissingPermissions: 'Bot is missing permissions to run this command.',
			commands.CheckFailure: 'You are not allowed to run this command.'
		}

		for type, text in errors.items():
			if isinstance(error, type):
				return await ctx.send(errors[type])

		# argument error
		if isinstance(error, commands.UserInputError):
			self.formatter.context = ctx
			self.formatter.command = ctx.command
			return await ctx.send(f'Invalid argument(s) provided.\n```{self.formatter.get_command_signature()}```')

		# await ctx.send(f'An error occured in `{ctx.command.name}` invoked by {ctx.message.author}:\n```{error}```')
		raise error.original


# overwrite discord.Embed with a monkey patched class that automatically sets the color attribute
class Embed(discord.Embed):
	def __init__(self, color=0x4A5E8C, **attrs):
		attrs['color'] = color
		super().__init__(**attrs)

discord.Embed = Embed

if __name__ == '__main__':
	bot = AceBot()
	bot.run(bot.config['token'])