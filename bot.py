import discord
from discord.ext import commands

import json

bot = commands.Bot(command_prefix='.', description="RUNIE's bot")

bot.description = f"A.C.E. - Autonomous Command Executor\n\nWritten by: RUNIE 🔥 #9646\nAvatar artwork: Vinter Borge\nContributors: Cap'n Odin #8812 and GeekDude #2532"

bot.owner_id = 265644569784221696

bot.info = {}

bot.info['nick'] = 'Ace'
bot.info['status'] = '.help for commands'

with open('cogs/data/ignore.json', 'r') as f:
	bot.info['ignore_users'] = json.loads(f.read())

extensions = (
	'cogs.commands',
	'cogs.autohotkey',
	'cogs.admin'
)

@bot.event
async def on_ready():
	await bot.user.edit(username=bot.info['nick'])
	await bot.change_presence(game=discord.Game(name=bot.info['status']))

	if __name__ == '__main__':
		print(f'Logged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')
		for extension in extensions:
			print(f'Loading extension: {extension}')
			bot.load_extension(extension)

	print(f'\nConnected to {len(bot.guilds)} servers:')
	print('\n'.join(f'{guild.name} - {guild.id}' for guild in bot.guilds))


# blacklist check
@bot.check_once
async def blacklist(ctx):
	return ctx.message.author.id not in bot.info['ignore_users']

# print command usage
@bot.before_invoke
async def before_any_command(ctx):
	print(f'------------------------\nServer: {ctx.guild.name}\nUser: {ctx.message.author.name}\nCommand: {ctx.command.name}\n')


# overwrite discord.Embed with a monkey patched class that automatically sets the color attribute
class Embed(discord.Embed):
	def __init__(self, color=0x78A064, **attrs):
		attrs['color'] = color
		super().__init__(**attrs)

discord.Embed = Embed

with open('lib/bot_token.txt', 'r') as f:
	bot.run(f.read())
