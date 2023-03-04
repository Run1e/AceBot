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
