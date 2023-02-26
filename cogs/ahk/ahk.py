import asyncio
import html
import io
import logging
import re
from asyncio import TimeoutError
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from random import choices

import aiohttp
import disnake
from aiohttp import ClientTimeout
from aiohttp.client_exceptions import ClientConnectorError
from bs4 import BeautifulSoup
from disnake.ext import commands, tasks
from rapidfuzz import fuzz, process

from cogs.mixins import AceMixin
from config import CLOUDAHK_PASS, CLOUDAHK_URL, CLOUDAHK_USER, GAME_PRED_URL
from ids import *
from utils.docs_parser import parse_docs, DOCS_URL
from utils.html2markdown import HTML2Markdown
from utils.string import shorten

log = logging.getLogger(__name__)

NO_RESULTS_STRING = 'No results'

AHK_COLOR = 0x95CD95
RSS_URL = 'https://www.autohotkey.com/boards/feed'

DOCS_FORMAT = f'{DOCS_URL}{{}}'
DOCS_NO_MATCH = commands.CommandError('Sorry, couldn\'t find an entry similar to that.')

SUGGESTION_PREFIX = 'suggestion:'
UPVOTE_EMOJI = '\N{Thumbs Up Sign}'
DOWNVOTE_EMOJI = '\N{Thumbs Down Sign}'

INACTIVITY_LIMIT = timedelta(weeks=4)

DISCORD_UPLOAD_LIMIT = 8000000  # 8 MB

SEARCH_COUNT = 8


class RunnableCodeConverter(commands.Converter):
    async def convert(self, ctx, code):
        if code.startswith('https://p.ahkscript.org/'):
            url = code.replace('?p=', '?r=')
            async with ctx.http.get(url) as resp:
                if resp.status == 200 and str(resp.url) == url:
                    code = await resp.text()
                else:
                    raise commands.CommandError('Failed fetching code from pastebin.')

        return code


DEFAULT_PIVOT_VALUE = 0.0


class AutoHotkey(AceMixin, commands.Cog):
    '''Commands for the AutoHotkey guild.'''

    def __init__(self, bot):
        super().__init__(bot)

        self._msdn_cache = dict()

        self.h2m = HTML2Markdown(
            escaper=disnake.utils.escape_markdown,
            big_box=True,
            lang='autoit',
            max_len=512,
        )

        self.h2m_version = HTML2Markdown(
            escaper=disnake.utils.escape_markdown, big_box=False, max_len=512
        )

        self.forum_thread_channel = None
        self.rss_time = datetime.now(tz=timezone(timedelta(hours=1))) - timedelta(
            minutes=1
        )

        self._tag_reminder_message = dict()

        self.rss.start()
        self.close_help_threads.start()

        asyncio.create_task(self._build_docs_cache())

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
                return json['p']
        except aiohttp.ClientError:
            return DEFAULT_PIVOT_VALUE

    def make_classification_embed(self, score):
        s = (
            'Your scripting question looks like it might be about a game, which is not allowed here. '
            f'Please make sure you are familiar with the <#{RULES_CHAN_ID}>, specifically rule 5.\n\n'
            'If your question does not break the rules, you can safely ignore this message. '
            'If you continue and your question is later found to break the rules, you might risk a ban.'
        )

        e = disnake.Embed(
            title='Hi there!', description=s, color=disnake.Color.orange()
        )

        e.set_footer(
            text=f'This message was sent by an automated system (confidence: {int(score * 100)}%)'
        )

        return e

    @commands.Cog.listener()
    async def on_thread_create(self, thread: disnake.Thread):
        if thread.parent_id != HELP_FORUM_CHAN_ID:
            return

        content = [thread.name]

        async for message in thread.history():
            content.append(message.content)

        pivot = await self.classify(' '.join(content))

        await asyncio.sleep(2.0)
        if pivot >= 0.65:
            await thread.send(embed=self.make_classification_embed(pivot))
        else:
            self._tag_reminder_message[thread.id] = await thread.send(
                f'{thread.owner.mention} You can tag your post using the `/tagme` command to make it easier for others to help.'
            )

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
                log.info('Archiving %s (auto archive duration: %s)', thread.name, delta)
                await thread.edit(archived=True, reason='Auto-expired.')

    @tasks.loop(minutes=14)
    async def rss(self):
        await self.bot.wait_until_ready()

        if self.forum_thread_channel is None:
            self.forum_thread_channel = self.bot.get_channel(FORUM_THRD_CHAN_ID)

            # if not forum thread channel found we can just gracefully stop this task from running
            if self.forum_thread_channel is None:
                self.rss.stop()
                return

        async with self.bot.aiohttp.request('get', RSS_URL) as resp:
            if resp.status != 200:
                return
            xml_rss = await resp.text('UTF-8')

        xml = BeautifulSoup(xml_rss, 'xml')

        for entry in reversed(xml.find_all('entry')):

            time = self.parse_date(str(entry.updated.text))
            title = self.h2m.convert(str(entry.title.text))

            if time > self.rss_time and '• Re: ' not in title:
                content = str(entry.content.text).split('Statistics: ')[0]
                content = self.h2m.convert(content)
                content = content.replace('\nCODE: ', '')

                e = disnake.Embed(
                    title=title,
                    description=content,
                    url=str(entry.id.text),
                    color=AHK_COLOR,
                )

                e.add_field(name='Author', value=str(entry.author.text))
                e.add_field(name='Forum', value=str(entry.category['label']))
                e.set_footer(
                    text='autohotkey.com',
                    icon_url='https://www.autohotkey.com/favicon.ico',
                )
                e.timestamp = time

                if self.forum_thread_channel is not None:
                    await self.forum_thread_channel.send(embed=e)

                self.rss_time = time

    async def cloudahk_call(self, ctx, code, lang='ahk'):
        '''Call to CloudAHK to run "code" written in "lang". Replies to invoking user with stdout/runtime of code.'''

        token = '{0}:{1}'.format(CLOUDAHK_USER, CLOUDAHK_PASS)

        encoded = b64encode(bytes(token, 'utf-8')).decode('utf-8')
        headers = {'Authorization': 'Basic ' + encoded}

        # remove first line with backticks and highlighting lang
        if re.match('^```.*\n', code):
            code = code[code.find('\n') + 1 :]

        # strip backticks on both sides
        code = code.strip('`').strip()

        url = f'{CLOUDAHK_URL}/{lang}/run'

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
                    raise commands.CommandError('Something went wrong.')
        except ClientConnectorError:
            raise commands.CommandError(
                'I was unable to connect to the API. Please try again later.'
            )
        except TimeoutError:
            raise commands.CommandError('I timed out. Please try again later.')

        stdout, time = result['stdout'].strip(), result['time']

        file = None
        stdout = stdout.replace('\r', '')

        if time is None:
            resp = 'Program ran for too long and was aborted.'
        else:
            stdout_len = len(stdout)
            display_time = f'Runtime: `{time:.2f}` seconds'

            if stdout_len < 1800 and stdout.count('\n') < 20:
                # upload as plaintext
                stdout = stdout.replace('``', '`\u200b`')

                resp = '```ansi\n{0}\n```{1}'.format(
                    stdout if stdout else 'No output.', display_time
                )

            elif stdout_len < DISCORD_UPLOAD_LIMIT:
                fp = io.BytesIO(bytes(stdout.encode('utf-8')))
                file = disnake.File(fp, 'output.txt')
                resp = f'Output dumped to file.\n{display_time}'

            else:
                raise commands.CommandError('Output greater than 8 MB.')

        # logging for security purposes and checking for abuse
        filename = 'ahk_eval/{0}_{1}_{2}_{3}'.format(
            ctx.guild.id, ctx.author.id, ctx.message.id, lang
        )
        with open(filename, 'w', encoding='utf-8-sig') as f:
            f.write(
                '{0}\n\nLANG: {1}\n\nCODE:\n{2}\n\nPROCESSING TIME: {3}\n\nSTDOUT:\n{4}\n'.format(
                    ctx.stamp, lang, code, time, stdout
                )
            )

        reference = ctx.message.to_reference()
        reference.fail_if_not_exists = False
        await ctx.send(content=resp, file=file, reference=reference)

    @commands.command()
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def ahk(self, ctx, *, code: RunnableCodeConverter):
        '''Run AHK code through CloudAHK. Example: `ahk print("hello world!")`'''

        await self.cloudahk_call(ctx, code)

    @commands.command(name='docs', aliases=['d', 'doc', 'rtfm'])
    @commands.bot_has_permissions(embed_links=True)
    async def cmd_docs(self, ctx: commands.Context, *, query: str = None):
        '''Search the AutoHotkey documentation. Enter multiple queries by separating with commas.'''

        if query is None:
            await ctx.send(DOCS_FORMAT.format(''))
            return

        spl = dict.fromkeys(sq.strip() for sq in query.lower().split(','))

        if len(spl) > 3:
            raise commands.CommandError('Maximum three different queries.')

        embeds = []
        for subquery in spl.keys():
            name = self.search_docs(subquery, k=1)[0]
            result = await self.get_doc(self._docs_id[name], entry=True, syntax=True)

            if not result:
                if len(spl.keys()) == 1:
                    raise DOCS_NO_MATCH
                else:
                    continue

            embeds.append(self.craft_docs_page(result, force_name=name))

        await ctx.send(embeds=embeds)

    @commands.slash_command(name='docs')
    async def slash_docs(self, inter, query: str):
        '''Search AutoHotkey documentation.'''

        _id = self._docs_id.get(query, None)

        # if this query wasn't picked from the autocomplete, do a search on the freetext query submitted
        if _id is None:
            query = self.search_docs(query, k=1)[0]

        record = await self.get_doc(self._docs_id[query], entry=True, syntax=True)

        await inter.response.send_message(
            embed=self.craft_docs_page(record, force_name=query)
        )

    @slash_docs.autocomplete('query')
    async def docs_autocomplete(self, inter: disnake.AppCommandInter, query: str):
        return self.search_docs(query, k=SEARCH_COUNT, make_default=True)

    def search_docs(self, query, k=8, make_default=False):
        query = query.strip().lower()

        if not query:
            return choices(self._docs_names, k=k) if make_default else None

        # further fuzzy search it using rapidfuzz ratio matching
        fuzzed = process.extract(
            query=query,
            choices=self._docs_names,
            scorer=fuzz.ratio,
            processor=None,
            limit=max(k, 8),
        )

        tweak = list()

        for idx, (name, score, junk) in enumerate(fuzzed):
            lower = name.lower()

            if lower == query:
                score += 50

            if query in lower:
                score += 20

            tweak.append((name, score))

        tweak = list(sorted(tweak, key=lambda v: v[1], reverse=True))

        return list(name for name, score in tweak)[:k]

    async def _build_docs_cache(self):
        records = await self.db.fetch(
            'SELECT docs_entry.id, name, content FROM docs_name INNER JOIN docs_entry ON docs_name.docs_id = docs_entry.id'
        )

        self._docs_names = list(record.get('name') for record in records)
        self._docs_id = {record.get('name'): record.get('id') for record in records}

    async def get_doc(self, id, entry=False, syntax=False):
        sql = 'SELECT * FROM docs_name '

        if entry:
            sql += 'INNER JOIN docs_entry ON docs_name.docs_id = docs_entry.id '

        if syntax:
            sql += 'LEFT OUTER JOIN docs_syntax ON docs_name.docs_id = docs_syntax.docs_id '

        sql += 'WHERE docs_entry.id = $1'

        return await self.db.fetchrow(sql, id)

    def craft_docs_page(self, record, force_name=None):
        page = record.get('page')

        e = disnake.Embed(
            title=record.get('name') if force_name is None else force_name,
            description=record.get('content') or 'No description for this page.',
            color=AHK_COLOR,
            url=page and DOCS_FORMAT.format(record.get('link')),
        )

        e.set_footer(
            text='autohotkey.com', icon_url='https://www.autohotkey.com/favicon.ico'
        )

        syntax = record.get('syntax')
        if syntax is not None:
            e.description += '\n```autoit\n{}\n```'.format(syntax)

        return e

    @commands.command(hidden=True)
    @commands.is_owner()
    async def build(self, ctx, download: bool = True):
        log.info('Starting documentation build job. Download=%s', download)

        async def on_update(text):
            log.info('Build job: %s', text)
            await ctx.send(text)

        try:
            agg = await parse_docs(on_update, fetch=download, loop=ctx.bot.loop)
        except Exception as exc:
            raise commands.CommandError(str(exc))

        await on_update('Building tables...')

        await self.db.execute(
            'TRUNCATE docs_name, docs_syntax, docs_entry RESTART IDENTITY'
        )

        async for entry in agg:
            names = entry.pop('names')
            link = entry.pop('page')
            desc = entry.pop('desc')
            syntax = entry.pop('syntax', None)

            if link is None:
                page = None
                fragment = None
            else:
                split = link.split('/')
                split = split[len(split) - 1].split('#')
                page = split.pop(0)[:-4]
                fragment = split.pop(0) if split else None

            docs_id = await self.db.fetchval(
                'INSERT INTO docs_entry (content, link, page, fragment, title) VALUES ($1, $2, $3, $4, $5) '
                'RETURNING id',
                desc,
                link,
                page,
                fragment,
                entry['main'],
            )

            for name in names:
                await self.db.execute(
                    'INSERT INTO docs_name (docs_id, name) VALUES ($1, $2)',
                    docs_id,
                    name,
                )

            if syntax is not None:
                await self.db.execute(
                    'INSERT INTO docs_syntax (docs_id, syntax) VALUES ($1, $2)',
                    docs_id,
                    syntax,
                )

        await self._build_docs_cache()
        await on_update('Done!')

    async def _msdn_lookup(self, query, top=1):
        url = 'https://docs.microsoft.com/api/search'

        params = {
            'filter': "category eq 'Documentation'",
            'locale': 'en-us',
            'search': query,
            '$top': top,
        }

        async with self.bot.aiohttp.get(url, params=params, timeout=2) as resp:
            if resp.status != 200:
                raise commands.CommandError('Query failed.')

            json = await resp.json()

        return json

    def _make_msdn_embed(self, result):
        if result['description'] is None:
            description = 'No description for this page.'
        else:
            description = html.unescape(result['description'])

        e = disnake.Embed(
            title=html.unescape(result['title']),
            description=description,
            color=AHK_COLOR,
            url=result['url'],
        )

        e.set_footer(
            text='docs.microsoft.com', icon_url='https://i.imgur.com/UvkNAEh.png'
        )

        return e

    @commands.command()
    async def msdn(self, ctx, *, query):
        '''Search Microsofts documentation.'''

        result = self._msdn_cache.get(query, None)
        if result is None:
            json = await self._msdn_lookup(query, top=1)

            if 'results' not in json or not json['results']:
                raise commands.CommandError('No results.')

            result = json['results'][0]

        e = self._make_msdn_embed(result)

        await ctx.send(embed=e)

    @commands.slash_command(name='msdn')
    async def slash_msdn(
        self, inter: disnake.ApplicationCommandInteraction, query: str
    ):
        '''Search Microsofts documentation.'''

        if query == NO_RESULTS_STRING:
            await inter.response.send_message('Search aborted!', ephemeral=True)
            return

        await self.msdn(inter, query=query)

    @slash_msdn.autocomplete(option_name='query')
    async def slash_msdn_autocomplete(
        self, inter: disnake.ApplicationCommandInteraction, query: str
    ):
        if not query:
            return [NO_RESULTS_STRING]

        json = await self._msdn_lookup(query, top=9)

        ret = []

        results = json['results']
        for result in results:
            title = shorten(result['title'], 100)
            ret.append(title)
            self._msdn_cache[title] = result

        if not ret:
            ret.append(NO_RESULTS_STRING)

        return ret

    @slash_msdn.error
    async def slash_msdn_error(self, inter: disnake.CommandInteraction, exc):
        if isinstance(exc, commands.CommandError):
            await inter.send(embed=disnake.Embed(description=str(exc)), ephemeral=True)

    @commands.command()
    async def version(self, ctx):
        '''Get changelog and download for the latest AutoHotkey_L version.'''

        url = 'https://api.github.com/repos/Lexikos/AutoHotkey_L/releases'

        async with ctx.http.get(url) as resp:
            if resp.status != 200:
                raise commands.CommandError('Query failed.')

            js = await resp.json()

        latest = js[0]
        asset = latest['assets'][0]

        content = self.h2m_version.convert(latest['body'])

        e = disnake.Embed(description=content, color=disnake.Color.green())

        e.set_author(
            name='AutoHotkey_L ' + latest['name'],
            icon_url=latest['author']['avatar_url'],
        )

        e.add_field(name='Release page', value=f"[Click here]({latest['html_url']})")
        e.add_field(
            name='Installer download',
            value=f"[Click here]({asset['browser_download_url']})",
        )
        e.add_field(name='Downloads', value=asset['download_count'])

        await ctx.send(embed=e)

    @commands.command(hidden=True)
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def ahk2(self, ctx, *, code: RunnableCodeConverter):
        '''Run ahkv2 code.'''

        await self.cloudahk_call(ctx, code, 'ahk2')

    @commands.command(hidden=True)
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def rlx(self, ctx, *, code: RunnableCodeConverter):
        '''Compile and run Relax code through CloudAHK. Example: `rlx define i32 Main() {return 20}`'''

        await self.cloudahk_call(ctx, code, 'rlx')

    @commands.command(hidden=True)
    async def ask(self, ctx):
        await ctx.send(
            f'To ask a scripting question, create a new post in <#{HELP_FORUM_CHAN_ID}> ' +
            f'or ask in any of the other help channels if their topic fit your problem: ' +
            ' '.join(f'<#{_id}>' for _id in HELP_CHANNEL_IDS)
        )

    @commands.slash_command(description='Add tags to your help post.')
    async def tagme(self, inter: disnake.AppCmdInter):
        if not isinstance(inter.channel, disnake.Thread) or inter.channel.parent.id != HELP_FORUM_CHAN_ID:
            raise commands.CommandError('This command should just be run in help channel posts.')

        if inter.author != inter.channel.owner:
            raise commands.CommandError('Only post author can add tags.')

        async def ask(question, tags: dict):
            embed = disnake.Embed()
            embed.set_author(name=inter.bot.user.display_name, icon_url=inter.bot.user.display_avatar.url)
            embed.color = disnake.Color.green()

            embed.description = question

            rows = []

            for num, (label, tag) in enumerate(tags.items()):
                if num % 4 == 0:
                    row = disnake.ui.ActionRow()
                    rows.append(row)

                row.add_button(
                    style=disnake.ButtonStyle.primary,
                    label=label,
                    emoji=tag.emoji,
                )

            row.add_button(
                style=disnake.ButtonStyle.secondary,
                label='Skip',
            )

            args = dict(embed=embed, components=rows)

            if not inter.response.is_done():
                await inter.send(**args, ephemeral=True)
            else:
                await inter.edit_original_response(**args)

            def check(inter: disnake.MessageInteraction):
                for components in inter.message.components:
                    if inter.component in components.children:
                        return True
                return False

            try:
                button_inter: disnake.MessageInteraction = await self.bot.wait_for(
                    event='button_click', check=check, timeout=120.0,
                )
                await button_inter.response.defer()
            except asyncio.TimeoutError:
                raise commands.CommandError('Timed out. Please invoke again to tag post.')

            return tags.get(button_inter.component.label, None)

        tags = {tag.name: tag for tag in inter.channel.parent.available_tags}
        added_tags = []

        questions = (
            ('Which version of AHK are you using?', {'v1.1': tags['v1'], 'v2.0': tags['v2']}),
            ('Which of these topics fit your question best? Skip if none apply.', {
                'Sending keys/mouse': tags['Send/Click'],
                'Hotkeys': tags['Hotkeys'],
                'GUI': tags['GUI'],
                'RegEx': tags['RegEx'],
                'WinAPI': tags['WinAPI'],
                'COM Objects': tags['COM Objects'],
                'Object-Oriented': tags['Object-Oriented'],
            }),
        )

        try:
            reminder_message_id = self._tag_reminder_message.get(inter.channel.id, None)
            if reminder_message_id is not None:
                await inter.channel.delete_messages([reminder_message_id])
        except:
            pass
        
        for question in questions:
            picked = await ask(*question)

            if picked is not None:
                added_tags.append(picked)

        await inter.channel.edit(applied_tags=added_tags)

        await inter.edit_original_response(
            content='Thanks for tagging your post!\n\nAdded tags: ' + ' '.join(f"`{tag.name}`" for tag in added_tags) + '\n\nIf your issue gets solved, you can mark your post as solved by doing `/solved`',
            embed=None,
            components=None,
        )

    @commands.slash_command(description='Mark your post as solved.')
    async def solved(self, inter: disnake.AppCmdInter):
        if not isinstance(inter.channel, disnake.Thread) or inter.channel.parent.id != HELP_FORUM_CHAN_ID:
            raise commands.CommandError('This command should just be run in help channel posts.')

        if inter.author != inter.channel.owner:
            raise commands.CommandError('Only post author can mark as solved.')

        solved_tag = disnake.utils.get(inter.channel.parent.available_tags, name='Solved!')
        if solved_tag is None:
            raise commands.CommandError('Solved tag not found')

        try:
            await inter.send(f'{inter.channel.owner.mention} marked the post as solved!')
        except: # hdafdsjkhfjdas
            pass

        await inter.channel.edit(
            archived=True,
            applied_tags=inter.channel.applied_tags + [solved_tag],
        )
    
    @solved.error
    @tagme.error
    async def slash_error(self, inter: disnake.CommandInteraction, exc):
        if exc.__class__ is commands.CommandError:
            await inter.send(embed=disnake.Embed(description=str(exc)), ephemeral=True)
        else:
            raise exc

    def find_all_emoji(self, message, *, regex=re.compile(r'<a?:.+?:([0-9]{15,21})>')):
        return regex.findall(message.content)

    @commands.Cog.listener('on_message')
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
                    await message.channel.send(content=f'{message.author.mention} {reason}', delete_after=10)
                except disnake.HTTPException:
                    pass

        if not matches and not message.attachments:
            return await delete('Your message has to contain an emoji suggestion.')

        elif message.attachments:
            # if more than one attachment, delete
            if len(message.attachments) > 1:
                return await delete('Please only send one attachment at a time.')

            attachment = message.attachments[0]
            if attachment.height is None:
                return await delete('Your attachment is not an image.')

            if attachment.height != attachment.width:
                return await delete('The attached image is not square.')

            if attachment.size > 256 * 1024:
                return await delete('The attached image is larger than the emoji size limit (256KB).')

            if message.content:
                return await delete('Please do not put text in your suggestion.')

        else:
            if len(matches) > 1:
                return await delete('Please make sure your message only contains only one emoji.')

            if not re.match(r'^<a?:.+?:([0-9]{15,21})>$', message.content.strip()):
                return await delete('Please do not put text alongside your emoji suggestion.')

            match = int(matches[0])
            if any(emoji.id == match for emoji in message.guild.emojis):
                return await delete('Please do not suggest emojis that have already been added.')

        # Add voting reactions
        try:
            await message.add_reaction('✅')
            await message.add_reaction('❌')
        except disnake.Forbidden as e:
            # catch if we can't add the reactions
            # it could be that person is blocked, but it also could be that the bot doesn't have perms
            # we treat it the same since this is only used in the ahk discord.
            if e.text == 'Reaction blocked':
                # runie: don't send error message to user since they have the bot blocked anyways.
                # people who block ace don't deserve answers to their misfortunes
                return await delete()

    @commands.Cog.listener('on_raw_message_edit')
    async def handle_emoji_suggestion_message_edit(self, message: disnake.RawMessageUpdateEvent):
        if message.channel_id == EMOJI_SUGGESTIONS_CHAN_ID:
            channel = self.bot.get_channel(EMOJI_SUGGESTIONS_CHAN_ID)
            if channel is None:
                return

            try:
                await channel.delete_messages([disnake.Object(message.message_id)])
            except disnake.HTTPException:
                pass

    @commands.Cog.listener('on_raw_reaction_add')
    async def handle_emoji_suggestion_reaction(self, reaction: disnake.RawReactionActionEvent):
        if reaction.channel_id != EMOJI_SUGGESTIONS_CHAN_ID:
            return

        if reaction.member.bot:
            return

        emoji = str(reaction.emoji)

        if emoji not in ('✅', '❌'):
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
            remove_from = '✅' if emoji == '❌' else '❌'

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
