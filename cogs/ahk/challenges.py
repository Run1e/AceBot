import discord
import os
import shutil
import subprocess

from discord.ext import commands
from datetime import datetime
from zipfile import ZipFile
from enum import Enum

from cogs.ahk.ids import *
from cogs.mixins import AceMixin


CHALLENGES_DIR = 'data/challenges'
MAX_ZIP_SIZE = 8 * 1024 * 1024
MAX_FILE_SIZE = 2 * 1024 * 1024


class SubmissionType(Enum):
	ADD = 1
	UPDATE = 2


class Challenges(AceMixin, commands.Cog):
	@commands.Cog.listener()
	async def on_message(self, message):
		if message.guild is None or message.author.bot:
			return

		if message.channel.id != SUBMIT_CHAN_ID:
			return

		async def send_info(msg, is_bad=False):
			try:
				await message.channel.send(
					'{} {}{}'.format(message.author.mention, msg, ' Entry not submitted.' if is_bad else ''),
					delete_after=10
				)
			except discord.HTTPException:
				pass

		attachment = None
		member = message.author

		if message.attachments and message.attachments[0].filename.endswith('.zip'):
			attachment = message.attachments[0]

		zipped = f'{CHALLENGES_DIR}/temp/{member.id}.zip'

		if attachment is not None:
			try:
				await attachment.save(open(zipped, 'wb'))
			except discord.HTTPException:
				os.remove(zipped)
				await send_info('Downloading ZIP failed.', True)

		try:
			await message.delete()
		except discord.HTTPException:
			pass

		if attachment is None:
			return

		try:
			_dir = self._get_challenge_dir()
		except commands.CommandError as exc:
			await send_info(str(exc), True)
			return

		submit_type = SubmissionType.ADD
		sub_dir = '{}/{}'.format(_dir, str(member.id))
		temp_dir = '{}/temp/{}'.format(CHALLENGES_DIR, str(member.id))

		def cleanup():
			if os.path.isfile(zipped):
				try:
					os.remove(zipped)
				except:
					pass

			shutil.rmtree(temp_dir, ignore_errors=True)

		# remove temp dir if it already exists for some reason
		if os.path.isdir(temp_dir):
			shutil.rmtree(temp_dir, ignore_errors=True)

		# create temp dir
		os.makedirs(temp_dir)

		# attempt to unzip to temp dir
		try:
			with ZipFile(zipped, 'r') as zip:
				for mem in zip.infolist():
					# not using extractall protects against zip bombs
					if mem.file_size > MAX_FILE_SIZE:
						raise commands.CommandError('ZIP archive contains files that are too large (> 2MB).')

					# and manually extracting each member ensures no path fuckery which is BAD
					zip.extract(mem, temp_dir)
		except Exception as exc:
			cleanup()
			await send_info('Unzipping failed, {}'.format(str(exc)), True)
			return

		# unzip success, perform verification
		try:
			self._validity_check(temp_dir)
		except commands.CommandError as exc:
			cleanup()
			await send_info(str(exc), True)
			return

		# verification success, delete previous submission if it exists
		if os.path.isdir(sub_dir):
			shutil.rmtree(sub_dir)
			submit_type = SubmissionType.UPDATE

		# rename temp dir to submission dir
		os.rename(temp_dir, sub_dir)

		if submit_type is SubmissionType.ADD:
			msg = 'Submission added.'
		else:
			msg = 'Submission updated.'

		try:
			await message.channel.send('{} {} Thanks for participating!'.format(member.mention, msg), delete_after=10)
		except discord.HTTPException:
			pass

		# add log for organizers
		try:
			channel = message.guild.get_channel(SUBMISSIONS_CHAN_ID)
			if channel is not None:
				e = discord.Embed(description=msg)
				e.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)
				e.set_footer(text='ID: {}'.format(message.author.id))
				e.timestamp = datetime.utcnow()
				await channel.send(embed=e)
		except discord.HTTPException:
			pass

		# add challenger role to submitter
		challenger = message.guild.get_role(CHALLENGER_ROLE_ID)
		if challenger is not None:
			try:
				await member.add_roles(challenger, reason='Auto-add upon challenge submission')
			except discord.HTTPException:
				pass

		# perform final cleanup
		cleanup()

		# run git script to create a new commit for this submission (if any)
		def git():
			subprocess.run([f'{CHALLENGES_DIR}/git.sh', str(submit_type.value), sub_dir[28:]], capture_output=False)

		await self.bot.loop.run_in_executor(None, git)

		# it gets pushed by an incron entry on the host machine

	def _get_challenge_dir(self):
		_dir = open('{}/current'.format(CHALLENGES_DIR), 'r').read().strip()
		if _dir == '':
			raise commands.CommandError('A challenge is currently not running, please wait for the next challenge to be announced!')
		return '{}/submissions/{}'.format(CHALLENGES_DIR, _dir)

	def _validity_check(self, _dir):
		expected = dict(ahk=False)
		disallowed = ('exe',)

		for root, dirs, files in os.walk(_dir):
			for ext, found in filter(lambda exp: not exp[1], expected.items()):
				expected[ext] = any(file.lower().endswith('.' + ext) for file in files)

			for disallowed_ext in disallowed:
				for file in files:
					if file.lower().endswith('.' + disallowed_ext):
						raise commands.CommandError('Disallowed file with extension `{}`.'.format(disallowed_ext))

		for exp, found in expected.items():
			if not found:
				raise commands.CommandError('Missing file(s) of type `{}`.'.format(exp))


def setup(bot):
	bot.add_cog(Challenges(bot))
