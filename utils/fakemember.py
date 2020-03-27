class FakeMember:
	def __init__(self, guild, id, name, avatar_url, discriminator=None, nick=None):
		self.guild = guild

		self.id = id
		self.name = name
		self.nick = nick
		self.discriminator = discriminator
		self.avatar_url = avatar_url
		self.mention = '<@{0.id}>'.format(self)

	def __str__(self):
		value = self.name
		if self.discriminator is not None:
			value += '#' + self.discriminator
		return value
