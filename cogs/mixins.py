from datetime import datetime

from ace import AceBot


class AceMixin:
    def __init__(self, bot: AceBot):
        self.bot: AceBot = bot

    @property
    def db(self):
        return self.bot.db
