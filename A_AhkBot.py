import discord
import datetime
import re

from funcs import *
import settings
import commands

client = discord.Client()

@client.event
async def on_message(message):
	# ignore user
	if message.author.id in settings.ignore_user:
		return

	# ignore chan
	if message.channel.name in settings.ignore_chan:
		return

	msg = ''

	if message.content.startswith("!helper"):
		role = discord.utils.get(message.server.roles, name="Helpers")
		if message.content in ("!helper+", "!helpers+"):
			print("Adding to helpers: " + message.author.name)
			await client.add_roles(message.author, role)
			await client.send_message(message.channel, "Added to Helpers!")
		elif message.content in ("!helper-", "!helpers-"):
			print("Removing from helpers: " + message.author.name)
			await client.remove_roles(message.author, role)
			await client.send_message(message.channel, "Removed from Helpers!")
		return

	if message.content in settings.plain:
		msg = settings.plain[message.content]

	elif message.content.startswith('!'):
		reg = re.match('!(.*?)(?:\s|\n|$)(.*)', message.content, re.DOTALL)
		cmd = reg.group(1).lower()
		cont = reg.group(2)

		# check if the command has an alias
		if cmd in settings.alias_assoc:
			cmd = settings.alias_assoc[cmd]

		# check if we're ignoring that command
		if cmd in settings.ignore_cmd:
			return

		# try to check if it's a function in the commands module
		try:
			msg = getattr(commands, cmd)(message, cont)
		except (AttributeError, TypeError):
			# if cmd is an alias, return the alias text
			if cmd in settings.alias:
				if type(settings.alias[cmd]) is dict:
					em = {}
					for key, val in settings.alias[cmd].items():
						em[key] = val.format(message)
					msg = em
				else:
					msg = settings.alias[cmd].format(message)
			# else, treat at as a docs search
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

	if msg:
		print()
		print("-" * 100)
		print()
		print('{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now()))
		print("\n{} in {}:".format(message.author.name, message.channel))
		print(message.content.split('\n')[0] + '\n')

		if type(msg) is dict:
			print('Returning embed:')
			print(msg['title'])
			if not 'color' in msg:
				msg['color'] = 0x78A064

			embed = discord.Embed(**msg)

			if 'image' in msg:
				embed.set_image(url=msg.pop('image'))
			if 'thumbnail' in msg:
				embed.set_thumbnail(url=msg.pop('thumbnail'))

			if 'footer' in msg:
				embed.set_footer(**msg.pop('footer'))

			if 'fields' in msg:
				for field in msg['fields']:
					embed.add_field(**field)

			await client.send_message(message.channel, embed=embed)
		else:
			print('Returning text:')
			print(msg.split('\n')[0])

			await client.send_message(message.channel, msg)

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