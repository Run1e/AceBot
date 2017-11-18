import discord
from discord.ext import commands

import os
import json

bot = commands.Bot(command_prefix=('!', '.'), description="RUNIE's bot")

bot.info = {}

bot.info['msgs'] = {}
bot.info['last_msg'] = None

with open('cogs/data/ignore.json', 'r') as f:
	bot.info['ignore_users'] = json.loads(f.read())

for file in os.listdir('cogs/data/msgs/'):
	with open(f'cogs/data/msgs/{file}', 'r') as f:
		bot.info['msgs'][file.split('.')[0]] = json.loads(f.read())

print(bot.info['msgs'])

bot.info['nick'] = 'Golbot'
bot.info['status'] = '.help for commands'

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

@bot.event
async def on_command_completion(ctx):
	if bot.info['last_msg'] == None or ctx.command.name == 'delete':
		return

	author = str(ctx.author.id)
	channel = str(ctx.message.channel.id)

	# make sure the channel is listed
	try:
		bot.info['msgs'][channel]
	except:
		bot.info['msgs'][channel] = {}

	# make sure the user is listed
	try:
		bot.info['msgs'][channel][author]
	except:
		bot.info['msgs'][channel][author] = []

	msg_list = bot.info['msgs'][channel][author]

	if len(msg_list) > 4:
		msg_list.remove(msg_list[0])

	# author/bot msg tuple
	msg_list.append([ctx.message.id, bot.info['last_msg'].id])

	bot.info['last_msg'] = None

	with open(f'cogs/data/msgs/{channel}.json', 'w') as f:
		f.write(json.dumps(bot.info['msgs'][channel], sort_keys=True, indent=4))


@bot.event
async def on_message(message):
	if message.author.id == bot.user.id:
		bot.info['last_msg'] = message
	await bot.process_commands(message)

# blacklist check
@bot.check_once
async def blacklist(ctx):
	return ctx.message.author.id not in bot.info['ignore_users']

# print command usage
@bot.before_invoke
async def before_any_command(ctx):
	print(f'----------------\nServer: {ctx.guild.name}\nUser: {ctx.message.author.name}\nCommand: {ctx.command.name}\n')


# overwrite discord.Embed with a monkey patched class that automatically sets the color attribute
class Embed(discord.Embed):
    def __init__(self, color=0x78A064, **attrs):
        attrs['color'] = color
        super().__init__(**attrs)

discord.Embed = Embed

with open('lib/bot_token.txt', 'r') as f:
	bot.run(f.read())