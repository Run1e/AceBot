from ace import AceBot

from datetime import datetime


class AceMixin:
	def __init__(self, bot: AceBot):
		self.bot = bot

	@property
	def db(self):
		return self.bot.db
