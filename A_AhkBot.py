import discord
import re

from funcs import *
import settings
import commands

client = discord.Client()

@client.event
async def on_message(message):
	if message.author == client.user:
		return

	# ignore from chan
	if message.channel.name in settings.ignore_chan:
		return

	msg = ''

	if message.content.startswith('!'):
		cmd = message.content[1:].split(' ')[0].lower()

		if cmd in settings.ignore_cmd:
			return

		if cmd in settings.alias_assoc:
			cmd = settings.alias_assoc[cmd]

		if cmd in settings.alias:
			if type(settings.alias[cmd]) is dict:
				em = {}
				for key, val in settings.alias[cmd].items():
					em[key] = val.format(message)
				msg = {"embed": discord.Embed(**em)}
			else:
				msg = settings.alias[cmd].format(message)
		elif hasattr(commands, cmd):
			msg = getattr(commands, cmd)(message)
		elif len(cmd):
			msg = commands.docs(message, cmd)

		if cmd in settings.del_cmd:
			await client.delete_message(message)

	else:
		try:
			link = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content)[0]
		except Exception:
			link = ''

		if link.startswith("http://p.ahkscript.org/?"):
			msg = pastesnippet(link)
		elif link.startswith("https://autohotkey.com/boards/viewtopic.php?"):
			msg = forumsnippet(link)

	if msg != '':
		print("-" * 50)
		print('{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now()))
		print("\n{} in {}:".format(message.author.name, message.channel))
		print(message.content.split('\n')[0])
		print("\nResponse:")

		if type(msg) is dict:
			print(msg['embed'].to_dict()['title'])
			await client.send_message(message.channel, **msg)
		else:
			print(msg.split('\n')[0])
			await client.send_message(message.channel, msg)
		print("\n")

	return

@client.event
async def on_ready():
	print(client.user.name)
	print(client.user.id)
	print(discord.__version__)
	await client.change_presence(game=discord.Game(name='autohotkey.com'))

with open("token.txt", "r") as f:
	token = f.read()

client.run(token)