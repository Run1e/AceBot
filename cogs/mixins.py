from discord.ext import commands

from utils.guildconfig import GuildConfig

class AceMixin:
	def __init__(self, bot):
		self.bot = bot

	@property
	def db(self):
		return self.bot.db
