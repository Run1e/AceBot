from asyncpg.exceptions import UniqueViolationError
import asyncio

class GuildConfig:
	bot = None
	guilds = dict()
	lock = asyncio.Lock()

	def __init__(self, guild_id, record):
		self.guild_id = guild_id
		self.config_id = record.get('id')
		self._modules = dict()
		self._prefix = record.get('prefix')

	@classmethod
	async def get_guild(cls, guild_id):
		async with cls.lock:
			if guild_id in cls.guilds:
				return cls.guilds[guild_id]

			conf = await cls.bot.db.fetchrow('SELECT * FROM guildconfig WHERE guild_id=$1', guild_id)

			if conf is None:
				await cls.bot.db.execute('INSERT INTO guildconfig (guild_id) VALUES ($1)', guild_id)
				conf = await cls.bot.db.fetchrow('SELECT * FROM guildconfig WHERE guild_id=$1', guild_id)

			ins = cls(guild_id, conf)
			cls.guilds[guild_id] = ins

			return ins

	@classmethod
	def set_bot(cls, bot):
		cls.bot = bot

	async def set_prefix(self, prefix):
		await self.bot.db.execute('UPDATE guildconfig SET prefix=$2 WHERE guild_id=$1', self.guild_id, prefix)
		self._prefix = prefix

	@property
	def prefix(self):
		return self._prefix

	async def enable_module(self, module) -> bool:
		try:
			await self.bot.db.execute('INSERT INTO module (guild_id, module) VALUES ($1, $2)', self.guild_id, module)
		except UniqueViolationError:
			return False

		self._modules[module] = True
		return True

	async def disable_module(self, module) -> bool:
		if not await self.uses_module(module):
			return False

		await self.bot.db.execute(
			'DELETE FROM module WHERE guild_id=$1 AND module=$2',
			self.guild_id, module
		)

		self._modules[module] = False
		return True

	async def uses_module(self, module):
		if module in self._modules:
			return self._modules[module]

		uses_module = await self.bot.db.fetchval(
			'SELECT id FROM module WHERE guild_id=$1 AND module=$2',
			self.guild_id, module
		)

		used = False if uses_module is None else True
		self._modules[module] = used

		return used