import asyncio
import html
import io
import logging
import re
from asyncio import TimeoutError
from base64 import b64encode
from datetime import datetime, timedelta, timezone

import aiohttp
import disnake
from aiohttp import ClientTimeout
from aiohttp.client_exceptions import ClientConnectorError
from bs4 import BeautifulSoup
from disnake.ext import commands, tasks

from cogs.mixins import AceMixin
from config import (
    CLOUDAHK_PASS,
    CLOUDAHK_URL,
    CLOUDAHK_USER,
    DOCS_API_URL,
    GAME_PRED_URL,
)
from ids import *
from utils.html2markdown import HTML2Markdown
from utils.string import shorten

log = logging.getLogger(__name__)

NO_RESULTS_STRING = "No results"

AHK_COLOR = 0x95CD95
RSS_URL = "https://www.autohotkey.com/boards/feed"

DOCS_FMT = "https://www.autohotkey.com/docs/v{}/{}"
DOCS_NO_MATCH = commands.CommandError("Sorry, couldn't find an entry similar to that.")

SUGGESTION_PREFIX = "suggestion:"
UPVOTE_EMOJI = "\N{Thumbs Up Sign}"
DOWNVOTE_EMOJI = "\N{Thumbs Down Sign}"

INACTIVITY_LIMIT = timedelta(weeks=4)

DISCORD_UPLOAD_LIMIT = 8000000  # 8 MB

BULLET = "•"


def tag_string(tag):
    return (tag.emoji.name + " " if tag.emoji else "") + tag.name


class RunnableCodeConverter(commands.Converter):
    async def convert(self, ctx, code):
        if code.startswith("https://p.ahkscript.org/"):
            url = code.replace("?p=", "?r=")
            async with ctx.http.get(url) as resp:
                if resp.status == 200 and str(resp.url) == url:
                    code = await resp.text()
                else:
                    raise commands.CommandError("Failed fetching code from pastebin.")

        return code


def solved_perms(inter):
    if (
        not isinstance(inter.channel, disnake.Thread)
        or inter.channel.parent.id != HELP_FORUM_CHAN_ID
    ):
        raise commands.CommandError("This command should just be run in help channel posts.")

    if inter.author != inter.channel.owner:
        raise commands.CommandError("Only post author can mark as solved.")

    solved_tag = disnake.utils.get(inter.channel.parent.available_tags, name="Solved!")
    if solved_tag is None:
        raise commands.CommandError("Solved tag not found")
    return True


DEFAULT_PIVOT_VALUE = 0.0


class AutoHotkey(AceMixin, commands.Cog):
    """Commands for the AutoHotkey guild."""

    def __init__(self, bot):
        super().__init__(bot)

        self._msdn_cache = dict()

        self.h2m = HTML2Markdown(
            escaper=disnake.utils.escape_markdown,
            big_box=True,
            lang="autoit",
            max_len=512,
        )

        self.h2m_version = HTML2Markdown(
            escaper=disnake.utils.escape_markdown, big_box=False, max_len=512
        )

        self.forum_thread_channel = None
        self.rss_time = datetime.now(tz=timezone(timedelta(hours=1))) - timedelta(minutes=1)

        self._tag_reminder_message = dict()

        self.rss.start()
        self.close_help_threads.start()

        self._docs_msg_map = {}

    def cog_unload(self):
        self.rss.cancel()

    def parse_date(self, date_str):
        date_str = date_str.strip()
        return datetime.strptime(date_str[:-3] + date_str[-2:], "%Y-%m-%dT%H:%M:%S%z")

    async def classify(self, text):
        try:
            async with self.bot.aiohttp.post(GAME_PRED_URL, data=dict(q=text)) as resp:
                if resp.status != 200:
                    return DEFAULT_PIVOT_VALUE

                json = await resp.json()
                return json["p"]
        except aiohttp.ClientError:
            return DEFAULT_PIVOT_VALUE

    def make_classification_embed(self, score):
        s = (
            "Your scripting question looks like it might be about a game, which is not allowed here. "
            f"Please make sure you are familiar with the <#{RULES_CHAN_ID}>, specifically rule 5.\n\n"
            "If your question does not break the rules, you can safely ignore this message. "
            "If you continue and your question is later found to break the rules, you might risk a ban."
        )

        e = disnake.Embed(title="Hi there!", description=s, color=disnake.Color.orange())

        e.set_footer(
            text=f"This message was sent by an automated system (confidence: {int(score * 100)}%)"
        )

        return e

    @commands.Cog.listener()
    async def on_thread_create(self, thread: disnake.Thread):
        if thread.parent_id != HELP_FORUM_CHAN_ID:
            return

        content = [thread.name]

        async for message in thread.history():
            content.append(message.content)

        pivot = await self.classify(" ".join(content))

        await asyncio.sleep(2.0)
        if pivot >= 0.65:
            await thread.send(embed=self.make_classification_embed(pivot))
        else:
            if not thread.applied_tags:
                await self.tagask(thread)

    @tasks.loop(minutes=1)
    async def close_help_threads(self):
        await self.bot.wait_until_ready()

        forum: disnake.ForumChannel = self.bot.get_channel(HELP_FORUM_CHAN_ID)

        for thread in forum.threads:
            if thread.is_pinned() or thread.archived:
                continue

            base = disnake.utils.snowflake_time(thread.last_message_id or thread.id)
            delta = timedelta(minutes=thread.auto_archive_duration)
            base += delta
            now = disnake.utils.utcnow()

            if base < now:
                log.info("Archiving %s (auto archive duration: %s)", thread.name, delta)
                await thread.edit(archived=True, reason="Auto-expired.")

    @tasks.loop(minutes=14)
    async def rss(self):
        await self.bot.wait_until_ready()

        if self.forum_thread_channel is None:
            self.forum_thread_channel = self.bot.get_channel(FORUM_THRD_CHAN_ID)

            # if not forum thread channel found we can just gracefully stop this task from running
            if self.forum_thread_channel is None:
                self.rss.stop()
                return

        async with self.bot.aiohttp.request("get", RSS_URL) as resp:
            if resp.status != 200:
                return
            xml_rss = await resp.text("UTF-8")

        xml = BeautifulSoup(xml_rss, "xml")

        for entry in reversed(xml.find_all("entry")):
            time = self.parse_date(str(entry.updated.text))
            title = self.h2m.convert(str(entry.title.text))

            if time > self.rss_time and "• Re: " not in title:
                content = str(entry.content.text).split("Statistics: ")[0]
                content = self.h2m.convert(content)
                content = content.replace("\nCODE: ", "")

                e = disnake.Embed(
                    title=title,
                    description=content,
                    url=str(entry.id.text),
                    color=AHK_COLOR,
                )

                e.add_field(name="Author", value=str(entry.author.text))
                e.add_field(name="Forum", value=str(entry.category["label"]))
                e.set_footer(
                    text="autohotkey.com",
                    icon_url="https://www.autohotkey.com/favicon.ico",
                )
                e.timestamp = time

                if self.forum_thread_channel is not None:
                    await self.forum_thread_channel.send(embed=e)

                self.rss_time = time

    async def cloudahk_call(self, ctx, code, lang="ahk"):
        """Call to CloudAHK to run "code" written in "lang". Replies to invoking user with stdout/runtime of code."""

        token = "{0}:{1}".format(CLOUDAHK_USER, CLOUDAHK_PASS)

        encoded = b64encode(bytes(token, "utf-8")).decode("utf-8")
        headers = {"Authorization": "Basic " + encoded}

        # remove first line with backticks and highlighting lang
        if re.match("^```.*\n", code):
            code = code[code.find("\n") + 1 :]

        # strip backticks on both sides
        code = code.strip("`").strip()

        url = f"{CLOUDAHK_URL}/{lang}/run"

        # call cloudahk with 20 in timeout
        try:
            async with self.bot.aiohttp.post(
                url,
                data=code,
                headers=headers,
                timeout=ClientTimeout(total=10, connect=5),
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                else:
                    raise commands.CommandError("Something went wrong.")
        except ClientConnectorError:
            raise commands.CommandError(
                "I was unable to connect to the API. Please try again later."
            )
        except TimeoutError:
            raise commands.CommandError("I timed out. Please try again later.")

        stdout, time = result["stdout"].strip(), result["time"]

        file = None
        stdout = stdout.replace("\r", "")

        if time is None:
            resp = "Program ran for too long and was aborted."
        else:
            stdout_len = len(stdout)
            display_time = f"Runtime: `{time:.2f}` seconds"

            if stdout_len < 1800 and stdout.count("\n") < 20:
                # upload as plaintext
                stdout = stdout.replace("``", "`\u200b`")

                resp = "```ansi\n{0}\n```{1}".format(
                    stdout if stdout else "No output.", display_time
                )

            elif stdout_len < DISCORD_UPLOAD_LIMIT:
                fp = io.BytesIO(bytes(stdout.encode("utf-8")))
                file = disnake.File(fp, "output.txt")
                resp = f"Output dumped to file.\n{display_time}"

            else:
                raise commands.CommandError("Output greater than 8 MB.")

        # logging for security purposes and checking for abuse
        filename = "data/ahk_eval/{0}_{1}_{2}_{3}".format(
            ctx.guild.id, ctx.author.id, ctx.message.id, lang
        )
        with open(filename, "w", encoding="utf-8-sig") as f:
            f.write(
                "{0}\n\nLANG: {1}\n\nCODE:\n{2}\n\nPROCESSING TIME: {3}\n\nSTDOUT:\n{4}\n".format(
                    ctx.stamp, lang, code, time, stdout
                )
            )

        reference = ctx.message.to_reference()
        reference.fail_if_not_exists = False
        await ctx.send(content=resp, file=file, reference=reference)

    @commands.command()
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def ahk(self, ctx, *, code: RunnableCodeConverter):
        """Run AHK code through CloudAHK. Example: `ahk print("hello world!")`"""

        await self.cloudahk_call(ctx, code)

    @commands.Cog.listener()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id != "docsdeletebutton":
            return

        author_id = self._docs_msg_map.pop(inter.message.id, None)
        if author_id is None:
            return

        if author_id != inter.author.id:
            return

        await inter.message.delete()

    async def _docs(self, thing: commands.Context | disnake.AppCmdInter, sender, query, version):
        data = await self.query_docs_service(query, version)
        ar = disnake.ui.ActionRow()
        ar.add_button(0, style=disnake.ButtonStyle.danger, label="🗑️", custom_id="docsdeletebutton")
        msg = await sender(embed=self.craft_docs_page(data), components=[ar])

        if isinstance(thing, disnake.AppCmdInter):
            msg = await thing.original_message()

        self._docs_msg_map[msg.id] = thing.author.id

    @commands.command(name="docs", aliases=["d", "doc", "rtfm"])
    @commands.bot_has_permissions(embed_links=True)
    async def cmd_docs(self, ctx: commands.Context, *, query: str = None):
        """Search the AutoHotkey v1.1 documentation"""

        await self._docs(ctx, ctx.send, query, 1)

    @commands.slash_command(name="docs")
    async def slash_docs(self, inter: disnake.AppCmdInter, query: str):
        """Search the AutoHotkey v1.1 documentation."""

        await self._docs(inter, inter.response.send_message, query, 1)

    @commands.command(name="docs2", aliases=["d2", "doc2", "rtfm2"])
    @commands.bot_has_permissions(embed_links=True)
    async def cmd_docs2(self, ctx: commands.Context, *, query: str = None):
        """Search the AutoHotkey v2.0 documentation"""

        await self._docs(ctx, ctx.send, query, 2)

    @commands.slash_command(name="docs2")
    async def slash_docs2(self, inter: disnake.AppCmdInter, query: str):
        """Search the AutoHotkey v2.0 documentation."""

        await self._docs(inter, inter.response.send_message, query, 2)

    @slash_docs.autocomplete("query")
    async def docs_autocomplete(self, inter: disnake.AppCommandInter, query: str):
        return await self.search_docs(query, 1)

    @slash_docs2.autocomplete("query")
    async def docs_autocomplete(self, inter: disnake.AppCommandInter, query: str):
        return await self.search_docs(query, 2)

    async def search_docs(self, query, version):
        query = query.strip()

        async with self.bot.aiohttp.post(
            DOCS_API_URL + "/search",
            json=dict(v=version, q=query),
            timeout=aiohttp.ClientTimeout(total=4),
        ) as resp:
            if resp.status != 200:
                return ["ahkdocs api is down! :("]
            data = await resp.json()
            data = [e[:80] + "..." if len(e) > 80 else e for e in data]
            return data

    async def query_docs_service(self, query, version):
        async with self.bot.aiohttp.post(
            DOCS_API_URL + "/entry",
            json=dict(v=version, q=query),
            timeout=aiohttp.ClientTimeout(total=4),
        ) as resp:
            if resp.status != 200:
                raise commands.CommandError("ahkdocs api is down :((((")
            data = await resp.json()

        return data

    def craft_docs_page(self, data: dict):
        def link_list(entries, sep):
            parts = []
            for entry in entries:
                name = entry["name"]
                page = entry["page"]
                fragment = entry["fragment"]
                if fragment is not None:
                    page += f"#{fragment}"
                link = DOCS_FMT.format(v, page)
                parts.append(f"[{name}]({link})")
            return sep.join(parts)

        name = data["name"]
        search_match = data["search_match"]
        page = data.get("page")
        syntax = data["syntax"]
        content = data["content"]
        v = data["v"]
        version = data["version"]
        parents = data["parents"]
        children = data["children"]

        link = data.get("page")
        fragment = data.get("fragment")
        if fragment is not None:
            link += f"#{fragment}"

        desc = (content or "") + "\n"

        if syntax is not None:
            desc += f"```autoit\n{syntax}\n```"

        desc += "\n"

        if parents:
            if children:
                desc += "Part of: "
            desc += link_list(parents, f" {BULLET} ")
            desc += "\n"

        if children:
            if content is None:
                desc += "\n\n"
            else:
                desc += "Subsections: "
            desc += link_list(children, "\n" if content is None else f" {BULLET} ")

        e = disnake.Embed(
            title=search_match or name,
            description=desc.strip() or "No description for this page.",
            color=AHK_COLOR,
            url=page and DOCS_FMT.format(v, link),
        )

        return e

    async def _msdn_lookup(self, query, top=1):
        url = "https://docs.microsoft.com/api/search"

        params = {
            "filter": "category eq 'Documentation'",
            "locale": "en-us",
            "search": query,
            "$top": top,
        }

        async with self.bot.aiohttp.get(url, params=params, timeout=2) as resp:
            if resp.status != 200:
                raise commands.CommandError("Query failed.")

            json = await resp.json()

        return json

    def _make_msdn_embed(self, result):
        if result["description"] is None:
            description = "No description for this page."
        else:
            description = html.unescape(result["description"])

        e = disnake.Embed(
            title=html.unescape(result["title"]),
            description=description,
            color=AHK_COLOR,
            url=result["url"],
        )

        e.set_footer(text="docs.microsoft.com", icon_url="https://i.imgur.com/UvkNAEh.png")

        return e

    @commands.command()
    async def msdn(self, ctx, *, query):
        """Search Microsofts documentation."""

        result = self._msdn_cache.get(query, None)
        if result is None:
            json = await self._msdn_lookup(query, top=1)

            if "results" not in json or not json["results"]:
                raise commands.CommandError("No results.")

            result = json["results"][0]

        e = self._make_msdn_embed(result)

        await ctx.send(embed=e)

    @commands.slash_command(name="msdn")
    async def slash_msdn(self, inter: disnake.ApplicationCommandInteraction, query: str):
        """Search Microsofts documentation."""

        if query == NO_RESULTS_STRING:
            await inter.response.send_message("Search aborted!", ephemeral=True)
            return

        await self.msdn(inter, query=query)

    @slash_msdn.autocomplete(option_name="query")
    async def slash_msdn_autocomplete(
        self, inter: disnake.ApplicationCommandInteraction, query: str
    ):
        if not query:
            return [NO_RESULTS_STRING]

        json = await self._msdn_lookup(query, top=9)

        ret = []

        results = json["results"]
        for result in results:
            title = shorten(result["title"], 100)
            ret.append(title)
            self._msdn_cache[title] = result

        if not ret:
            ret.append(NO_RESULTS_STRING)

        return ret

    @commands.command()
    async def version(self, ctx):
        """Get changelog and download for the latest AutoHotkey_L version."""

        url = "https://api.github.com/repos/Lexikos/AutoHotkey_L/releases"

        async with ctx.http.get(url) as resp:
            if resp.status != 200:
                raise commands.CommandError("Query failed.")

            js = await resp.json()

        latest = js[0]
        asset = latest["assets"][0]

        content = self.h2m_version.convert(latest["body"])

        e = disnake.Embed(description=content, color=disnake.Color.green())

        e.set_author(
            name="AutoHotkey_L " + latest["name"],
            icon_url=latest["author"]["avatar_url"],
        )

        e.add_field(name="Release page", value=f"[Click here]({latest['html_url']})")
        e.add_field(
            name="Installer download",
            value=f"[Click here]({asset['browser_download_url']})",
        )
        e.add_field(name="Downloads", value=asset["download_count"])

        await ctx.send(embed=e)

    @commands.command(hidden=True)
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def ahk2(self, ctx, *, code: RunnableCodeConverter):
        """Run ahkv2 code."""

        await self.cloudahk_call(ctx, code, "ahk2")

    @commands.command(hidden=True)
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def rlx(self, ctx, *, code: RunnableCodeConverter):
        """Compile and run Relax code through CloudAHK. Example: `rlx define i32 Main() {return 20}`"""

        await self.cloudahk_call(ctx, code, "rlx")

    @commands.command(hidden=True)
    async def ask(self, ctx):
        await ctx.send(
            f"To ask a scripting question, create a new post in <#{HELP_FORUM_CHAN_ID}> "
            + f"or ask in any of the other help channels if their topic fit your problem: "
            + " ".join(f"<#{_id}>" for _id in HELP_CHANNEL_IDS)
        )

    @commands.slash_command(
        name="retag", description="Tag your help channel anew.", guild_ids=[AHK_GUILD_ID]
    )
    async def retag(self, inter: disnake.AppCmdInter):
        channel = inter.channel
        if not isinstance(channel, disnake.Thread):
            return

        thread = channel

        if thread.parent_id != HELP_FORUM_CHAN_ID:
            return

        if inter.author != thread.owner:
            return

        await self.tagask(thread, inter)

    async def tagask(self, thread: disnake.Thread, inter: disnake.AppCmdInter = None):
        message = None

        async def ask(question, tags: dict):
            nonlocal message
            embed = disnake.Embed()
            embed.set_author(
                name=self.bot.user.display_name,
                icon_url=self.bot.user.display_avatar.url,
            )
            embed.color = disnake.Color.green()

            embed.description = question

            rows = []

            for num, (label, tag) in enumerate(tags.items()):
                if num % 4 == 0:
                    row = disnake.ui.ActionRow()
                    rows.append(row)

                row.add_button(
                    style=disnake.ButtonStyle.secondary,
                    label=label,
                    emoji=tag.emoji,
                )

            row.add_button(
                style=disnake.ButtonStyle.grey,
                label="Skip",
            )

            args = dict(embed=embed, components=rows)

            if message is None:
                content = (
                    f"{thread.owner.mention} Increase your visibility by adding tags your post!"
                )
                if inter:
                    await inter.response.send_message(content=content, **args)
                    message = await inter.original_message()
                else:
                    message = await thread.send(content=content, **args)
            else:
                await message.edit(content=None, **args)

            def check(inter: disnake.MessageInteraction):
                if inter.author != thread.owner:
                    return False

                for components in inter.message.components:
                    if inter.component in components.children:
                        return True

                return False

            try:
                button_inter: disnake.MessageInteraction = await self.bot.wait_for(
                    event="button_click",
                    check=check,
                    timeout=300.0,  # if they haven't done anything in 5 minutes then timeout
                )
                await button_inter.response.defer()
            except asyncio.TimeoutError:
                return None

            return tags.get(button_inter.component.label, "Skip")

        tags = {tag.name: tag for tag in thread.parent.available_tags}
        added_tags: list[disnake.ForumTag] = []

        questions = (
            (
                "Which version of AHK are you using?",
                {"v1.1": tags["v1"], "v2.0": tags["v2"]},
            ),
            (
                "Which of these topics fit your question best? Skip if none apply.",
                {
                    "Sending keys/mouse": tags["Send/Click"],
                    "Hotkeys": tags["Hotkeys"],
                    "GUI": tags["GUI"],
                    "RegEx": tags["RegEx"],
                    "WinAPI": tags["WinAPI"],
                    "COM Objects": tags["COM Objects"],
                    "Object-Oriented": tags["Object-Oriented"],
                },
            ),
        )

        for question in questions:
            picked = await ask(*question)

            # None signifies a timeout
            # add whatever was picked, if anything
            if picked is None:
                break

            # add tag to list if we picked one
            # anything else, probably means a skip
            if isinstance(picked, disnake.ForumTag):
                added_tags.append(picked)

        # just delete and stop if we timed out
        if not added_tags:
            await message.delete()
            return

        await thread.edit(applied_tags=added_tags)

        content = "Thanks for tagging your post!\nYou can change the tags at any time by using `/retag`\n"

        if added_tags:
            content += "\n"
            for tag in added_tags:
                if tag.emoji:
                    content += f"- {tag.emoji} {tag.name}\n"
                else:
                    content += f"- {tag.name}\n"

        content += "\n**If your issue gets solved, you can mark your post as solved by sending `/solved`**"

        await message.edit(content=content, embed=None, components=None)

    @commands.slash_command(description="Mark your post as solved.", guild_ids=[AHK_GUILD_ID])
    @commands.check(solved_perms)
    async def solved(self, inter: disnake.AppCmdInter):
        solved_tag = disnake.utils.get(inter.channel.parent.available_tags, name="Solved!")

        try:
            await inter.send(
                "The post has been closed and given the solved tag. The post can be reopened at any time by sending a message. You can use `/unsolved` if the issue is no longer solved."
            )
        except disnake.HTTPException:
            pass

        add = dict()
        if solved_tag not in inter.channel.applied_tags:
            add["applied_tags"] = inter.channel.applied_tags + [solved_tag]

        await inter.channel.edit(archived=True, **add)

    @commands.slash_command(description="Unmark your post as solved.", guild_ids=[AHK_GUILD_ID])
    @commands.check(solved_perms)
    async def unsolved(self, inter: disnake.AppCmdInter):
        solved_tag = disnake.utils.get(inter.channel.parent.available_tags, name="Solved!")

        try:
            await inter.send(
                "The post has been opened and lost the solved tag. The post can be resolved at any time by using `/solved` again."
            )
        except disnake.HTTPException:
            pass

        await inter.channel.edit(
            archived=False,
            applied_tags=[tag for tag in inter.channel.applied_tags if tag != solved_tag],
        )

    def find_all_emoji(self, message, *, regex=re.compile(r"<a?:.+?:([0-9]{15,21})>")):
        return regex.findall(message.content)

    @commands.Cog.listener("on_message")
    async def handle_emoji_suggestion_message(self, message: disnake.Message):
        if message.guild is None or message.guild.id != AHK_GUILD_ID:
            return

        if message.channel.id != EMOJI_SUGGESTIONS_CHAN_ID:
            return

        if message.author.bot:
            return

        matches = self.find_all_emoji(message)

        async def delete(reason=None):
            # if await self.bot.is_owner(message.author):
            #     return

            try:
                await message.delete()
            except disnake.HTTPException:
                return

            if reason is not None:
                try:
                    await message.channel.send(
                        content=f"{message.author.mention} {reason}", delete_after=10
                    )
                except disnake.HTTPException:
                    pass

        if not matches and not message.attachments:
            return await delete("Your message has to contain an emoji suggestion.")

        elif message.attachments:
            # if more than one attachment, delete
            if len(message.attachments) > 1:
                return await delete("Please only send one attachment at a time.")

            attachment = message.attachments[0]
            if attachment.height is None:
                return await delete("Your attachment is not an image.")

            if attachment.height != attachment.width:
                return await delete("The attached image is not square.")

            if attachment.size > 256 * 1024:
                return await delete(
                    "The attached image is larger than the emoji size limit (256KB)."
                )

            if message.content:
                return await delete("Please do not put text in your suggestion.")

        else:
            if len(matches) > 1:
                return await delete("Please make sure your message only contains only one emoji.")

            if not re.match(r"^<a?:.+?:([0-9]{15,21})>$", message.content.strip()):
                return await delete("Please do not put text alongside your emoji suggestion.")

            match = int(matches[0])
            if any(emoji.id == match for emoji in message.guild.emojis):
                return await delete("Please do not suggest emojis that have already been added.")

        # Add voting reactions
        try:
            await message.add_reaction("✅")
            await message.add_reaction("❌")
        except disnake.Forbidden as e:
            # catch if we can't add the reactions
            # it could be that person is blocked, but it also could be that the bot doesn't have perms
            # we treat it the same since this is only used in the ahk discord.
            if e.text == "Reaction blocked":
                # runie: don't send error message to user since they have the bot blocked anyways.
                # people who block ace don't deserve answers to their misfortunes
                return await delete()

    @commands.Cog.listener("on_raw_message_edit")
    async def handle_emoji_suggestion_message_edit(self, message: disnake.RawMessageUpdateEvent):
        if message.channel_id == EMOJI_SUGGESTIONS_CHAN_ID:
            channel = self.bot.get_channel(EMOJI_SUGGESTIONS_CHAN_ID)
            if channel is None:
                return

            try:
                await channel.delete_messages([disnake.Object(message.message_id)])
            except disnake.HTTPException:
                pass

    @commands.Cog.listener("on_raw_reaction_add")
    async def handle_emoji_suggestion_reaction(self, reaction: disnake.RawReactionActionEvent):
        if reaction.channel_id != EMOJI_SUGGESTIONS_CHAN_ID:
            return

        if reaction.member.bot:
            return

        emoji = str(reaction.emoji)

        if emoji not in ("✅", "❌"):
            return

        channel: disnake.TextChannel = self.bot.get_channel(reaction.channel_id)
        if channel is None:
            return

        try:
            message: disnake.Message = await channel.fetch_message(reaction.message_id)
        except disnake.HTTPException:
            return

        # remove same emoji if from message author
        if message.author == reaction.member:
            try:
                await message.remove_reaction(emoji, reaction.member)
            except disnake.HTTPException:
                pass
        else:
            # remove opposite emoji if added
            remove_from = "✅" if emoji == "❌" else "❌"

            for reac in message.reactions:
                if str(reac.emoji) == remove_from:
                    try:
                        users = await reac.users().flatten()
                    except disnake.HTTPException:
                        return

                    if reaction.member in users:
                        try:
                            await message.remove_reaction(remove_from, reaction.member)
                        except disnake.HTTPException:
                            pass

                    return


def setup(bot):
    bot.add_cog(AutoHotkey(bot))
