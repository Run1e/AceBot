import discord

def pretty_dobject(obj):
	if not isinstance(obj, discord.Object):
		return None

	return f'name={obj.name} id={obj.id}'