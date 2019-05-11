import asyncio
from gino import Gino
from gino.exceptions import *
from asyncpg.exceptions import *

db = Gino()


# list of users the bot ignores
class IgnoredUser(db.Model):
	__tablename__ = 'ignore'

	user_id = db.Column(db.BigInteger, primary_key=True)


class LogEntry(db.Model):
	__tablename__ = 'log'

	id = db.Column(db.Integer, primary_key=True)
	guild_id = db.Column(db.BigInteger)
	channel_id = db.Column(db.BigInteger)
	author_id = db.Column(db.BigInteger)
	date = db.Column(db.DateTime)
	command = db.Column(db.String)


class GuildModule(db.Model):
	__tablename__ = 'module'

	id = db.Column(db.Integer, primary_key=True)
	guild_id = db.Column(db.BigInteger)
	module = db.Column(db.String)


class Tag(db.Model):
	__tablename__ = 'tag'

	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.Unicode)
	alias = db.Column(db.Unicode, nullable=True)
	content = db.Column(db.Unicode)
	guild_id = db.Column(db.BigInteger)
	owner_id = db.Column(db.BigInteger)
	uses = db.Column(db.Integer)
	created_at = db.Column(db.DateTime)
	edited_at = db.Column(db.DateTime, nullable=True)


class WelcomeMsg(db.Model):
	__tablename__ = 'welcome'

	id = db.Column(db.Integer, primary_key=True)
	guild_id = db.Column(db.BigInteger)
	channel_id = db.Column(db.BigInteger, nullable=True)
	content = db.Column(db.Unicode)


class HighlightLang(db.Model):
	__tablename__ = 'highlight'

	id = db.Column(db.Integer, primary_key=True)
	guild_id = db.Column(db.BigInteger)
	user_id = db.Column(db.BigInteger, nullable=True)
	language = db.Column(db.Text)


class UserCoin(db.Model):
	__tablename__ = 'coin'

	id = db.Column(db.Integer, primary_key=True)
	guild_id = db.Column(db.BigInteger)
	user_id = db.Column(db.BigInteger)
	bets = db.Column(db.Integer)
	biggest_win = db.Column(db.BigInteger, nullable=True)
	biggest_loss = db.Column(db.BigInteger, nullable=True)
	biggest_mult = db.Column(db.BigInteger, nullable=True)
	coins = db.Column(db.BigInteger)


class StarGuild(db.Model):
	__tablename__ = 'starguild'

	id = db.Column(db.Integer, primary_key=True)
	guild_id = db.Column(db.BigInteger)
	channel_id = db.Column(db.BigInteger)


class StarMessage(db.Model):
	__tablename__ = 'starmessage'

	id = db.Column(db.Integer, primary_key=True)
	guild_id = db.Column(db.BigInteger)
	author_id = db.Column(db.BigInteger)
	message_id = db.Column(db.BigInteger)
	channel_id = db.Column(db.BigInteger)
	star_message_id = db.Column(db.BigInteger)
	starrer_id = db.Column(db.BigInteger)
	starred_at = db.Column(db.DateTime)


class Starrers(db.Model):
	__tablename__ = 'starrers'

	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.BigInteger)
	star_id = db.Column(None, db.ForeignKey('starmessage.id'))


class RemindMeEntry(db.Model):
	__tablename__ = 'reminder'

	id = db.Column(db.Integer, primary_key=True)
	guild_id = db.Column(db.BigInteger)
	channel_id = db.Column(db.BigInteger)
	user_id = db.Column(db.BigInteger)
	remind_on = db.Column(db.DateTime)
	made_on = db.Column(db.DateTime)
	message = db.Column(db.Unicode, nullable=True)


class DocsEntry(db.Model):
	__tablename__ = 'docs'

	id = db.Column(db.Integer, primary_key=True)

	# required
	desc = db.Column(db.Text, nullable=True)
	page = db.Column(db.Text, unique=True)


class DocsNameEntry(db.Model):
	__tablename__ = 'docs_name'

	id = db.Column(db.Integer, primary_key=True)

	docs_id = db.Column(None, db.ForeignKey('docs.id'))
	name = db.Column(db.Text, unique=True)


class DocsSyntaxEntry(db.Model):
	__tablename__ = 'docs_syntax'

	id = db.Column(db.Integer, primary_key=True)

	docs_id = db.Column(None, db.ForeignKey('docs.id'))
	syntax = db.Column(db.Text)


class DocsParamEntry(db.Model):
	__tablename__ = 'docs_param'

	id = db.Column(db.Integer, primary_key=True)

	docs_id = db.Column(None, db.ForeignKey('docs.id'))
	name = db.Column(db.Text)
	value = db.Column(db.Text)


class SeenEntry(db.Model):
	__tablename__ ='seen'

	guild_id = db.Column(db.BigInteger, primary_key=True)
	user_id = db.Column(db.BigInteger, primary_key=True)
	seen = db.Column(db.DateTime)


async def setup_db(bind, loop):
	# connect
	await db.set_bind(bind, loop=loop)

	# create tables
	await db.gino.create_all()

	return db
