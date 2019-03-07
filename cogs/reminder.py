import discord
from discord.ext import commands
import asyncio

from utils.database import db, Reminders
from cogs.base import TogglableCogMixin
from datetime import datetime, timedelta

class TimeUnit(commands.Converter):
    async def convert(self, ctx, unit: str):
        unit = unit.lower()

        if unit is None:
            unit = 'minute' # If a unit isn't passed, assume minutes
        if unit[-1] == 's':
            unit = unit[0:-1] # If a unit is passed, but plural, remove the "s" at the end

        units = {'minute':60, 'hour':60 * 60, 'day': 60 * 60 * 24}

        try:
            seconds = units[unit] # Try to get the mult for the unit, if it fails then an invalid unit was passed and we can throw a UnitError
        except KeyError:
            raise commands.BadArgument

        return seconds

class Reminder(TogglableCogMixin):
    
    SUCCESS_EMOJI = '\U00002705'
    CHECK_EVERY = 60
    DEFAULT_REMINDER_MESSAGE = 'Hey, wake up!'
    REMINDER_PREFIX = 'Reminder:```'
    REMINDER_SUFIX = '```'

    def __init__(self, bot):
        super().__init__(bot)
        self.bot.loop.create_task(self.check_reminders())

    @commands.command(aliases=['reminder'])
    async def remindme(self, ctx, amount: int, unit: TimeUnit, *, message = None):
        seconds = amount * unit
        
        time = datetime.now() + timedelta(seconds=seconds) # Create a datetime object of the current time, and add how long to wait before reminding to it
        
        await Reminders.create(
            guild_id = ctx.guild.id,
            user_id = ctx.author.id,
            remind_on = time,
            message = message
        )
        # Add the reminder to the DB

        await ctx.message.add_reaction(self.SUCCESS_EMOJI)

    async def check_reminders(self):
        while True:
            query = 'SELECT * FROM reminder'
            res = await db.all(query)

            # For each entry in the reminder table, check if now is greater than or equal to when that reminder needs to be sent by
            now = datetime.now()
            for id, guild_id, user_id, remind_on, message in res:
                if now >= remind_on:
                    # If it is time to send the reminder, then get the guild it was sent in so we can get the user to send it to
                    guild = self.bot.get_guild(guild_id)
                    user = guild.get_member(user_id)
                    msg = message

                    # If there is no reminder message, use the default one
                    if msg is None:
                        msg = self.DEFAULT_REMINDER_MESSAGE
                    
                    msg = f'{self.REMINDER_PREFIX}{msg}{self.REMINDER_SUFIX}'
                    # Encapsulate the reminder message in the prefix/sufix, and send it to the user

                    await user.send(msg)

                    # Get the record we just sent the message for, and delete it so it isn't sent again
                    row = await Reminders.query.where(Reminders.id == id).gino.first()
                    await row.delete()
            
            await asyncio.sleep(self.CHECK_EVERY)

def setup(bot):
    bot.add_cog(Reminder(bot))