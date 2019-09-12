class FakeContext:
	def __init__(self, guild, author, channel):
		self.guild = guild
		self.channel = channel
		self.author = author
