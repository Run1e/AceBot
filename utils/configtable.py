import asyncio

from asyncpg.exceptions import NotNullViolationError
from discord.ext import commands


class ConfigTableEntry:
	def __init__(self, cfg, record):
		self._config = cfg
		self._values = {key: record.get(key) for key in cfg.keys.keys()}

		self.__slots__ = cfg.keys.keys()

	async def set(self, key, value):
		if key not in self._config.keys:
			raise AttributeError('Key \'{}\' not defined in \'{}\''.format(key, self._config.table))

		expected_type = self._config.keys[key]

		if value is not None and not isinstance(value, expected_type):
			raise TypeError('Key \'{}\' should be of type {}, got {}'.format(
				key, expected_type.__name__, type(value).__name__)
			)

		# raises NotNullViolationError if value is None and schema actually doesn't allow it, it's an ok fix for now
		await self._config.bot.db.execute(
			'UPDATE {} SET {}=$1 WHERE {}=$2'.format(self._config.table, key, self._config.primary),
			value, getattr(self, self._config.primary)
		)
		self._values[key] = value

	def __getattr__(self, item):
		if item in self._values:
			return self._values[item]


class ConfigTable:

	PRIMARY_KEY_TYPE_ERROR = TypeError('Primary key must be int.')

	def __init__(self, bot, table, primary, keys, entry_class=None):
		entry_class = entry_class or ConfigTableEntry

		if entry_class is not ConfigTableEntry and not issubclass(entry_class, ConfigTableEntry):
			raise TypeError('entry_class must inherit from ConfigTableEntry.')

		if isinstance(primary, str):
			primary = (primary,)
		elif not isinstance(primary, tuple):
			raise TypeError('Primary keys must be tuple or string.')

		self.bot = bot
		self.lock = asyncio.Lock()
		self.entry_class = entry_class
		self.table = table
		self.primary = primary
		self._entries = dict()
		self.keys = keys

	@property
	def entries(self):
		return self._entries.values()

	def insert_record(self, record):
		entry = self.entry_class(self, record)
		self._entries[record.get(self.primary)] = entry

		return entry

	@property
	def _get_query(self):
		query = 'SELECT * FROM {} WHERE '.format(self.table)

		sub = list()
		for idx, key in enumerate(self.primary):
			sub.append('{} = ${}'.format(key, idx + 1))

		return query + ' AND '.join(sub)

	@property
	def _create_query(self):
		return 'INSERT INTO {} ({}) VALUES ({})'.format(
			self.table,
			', '.join(self.primary),
			', '.join('${}'.format(idx + 1) for idx, _ in enumerate(self.primary))
		)

	async def get_entry(self, *keys):
		keys = tuple(keys)

		for key in keys:
			if not isinstance(key, int):
				raise self.PRIMARY_KEY_TYPE_ERROR

		get_query = self._get_query

		async with self.lock:
			if keys in self._entries:
				return self._entries[keys]

			record = await self.bot.db.fetchrow(get_query, *keys)

			if record is None:
				await self.bot.db.execute(self._create_query, *keys)

				record = await self.bot.db.fetchrow(get_query, *keys)

			return self.insert_record(record)


class GuildConfigEntry(ConfigTableEntry):

	@property
	def mod_role(self):
		if self.mod_role_id is None:
			return None

		guild = self._config.bot.get_guild(self.guild_id)

		if guild is None:
			return None

		return guild.get_role(self.mod_role_id)


class StarboardConfigEntry(ConfigTableEntry):

	@property
	def channel(self):
		if self.channel_id is None:
			return None

		guild = self._config.bot.get_guild(self.guild_id)
		if guild is None:
			return None

		return guild.get_channel(self.channel_id)


class SecurityConfigEntry(ConfigTableEntry):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.create_spam_cooldown()
		self.create_mention_cooldown()

	@property
	def guild(self):
		return self._config.bot.get_guild(self.guild_id)

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

	# injects it into the _values dict so __getattr__ can find them
	def create_spam_cooldown(self):
		self.spam_cooldown = commands.CooldownMapping.from_cooldown(
			self.spam_count, self.spam_per, commands.BucketType.user
		)

	def create_mention_cooldown(self):
		self.mention_cooldown = commands.CooldownMapping.from_cooldown(
			self.mention_count, self.mention_per, commands.BucketType.user
		)
