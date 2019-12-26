import discord
import os
import shutil

from discord.ext import commands
from zipfile import ZipFile

from cogs.ahk.ids import *
from cogs.mixins import AceMixin

CHALLENGES_DIR = 'data/challenges'
MAX_SIZE = 8 * 1024 * 1024


class Challenges(AceMixin, commands.Cog):

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.guild is None or message.author.bot:
			return

		if message.channel.id != SUBMISSION_CHAN_ID:
			return

		async def send_info(msg):
			try:
				await message.channel.send('{} {}'.format(message.author.mention, msg), delete_after=10)
			except discord.HTTPException:
				pass

		if message.attachments and message.attachments[0].filename.endswith('.zip'):
			try:
				await self._save_entry(message.author, message.attachments[0])
				await send_info('Submission saved, thanks for participating!')
			except commands.CommandError as exc:
				await send_info(str(exc) + ' Code not submitted.')

		try:
			await message.delete()
		except discord.HTTPException:
			pass

	async def _save_entry(self, member, attachment):
		if attachment.size > MAX_SIZE:
			raise commands.CommandError('File size too large, 8 MB maximum.')

		# make users submission dir
		_dir = self._get_challenge_dir()
		submission_dir = '{}/{}'.format(_dir, str(member.id))

		# delete it if it already exists
		if os.path.isdir(submission_dir):
			shutil.rmtree(submission_dir)

		# re-create dirs
		os.makedirs(submission_dir, exist_ok=True)

		submission_zip = '{}/submission.zip'.format(submission_dir)
		fp = open(submission_zip, 'wb')

		# save zip
		try:
			await attachment.save(fp)
		except discord.HTTPException:
			shutil.rmtree(submission_dir)
			raise commands.CommandError('Failed downloading submission.')

		# attempt to unzip
		try:
			with ZipFile(submission_zip, 'r') as zip_ref:
				zip_ref.extractall(submission_dir)
		except:
			shutil.rmtree(submission_zip)
			raise commands.CommandError('Failed extracting zip archive.')

		# delete zip as it's now extracted
		os.remove(submission_zip)

		self._validity_check(submission_dir)

	def _get_challenge_dir(self):
		_dir = open(CHALLENGES_DIR + '/current', 'r').read().strip()
		if _dir == '':
			raise commands.CommandError('A challenge is currently not set up, please wait for the next challenge to be posted!')
		return CHALLENGES_DIR + '/' + _dir

	def _validity_check(self, _dir):
		pass


def setup(bot):
	bot.add_cog(Challenges(bot))
