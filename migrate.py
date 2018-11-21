"""
USED TO MIGRATE OLD TAGS AND WELCOME MESSAGES
"""

import asyncio

from datetime import datetime
from peewee import *
from utils.database import setup_db, Tag

aTag = Tag

db = SqliteDatabase('old/tags.db')

class Tag(Model):
	name = CharField(max_length=20)
	alias = CharField(null=True, max_length=20)
	content = TextField()
	owner = BigIntegerField()
	guild = BigIntegerField()
	uses = IntegerField(default=0)
	created_at = DateTimeField(default=datetime.now)
	edited_at = DateTimeField(null=True)

	class Meta:
		database = db

async def main():
	await setup_db('postgresql://ace:password@129.242.75.116/acebot', loop=loop)
	
	for ptag in Tag.select():
		await aTag.create(
			name=ptag.name,
			alias=ptag.alias,
			content=ptag.content,
			owner_id=ptag.owner,
			guild_id=ptag.guild,
			uses=ptag.uses,
			created_at=ptag.created_at,
			edited_at=ptag.edited_at
		)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())