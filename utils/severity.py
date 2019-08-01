import discord

from enum import Enum


class SeverityColors(Enum):
	LOW = discord.Embed().color
	MEDIUM = 0xFF8C00
	HIGH = 0xFF2000
