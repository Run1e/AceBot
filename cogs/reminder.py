import discord
from discord.ext import commands
import datetime
import asyncio

from utils.database import db, Reminders
from cogs.base import TogglableCogMixin

class Reminder(TogglableCogMixin):
    
    SUCCESS_EMOJI = '\U00002705'
    FAIL_EMOJI = '\U0000274C'
    CHECK_EVERY = 60
    DEFAULT_REMINDER_MESSAGE = 'Hey, wake up!'
    REMINDER_PREFIX = 'Reminder:```'
    REMINDER_SUFIX = '```'

    def __init__(self, bot):
        super().__init__(bot)
        self.bot.loop.create_task(self.check_reminders())

    @commands.command(aliases=['remindme', 'Remindme', 'remindMe', 'reminder'])
    async def RemindMe(self, ctx, amount:int, unit: str = None, *message):
        if unit is None:
            unit = 'minute' # If a unit isn't passed, assume minutes
        if unit[-1] == 's':
            unit = unit[0:-1] # If a unit is passed, but plural, remove the "s" at the end

        msg = ''
        for part in message:
            msg = f'{msg} {part}' # Combine n unquotes words of the message into one string

        units = {'minute':60, 'hour':60 * 60, 'day': 60 * 60 * 24} # Get a multiplier for the unit to multiply the amount by to get a time in seconds

        try:
            seconds = int(amount) * units[unit] # Try to get the mult for the unit, if it fails then an invalid unit was passed and we can throw a UnitError
        except KeyError:
            await ctx.message.add_reaction(self.FAIL_EMOJI)
            raise self.UnitError(unit) # I could make it assume minutes here and use the third param onward as a message, but that might get messy
        
        time = datetime.datetime.now() + datetime.timedelta(seconds=seconds) # Create a datetime object of the current time, and add how long to wait before reminding to it
        
        await Reminders.create(
            server_id = ctx.guild.id,
            user_id = ctx.author.id,
            remind_on = time,
            message = msg
        )
        # Add the reminder to the DB

        await ctx.message.add_reaction(self.SUCCESS_EMOJI)

    async def check_reminders(self):
        while True:
            query = 'SELECT * FROM reminders'
            res = await db.all(query)

            # For each entry in the reminder table, check if now is greater than or equal to when that reminder needs to be sent by
            for reminder_entry in res:
                if datetime.datetime.now() >= reminder_entry[3]:
                    # If it is time to send the reminder, then get the guild it was sent in so we can get the user to send it to
                    guild = self.bot.get_guild(reminder_entry[1])
                    user = guild.get_member(reminder_entry[2])
                    msg = reminder_entry[4]

                    # If there is no reminder message, use the default one
                    if msg is None:
                        msg = self.DEFAULT_REMINDER_MESSAGE
                    
                    msg = f'{self.REMINDER_PREFIX}{msg}{self.REMINDER_SUFIX}'
                    # Encapsulate the reminder message in the prefix/sufix, and send it to the user

                    await user.send(msg)

                    # Get the record we just sent the message for, and delete it so it isn't sent again
                    row = await Reminders.query.where(Reminders.id == reminder_entry[0]).gino.first()
                    await row.delete()
            
            await asyncio.sleep(self.CHECK_EVERY)

    class UnitError(Exception):
        def __init__(self, unit):
            self.unit = unit

        def __str__(self):
            return f'Unit must be "day(s)", "hour(s)", or "minute(s)", not "{self.unit}"'

def setup(bot):
    bot.add_cog(Reminder(bot))