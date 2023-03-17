import asyncio
import dataclasses
import logging
import string
from datetime import datetime
from enum import Enum
from random import choice, randrange, sample
from typing import Any, Literal, Optional, Union
from urllib.parse import unquote

import aiohttp
import disnake
from disnake.ext import commands
from rapidfuzz import fuzz, process

from cogs.mixins import AceMixin
from utils.configtable import ConfigTable

log = logging.getLogger(__name__)

REQUEST_FAILED = commands.CommandError("Request failed, try again later.")


# TRIVIA CONSTANTS


class Difficulty(Enum):
    EASY = 1
    MEDIUM = 2
    HARD = 3


TRIVIA_CUSTOM_ID_PREFIX = "trivia:v1:"

CORRECT_EMOJI = "\N{WHITE HEAVY CHECK MARK}"
WRONG_EMOJI = "\N{CROSS MARK}"

CORRECT_MESSAGES = (
    "Nice one!",
    "That's right!",
    "That one was easy, eh?",
    "Correct!",
)

WRONG_MESSAGES = (
    "Nope!",
    "Oof.",
    "Yikes.",
    "That one was hard.",
    "That was wrong!",
    "That wasn't easy.",
    "Afraid that's wrong!",
    "That's incorrect!",
)

FOOTER_FORMAT = "Score: {} • You can go again in 5 minutes."

DIFFICULTY_COLORS = {
    Difficulty.EASY: disnake.Color.blue(),
    Difficulty.MEDIUM: disnake.Color.from_rgb(212, 212, 35),
    Difficulty.HARD: disnake.Color.red(),
}

API_BASE = "https://opentdb.com/"
API_CATEGORY_LIST_URL = API_BASE + "api_category.php"
API_URL = API_BASE + "api.php"
QUESTION_TIMEOUT = 20.0

MULTIPLE_MAP = (
    "\N{Digit One}\N{Combining Enclosing Keycap}",
    "\N{Digit Two}\N{Combining Enclosing Keycap}",
    "\N{Digit Three}\N{Combining Enclosing Keycap}",
    "\N{Digit Four}\N{Combining Enclosing Keycap}",
)

BOOLEAN_MAP = (
    "\N{REGIONAL INDICATOR SYMBOL LETTER Y}",
    "\N{REGIONAL INDICATOR SYMBOL LETTER N}",
)

SCORE_POT = {Difficulty.EASY: 400, Difficulty.MEDIUM: 800, Difficulty.HARD: 1200}

PENALTY_DIV = 2
CATEGORY_PENALTY = 2.5

# NATO CONSTANTS

PHONETICS = (
    ("alpha", "alfa"),
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
    "india",
    ("juliet", "juliett"),
    "kilo",
    "lima",
    "mike",
    "november",
    "oscar",
    "papa",
    "quebec",
    "romeo",
    "sierra",
    "tango",
    "uniform",
    "victor",
    ("whiskey", "whisky"),
    ("x-ray", "xray"),
    "yankee",
    "zulu",
)

LETTERS = list(string.ascii_lowercase)
NATO = {x[0]: x[1] for x in zip(LETTERS, PHONETICS)}


@dataclasses.dataclass
class TriviaQuestion:
    type: Literal["multiple", "boolean"]
    category: str
    question: str
    hash: int = dataclasses.field(init=False)
    correct_answer: str
    difficulty: Difficulty
    incorrect_answers: list[str]
    _options: Optional[list] = dataclasses.field(init=False, default=None)
    _correct_emoji: Optional[str] = dataclasses.field(init=False, default=None)

    def __post_init__(self):
        if self.type not in ("multiple", "boolean"):
            raise ValueError("Unknown question type: {}".format(self.type))
        self.hash = hash(self.question)

    @classmethod
    def from_result(cls, res: dict, *, difficulty: Difficulty) -> "TriviaQuestion":
        question = unquote(res["question"])
        return cls(
            type=res["type"],
            category=unquote(res["category"]),
            correct_answer=unquote(res["correct_answer"]),
            incorrect_answers=list(unquote(ans) for ans in res["incorrect_answers"]),
            question=question,
            difficulty=difficulty,
        )

    @property
    def options(self) -> list[str]:
        if not self._options:
            if self.type == "multiple":
                options = list(self.incorrect_answers)
                correct_pos = randrange(0, len(options) + 1)
                options.insert(correct_pos, self.correct_answer)
                self._correct_emoji = MULTIPLE_MAP[correct_pos]

            elif self.type == "boolean":
                options = ["True", "False"]
                self._correct_emoji = BOOLEAN_MAP[int(self.correct_answer == "False")]
            else:
                raise RuntimeError
            self._options = options
        return self._options

    @property
    def buttons(self) -> list[disnake.ui.Button]:
        buttons = []
        longest_option = max(len(opt) for opt in self.options)
        for emoji, option in zip(self.option_emojis, self.options):
            buttons.append(
                disnake.ui.Button(
                    style=disnake.ButtonStyle.primary,
                    label=option,
                    custom_id=TRIVIA_CUSTOM_ID_PREFIX + "ans_choices:" + emoji,
                )
            )
        return buttons

    @property
    def correct_emoji(self) -> str:
        if not self._correct_emoji:
            self.options  # get the correct emoji
        return self._correct_emoji

    @property
    def option_emojis(self) -> tuple[str, ...]:
        return BOOLEAN_MAP if self.type == "boolean" else MULTIPLE_MAP

    def to_embed(self) -> disnake.Embed:
        question_string = "{}\n\n{}\n".format(
            self.question,
            "\n".join(
                "{} {}".format(emoji, option)
                for emoji, option in zip(self.option_emojis, self.options)
            ),
        )
        e = disnake.Embed(
            title="Trivia time!",
            description="**Category**: {}\n**Difficulty**: {}".format(
                self.category, self.difficulty.name.lower()
            ),
            color=DIFFICULTY_COLORS[self.difficulty],
        )
        e.add_field(name="Question", value=self.question, inline=False)
        return e


class CategoryConverter(commands.Converter):
    async def convert(self, ctx, argument):
        res, score, junk = process.extractOne(
            query=argument, choices=ctx.cog.trivia_categories.keys(), scorer=fuzz.ratio
        )

        if score < 76:
            # will never be shown so no need to prettify it
            raise ValueError()

        _id = ctx.cog.trivia_categories[res]
        return choice(_id) if isinstance(_id, list) else _id


class DifficultyConverter(commands.Converter):
    async def convert(self, ctx, argument):
        name = argument.upper()

        try:
            return Difficulty[name]
        except KeyError:
            pass

        try:
            return Difficulty(int(name))
        except ValueError:
            cleaner = commands.clean_content(escape_markdown=True)
            raise commands.CommandError(
                "'{}' is not a valid difficulty.".format(await cleaner.convert(ctx, name))
            )


class Games(AceMixin, commands.Cog):
    def __init__(self, bot):
        super().__init__(bot)

        self.config = ConfigTable(bot, "trivia", ("guild_id", "user_id"))

        self.trivia_categories: dict[str, Any] = {}

        self.bot.loop.create_task(self.get_trivia_categories())

    async def get_trivia_categories(self):
        try:
            async with self.bot.aiohttp.get(API_CATEGORY_LIST_URL) as resp:
                if resp.status != 200:
                    log.info("Failed getting trivia categories, trying again in 10 seconds...")
                    await asyncio.sleep(10)
                    asyncio.create_task(self.get_trivia_categories())
                    return

                res = await resp.json()
        except asyncio.TimeoutError:
            return

        categories = dict()

        for category in res["trivia_categories"]:
            name = category["name"].lower()

            if ":" in name:
                spl = name.split(":")
                cat = spl[0].strip()
                name = spl[1].strip()

                if cat not in categories:
                    categories[cat] = list()

                if isinstance(categories[cat], list):
                    categories[cat].append(category["id"])

            name = name.replace(" ", "_")

            categories[name] = category["id"]

        categories["anime"] = categories.pop("japanese_anime_&_manga")
        categories["science"].append(categories.pop("science_&_nature"))
        categories["musicals"] = categories.pop("musicals_&_theatres")
        categories["cartoons"] = categories.pop("cartoon_&_animations")

        self.trivia_categories = categories

    async def fetch_question(
        self,
        *,
        difficulty: Difficulty = Difficulty.MEDIUM,
        category: Optional[Union[str, list[str]]] = None,
    ):
        params = dict(
            amount=1,
            encode="url3986",
            difficulty=difficulty.name.lower(),
        )
        if category is not None:
            params["category"] = choice(category) if category is list else category
        try:
            async with self.bot.aiohttp.get(API_URL, params=params, raise_for_status=True) as resp:
                resp.raise_for_status()
                res = await resp.json()
        except (TimeoutError, aiohttp.ClientResponseError) as e:
            raise REQUEST_FAILED from e

        question = TriviaQuestion.from_result(res["results"][0], difficulty=difficulty)
        return question

    @commands.group(invoke_without_command=True, cooldown_after_parsing=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=2, per=60.0, type=commands.BucketType.member)
    async def trivia(
        self,
        ctx,
        category: Optional[CategoryConverter] = None,
        *,
        difficulty: DifficultyConverter = None,
    ):
        """Trivia time! Optionally specify a difficulty or category and difficulty as arguments. Valid difficulties are `easy`, `medium` and `hard`. Valid categories can be listed with `trivia categories`."""

        diff = difficulty

        if diff is None:
            diff = choice(list(Difficulty))

        # if we have a category ID, insert it into the query params for the question request

        try:
            question = await self.fetch_question(
                difficulty=diff,
                category=category,
            )
        except Exception:
            self.trivia.reset_cooldown(ctx)
            raise

        embed = question.to_embed()

        msg = await ctx.send(embed=embed, components=question.buttons)

        now = datetime.utcnow()

        def check(interaction: disnake.MessageInteraction):
            return (
                interaction.message.id == msg.id
                and interaction.author.id == ctx.author.id
                and (custom_id := interaction.data.custom_id).startswith(
                    TRIVIA_CUSTOM_ID_PREFIX + "ans_choices:"
                )
                and custom_id.removeprefix(TRIVIA_CUSTOM_ID_PREFIX + "ans_choices:")
                in question.option_emojis
            )

        try:
            interaction: disnake.MessageInteraction = await self.bot.wait_for(
                "message_interaction", check=check, timeout=QUESTION_TIMEOUT
            )

            answer = interaction.component.custom_id.removeprefix(
                TRIVIA_CUSTOM_ID_PREFIX + "ans_choices:"
            )

            answered_at = datetime.utcnow()
            score = self._calculate_score(SCORE_POT[diff], answered_at - now)

            if answer == question.correct_emoji:
                # apply penalty if category was specified
                if category:
                    score = int(score / CATEGORY_PENALTY)

                current_score = await self._on_correct(ctx, answered_at, question.hash, score)

                e = disnake.Embed(
                    title="{}  {}".format(CORRECT_EMOJI, choice(CORRECT_MESSAGES)),
                    description="You gained {} points.".format(score),
                    color=disnake.Color.green(),
                )

                # make the correct answer green and disable the buttons
                components = disnake.ui.ActionRow.rows_from_message(msg)
                for row in components:
                    for component in row:
                        component.disabled = True
                        if component.custom_id == interaction.component.custom_id:
                            component.style = disnake.ButtonStyle.green
                await interaction.response.edit_message(components=components)

                await interaction.followup.send(embed=e)
            else:
                score = int(score / PENALTY_DIV)
                current_score = await self._on_wrong(ctx, answered_at, question.hash, score)

                e = disnake.Embed(
                    title="{}  {}".format(WRONG_EMOJI, choice(WRONG_MESSAGES)),
                    description="You lost {} points.".format(score),
                    color=disnake.Color.red(),
                )

                if question.type == "multiple":
                    e.description += "\nThe correct answer is ***`{}`***".format(
                        question.correct_answer
                    )

                # make the correct answer green, the guessed answer red, and disable the buttons
                components = disnake.ui.ActionRow.rows_from_message(msg)
                for row in components:
                    for component in row:
                        component.disabled = True
                        if not isinstance(component, disnake.ui.Button):
                            continue
                        if component.custom_id == interaction.component.custom_id:
                            component.style = disnake.ButtonStyle.red
                        elif (
                            component.custom_id.removeprefix(
                                TRIVIA_CUSTOM_ID_PREFIX + "ans_choices:"
                            )
                            == question.correct_emoji
                        ):
                            component.style = disnake.ButtonStyle.green

                await interaction.response.edit_message(components=components)

                await interaction.followup.send(embed=e)

        except asyncio.TimeoutError:
            score = int(SCORE_POT[diff] / 4)
            answered_at = datetime.utcnow()

            components = disnake.ui.ActionRow.rows_from_message(msg)
            for row in components:
                for component in row:
                    if isinstance(component, disnake.ui.Button):
                        component.disabled = True
                        component.style = disnake.ButtonStyle.gray
            try:
                await msg.edit(components=components)
            except disnake.HTTPException:
                pass

            await msg.reply(
                "Question timed out and you lost {} points. Answer within {} seconds next time!".format(
                    score, int(QUESTION_TIMEOUT)
                ),
                fail_if_not_exists=False,
            )

            await self._on_wrong(ctx, answered_at, question.hash, score)

    def _calculate_score(self, pot, time_spent):
        time_div = QUESTION_TIMEOUT - time_spent.total_seconds() / 2
        points = pot * time_div / QUESTION_TIMEOUT
        return int(points)

    async def _on_correct(self, ctx, answered_at, question_hash, add_score):
        entry = await self.config.get_entry(ctx.guild.id, ctx.author.id)

        await entry.update(score=entry.score + add_score, correct_count=entry.correct_count + 1)
        await self._insert_question(ctx, answered_at, question_hash, True)

        return entry.score

    async def _on_wrong(self, ctx, answered_at, question_hash, remove_score):
        entry = await self.config.get_entry(ctx.guild.id, ctx.author.id)

        await entry.update(score=entry.score - remove_score, wrong_count=entry.wrong_count + 1)
        await self._insert_question(ctx, answered_at, question_hash, False)

        return entry.score

    async def _insert_question(self, ctx, answered_at, question_hash, result):
        await self.db.execute(
            "INSERT INTO trivia_stats (guild_id, user_id, timestamp, question_hash, result) VALUES ($1, $2, $3, $4, $5)",
            ctx.guild.id,
            ctx.author.id,
            answered_at,
            question_hash,
            result,
        )

    @trivia.command()
    @commands.bot_has_permissions(embed_links=True)
    async def categories(self, ctx):
        """Get a list of valid categories for the trivia command."""

        e = disnake.Embed(description="\n".join(self.trivia_categories.keys()))
        e.set_footer(text="Specifying a category halves your winnings.")

        await ctx.send(embed=e)

    @trivia.command()
    @commands.bot_has_permissions(embed_links=True)
    async def stats(self, ctx, *, member: disnake.Member = None):
        """Get your own or another members' trivia stats."""

        member = member or ctx.author

        entry = await self.config.get_entry(ctx.guild.id, member.id)

        total_games = entry.correct_count + entry.wrong_count

        if total_games == 0:
            win_rate = 0
        else:
            win_rate = int(entry.correct_count / total_games * 100)

        e = disnake.Embed()

        e.set_author(name=member.display_name, icon_url=member.display_avatar.url)

        e.add_field(name="Score", value=str(entry.score))
        e.add_field(name="Correct", value="{} games".format(str(entry.correct_count)))
        e.add_field(name="Wrong", value="{} games".format(str(entry.wrong_count)))
        e.add_field(name="Games played", value="{} games".format(str(total_games)))
        e.add_field(name="Correct percentage", value="{}%".format(str(win_rate)))

        await ctx.send(embed=e)

    @trivia.command()
    @commands.bot_has_permissions(embed_links=True)
    async def ranks(self, ctx):
        """See trivia leaderboard."""

        leaders = await self.db.fetch(
            "SELECT * FROM trivia WHERE guild_id=$1 ORDER BY score DESC LIMIT 8",
            ctx.guild.id,
        )

        e = disnake.Embed(title="Trivia leaderboard", color=DIFFICULTY_COLORS[Difficulty.MEDIUM])

        mentions = "\n".join("<@{}>".format(leader.get("user_id")) for leader in leaders)
        scores = "\n".join(str(leader.get("score")) for leader in leaders)

        e.add_field(name="User", value=mentions)
        e.add_field(name="Score", value=scores)

        await ctx.send(embed=e)

    @commands.command()
    async def nato(self, ctx, count: int = 3):
        """Learn the NATO phonetic alphabet."""

        if count < 1:
            raise commands.CommandError("Please pick a length larger than 0.")

        if count > 16:
            raise commands.CommandError("Sorry, please pick lengths lower or equal to 16.")

        lets = sample(LETTERS, k=count)

        await ctx.send(f'**{"".join(lets).upper()}**?')

        def check(m):
            return m.channel == ctx.channel and m.author == ctx.author

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=60.0)
        except asyncio.TimeoutError:
            await ctx.send(f"Sorry {ctx.author.mention}, time ran out!")
            return

        answer = msg.content.lower().split()

        async def failed():
            right = []
            for let in lets:
                asd = NATO[let]
                right.append(asd[0] if isinstance(asd, tuple) else asd)
            await ctx.send(
                f'Sorry, that was wrong! The correct answer was `{" ".join(right).upper()}`'
            )

        if len(answer) != len(lets):
            return await failed()

        for index, part in enumerate(answer):
            answer = NATO[lets[index]]
            if isinstance(answer, tuple):
                if part not in answer:
                    return await failed()
            else:
                if part != answer:
                    return await failed()

        await ctx.send("Correct! ✅")


def setup(bot):
    bot.add_cog(Games(bot))
