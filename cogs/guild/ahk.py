import discord, asyncio
from discord.ext import commands

from ace import log
from utils.docs_search import docs_search
from utils.string_manip import welcomify, to_markdown, shorten
from cogs.base import TogglableCogMixin

from html2text import HTML2Text
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

htt = HTML2Text()
htt.body_width = 0

# for verification stuff
GENERAL_ID = 115993023636176902
STAFF_ID = 311784919208558592
MEMBER_ID = 509526426198999040

WELCOME_MSG = '''
Welcome to our Discord community {user}!
A collection of useful tips are in <#407666416297443328> and recent announcements can be found in <#367301754729267202>.
'''

# for rss
#FORUM_ID = 517692823621861409
FORUM_ID = 536785342959845386

# for roles
ROLES_CHANNEL = 513071256283906068
ROLES = {
	345652145267277836: '💻',  # helper
	513078270581932033: '🕹',  # lounge
	513111956425670667: '🇭',  # hotkey crew
	513111654112690178: '🇬',  # gui crew
	513111541663662101: '🇴',  # oop crew
	513111591361970204: '🇷'  # regex crew
}

class AutoHotkey(TogglableCogMixin):
	'''Commands for the AutoHotkey guild.'''

	def __init__(self, bot):
		super().__init__(bot)
		self.bot.loop.create_task(self.rss())

	async def __local_check(self, ctx):
		return await self._is_used(ctx)

	async def on_command_error(self, ctx, error):
		if ctx.guild.id != 115993023636176902:
			return

		# command not found? docs search it. only if message string is not *only* dots though
		if isinstance(error, commands.CommandNotFound) and len(
				ctx.message.content) > 3 and not ctx.message.content.startswith('..'):
			await ctx.invoke(self.docs, search=ctx.message.content[1:])

	async def on_raw_reaction_add(self, payload):
		if payload.channel_id != ROLES_CHANNEL:
			return

		channel = self.bot.get_channel(payload.channel_id)
		msg = await channel.get_message(payload.message_id)
		if msg.author.id != self.bot.user.id:
			return

		guild = self.bot.get_guild(payload.guild_id)
		member = guild.get_member(payload.user_id)

		if member.bot:
			return

		await msg.remove_reaction(payload.emoji, member)

		action = None

		for role_id, emoji in ROLES.items():
			if emoji == str(payload.emoji):
				role = guild.get_role(role_id)
				action = True
				desc = f'{member.mention} -> {role.mention}'
				if role in member.roles:
					await member.remove_roles(role)
					title = 'Removed Role'
				else:
					await member.add_roles(role)
					title = 'Added Role'

		if action:
			log.info('{} {} {} {}'.format(title, role.name, 'to' if title == 'Added Role' else 'from', member.name))
			await channel.send(embed=discord.Embed(title=title, description=desc), delete_after=5)

	@commands.command(hidden=True)
	@commands.is_owner()
	async def roles(self, ctx):
		if ctx.channel.id != ROLES_CHANNEL:
			return

		await ctx.message.delete()
		await ctx.channel.purge()

		roles = []
		for role_id in ROLES:
			roles.append(ctx.guild.get_role(role_id))

		e = discord.Embed(description='Click the reactions to add yourselves to a role!')

		for role in roles:
			e.add_field(name=ROLES[role.id], value=role.mention)

		msg = await ctx.send(embed=e)

		for role in roles:
			await msg.add_reaction(ROLES[role.id])

	async def rss(self):

		url = 'https://www.autohotkey.com/boards/feed'

		channel = self.bot.get_channel(FORUM_ID)

		def parse_date(date_str):
			date_str = date_str.strip()
			return datetime.strptime(date_str[:-6], "%Y-%m-%dT%H:%M:%S") + timedelta(hours=6)

		old_time = datetime.now() - timedelta(minutes=1)

		while True:
			await asyncio.sleep(5 * 60)

			try:
				async with self.bot.aiohttp.request('get', url) as resp:
					if resp.status != 200:
						continue
					xml_rss = await resp.text()

				xml = BeautifulSoup(xml_rss, 'xml')

				for entry in xml.find_all('entry')[::-1]:
					time = parse_date(entry.updated.text)
					title = htt.handle(entry.title.text)
					content = shorten(entry.content.text, 512, 8)

					if time > old_time and '• Re: ' not in title:
						e = discord.Embed(
							title=title,
							description=to_markdown(content.split('Statistics: ')[0]),
							url=entry.id.text
						)

						e.add_field(name='Author', value=entry.author.text)
						e.add_field(name='Forum', value=entry.category['label'])
						e.timestamp = time

						if channel is not None:
							await channel.send(embed=e)

						old_time = time
			except (SyntaxError, ValueError, AttributeError) as exc:
				raise exc
			except Exception:
				pass

	@commands.command()
	async def docs(self, ctx, *, search):
		'''Search the AutoHotkey documentation.'''

		embed = discord.Embed()
		results = docs_search(search)

		if not len(results):
			raise commands.CommandError('No documentation pages found.')

		elif len(results) == 1:
			for title, obj in results.items():
				embed.title = obj.get('syntax', title)
				embed.description = obj['desc']
				if 'dir' in obj:
					embed.url = f"https://autohotkey.com/docs/{obj['dir']}"

		else:
			for title, obj in results.items():
				value = obj['desc']
				if 'dir' in obj:
					value += f"\n[Documentation](https://autohotkey.com/docs/{obj['dir']})"
				embed.add_field(
					name=obj.get('syntax', title),
					value=value
				)

		await ctx.send(embed=embed)

	@commands.command(hidden=True, aliases=['app'])
	@commands.has_role(STAFF_ID)
	async def approve(self, ctx, member: discord.Member):
		'''Approve member.'''

		try:
			member_role = ctx.guild.get_role(MEMBER_ID)
			if member_role is None:
				raise commands.CommandError('Couldn\'t find Member role.')

			await member.add_roles(member_role, reason=f'Approved by {ctx.author.name}')

		except Exception as exc:
			raise commands.CommandError('Failed adding member role.\n\nError:\n' + str(exc))

		await ctx.send(f'{member.display_name} approved.')

		general_channel = ctx.guild.get_channel(GENERAL_ID)
		if general_channel is None:
			raise commands.CommandError('Couldn\'t find the #general channel.')

		await asyncio.sleep(3)
		await general_channel.send(welcomify(member, ctx.guild, WELCOME_MSG))


	@commands.command(hidden=True)
	@commands.is_owner()
	async def ahkrules(self, ctx):
		await ctx.message.delete()

		e = discord.Embed()

		e.set_author(name='AutoHotkey server rules!', icon_url=ctx.guild.icon_url)

		e.add_field(
			name='1. Be nice to each other.',
			value=(
				'Treat others like you want others to treat you. This includes not getting heated up and making '
				'arguments unpleasant.'
			)
		)

		e.add_field(
			name='2. No NSFW or antagonizing content.',
			value=(
				'This includes but is not limited to nudity, sexual content, gore, personal information or otherwise '
				'disruptive content.'
			)
		)

		e.add_field(
			name='3. No spamming/flooding of voice or text channels.',
			value=(
				'Repeated posting of text, links, images, videos or abusing the voice channels is not tolerated.'
			)
		)

		e.add_field(
			name='4. Scripting questions should *only* be asked in the channels grouped under the AutoHotkey category.',
			value=(
				'Pick the channel that makes most sense for your question. If you\'re unsure, just ask in #scripting!'
			)
		)

		e.add_field(
			name='5. Do not discuss the creation or usage of malicious scripts.',
			value=(
				'Discussing, distributing, or any attempt at creating a cheat, keylogger, virus, spam tool, '
				'"joke" script, phishing script, or anything similar is not tolerated and will lead to a kick/ban. '
				'If you are unsure whether your script can be seen as malicious, please ask @Staff.'
			)
		)

		e.add_field(
			name='6. Do not tag individuals for help.',
			value=(
				'If you\'re asking for help, use the @Helpers tag or the Crew tags. Do not tag or PM @Staff or '
				'invididual users for help.'
			)
		)

		e.add_field(
			name='7. Only open-source.',
			value=(
				'Do not share compiled or obfuscated versions of your script.'
			)
		)

		e.add_field(
			name='Important notes',
			value=(
				'**A.** Being disrespectful to our volunteering @Helpers or @Staff because they won\'t help you with '
				'your script will get you banned. Them being in the Helpers role does not make them obligated to '
				'help you.\n'
				'**B.** If your nick is unreadable/untaggable, you might be asked to change it. If you refuse it will '
				'be changed for you.'
			)
		)

		e.set_footer(text='Rules updated: 06/12/2018')

		await ctx.send(embed=e)

def setup(bot):
	bot.add_cog(AutoHotkey(bot))
