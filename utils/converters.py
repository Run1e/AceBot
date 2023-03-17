import re
from inspect import Parameter

import disnake
import emoji
from disnake.ext import commands

from .fakeuser import FakeUser

empty = Parameter.empty


def param_name(converter, ctx):
    fallback = "Argument"

    for param_name, parameter in ctx.command.params.items():
        param_conv = parameter.annotation

        if param_conv == empty:
            continue

        if param_conv is converter:
            return param_name

    return fallback


def _make_int(converter, ctx, argument):
    try:
        return int(argument)
    except ValueError:
        name = param_name(converter, ctx)
        raise commands.BadArgument(f"{name} should be a number.")


class MaybeMemberConverter(commands.MemberConverter):
    async def resolve_id(self, ctx, member_id):
        member = ctx.guild.get_member(member_id)
        if member is not None:
            return member

        try:
            return await ctx.guild.fetch_member(member_id)
        except disnake.HTTPException:
            return FakeUser(member_id, ctx.guild)

    async def convert(self, ctx, argument):
        try:
            return await super().convert(ctx, argument)
        except commands.BadArgument as exc:
            # handles pure id's
            if argument.isdigit():
                return await self.resolve_id(ctx, int(argument))

            # handles mentions
            match = re.match(r"<@!?([0-9]+)>$", argument)
            if match is not None:
                return await self.resolve_id(ctx, int(match.group(1)))

            raise exc


class EmojiConverter(commands.Converter):
    async def convert(self, ctx, argument):
        guild_emojis = list(str(e) for e in ctx.guild.emojis)

        if argument not in emoji.UNICODE_EMOJI["en"]:
            if argument not in guild_emojis:
                raise commands.BadArgument("Unknown emoji.")

        return argument


class MaxValueConverter(commands.Converter):
    def __init__(self, _max):
        self.max = _max

    async def convert(self, ctx, argument):
        value = _make_int(self, ctx, argument)

        if value > self.max:
            name = param_name(self, ctx)
            raise commands.BadArgument(f"{name} must be lower than {self.max}")

        return value


class SerialConverter(commands.Converter):
    MAX = pow(2, 31) - 1

    async def convert(self, ctx, argument):
        value = _make_int(self, ctx, argument)

        if value > self.MAX:
            name = param_name(self, ctx)
            raise commands.BadArgument(f"{name} must be a lower value.")

        return value


class RangeConverter(commands.Converter):
    def __init__(self, min, max):
        self.min = min
        self.max = max

    def _make_error(self, ctx):
        name = param_name(self, ctx)
        return commands.BadArgument(f"{name} must be between {self.min} and {self.max}")

    async def convert(self, ctx, argument):
        value = _make_int(self, ctx, argument)

        if value < self.min:
            raise self._make_error(ctx)

        if value > self.max:
            raise self._make_error(ctx)

        return value


class LengthConverter(commands.Converter):
    def __init__(self, min=1, max=32):
        self.min = min
        self.max = max

    def _make_error(self, ctx):
        name = param_name(self, ctx)
        return commands.BadArgument(f"{name} must be between {self.min} and {self.max} characters.")

    async def convert(self, ctx, argument):
        length = len(argument)

        if length < self.min:
            raise self._make_error(ctx)

        if length > self.max:
            raise self._make_error(ctx)

        return argument


class MaxLengthConverter(commands.Converter):
    def __init__(self, max=32):
        self.max = max

    async def convert(self, ctx, argument):
        length = len(argument)

        if length > self.max:
            name = param_name(self, ctx)
            raise commands.BadArgument(f"{name} must be shorter than {self.max} characters.")

        return argument
