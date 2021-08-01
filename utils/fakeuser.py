from discord import Object


class FakeUser(Object):
	def __init__(self, id, guild=None, **data):
		super().__init__(id)

		self._guild = guild
		self._data = data

	@property
	def guild(self):
		if self._guild is None:
			raise ValueError('FakeUser does not have a guild')

		return self._guild

	@property
	def mention(self):
		return f'<@!{self.id}>'

	@property
	def name(self):
		return self._data.get('name', 'Unknown User')

	@property
	def nick(self):
		return self._data.get('nick', None)

	@property
	def display_name(self):
		return self.nick or self.name

	@property
	def discriminator(self):
		return self._data.get('discriminator', '????')

	@property
	def avatar_url(self):
		return self._data.get('avatar_url', 'https://cdn.discordapp.com/embed/avatars/0.png')

	@property
	def avatar(self):

		@property
		def url(self):
			return self._data.get('avatar.url', 'https://cdn.discordapp.com/embed/avatars/0.png')

	def __str__(self):
		name = self.name
		nick = self.nick
		discriminator = self.discriminator

		string = ''
		if nick is not None:
			string += nick
		elif name is not None:
			string += name
		else:
			raise ValueError('Not enough information in FakeMember data to craft str')

		if discriminator is not None:
			string += '#' + discriminator

		return string
