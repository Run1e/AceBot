class FakeMember:
	def __init__(self, id, name, avatar_url, guild):
		self.id = id
		self.nick = name
		self.display_name = name
		self.guild = guild
		self.avatar_url = avatar_url
		self.mention = '<@{0.id}>'.format(self)
