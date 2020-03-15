from .configtable import ConfigTableRecord


class GuildConfigRecord(ConfigTableRecord):
	@property
	def mod_role(self):
		if self.mod_role_id is None:
			return None

		guild = self._config.bot.get_guild(self.guild_id)

		if guild is None:
			return None

		return guild.get_role(self.mod_role_id)

	@property
	def mute_role(self):
		if self.mute_role_id is None:
			return None

		guild = self._config.bot.get_guild(self.guild_id)

		if guild is None:
			return None

		return guild.get_role(self.mute_role_id)

	@property
	def log_channel(self):
		if self.log_channel_id is None:
			return None

		guild = self._config.bot.get_guild(self.guild_id)
		if guild is None:
			return None

		return guild.get_channel(self.log_channel_id)
