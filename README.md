# ![Avatar](https://i.imgur.com/Sv7L0a1.png) A.C.E. - Autonomous Command Executor

[![Discord Bots](https://discordbots.org/api/widget/status/367977994486022146.svg)](https://discordbots.org/bot/367977994486022146)

A fun, general purpose Discord bot that I run!

Want it in your server? [Click here to add it!](https://discordapp.com/oauth2/authorize?&client_id=367977994486022146&scope=bot&permissions=67497025)

The bot was initially made for the [AutoHotkey server](https://discord.gg/tPGdSr2).

## General Commands

To get a random animal picture:
```
.woof		Get a random doggo picture
.meow		Get a random cat picture
.quack		Get a random duck picture
.floof		Get a random fox picture
```

Miscellaneous other commands:
```
.stats		Gets command usage stats for your guild.
.define		Returns definition of a word.
.weather	Display weather information for a location.
.wolfram	Query Wolfram Alpha.
.fact		Get a random fact.
```

A complete list of available commands can be browsed by doing `.help`

## Modules

### Tags

The tags module makes it easy to bring up text. The tags system works like this:

```py
# this command creates a tag called 'test'
.tag create supportserver Hi there! Join my support server at https://discord.gg/X7abzRe

# calling the tag will make the bot echo back the tag contents:
.tag supportserver
# > Hi there! Join my support server at https://discord.gg/X7abzRe
```

To see a full list of tag related commands, do `.help tags`

### Starboard

Classic Starboard. Anyone can star any message, which gets copied to a #starboard channel by the bot. From there anyone
can add more stars. After a week, starred messages with less than 5 stars get removed. It's essentially a way for anyone to pin messages.

`.starboard top`
Lists what users have the most popular/starred messages.

`.starboard info <message_id>`
Displays information about a starred message, such as who starred it, and in what channel the original message was posted in.
`message_id` can be either the original or starred message id.

`.starboard channel <channel>`
What channel starred messages should be posted in. Make sure people can add reactions to messages, but can not *post* messages.

`.starboard delete <message_id>`
Delete a starred message.

### Welcome

The welcome module makes it easy to welcome new server members with a welcoming message. Has to be enabled using `.enable`

```py
# configure welcome channel and message:
.welcome channel #general
# > Channel is set to: #general
.welcome msg Hi there {user}! Welcome to {guild}!
# > New welcome message set. Do ".welcome test" to test!
.welcome test
# The above command will send a test message so you can confirm it works and looks like you want it to.
```

When a member joins, `{user}` is replaced with a mention and `{guild}` is replaced with the server name.

To see a full list of welcome message related commands, do `.help welcome`. To enable/disable welcome messages, simply toggle the module.

### Moderator

The moderator module has some basic moderation functionality. Has to be enabled using `.enable`

These commands are only available to members with the Ban Members permission.

`.clear [message_count] [user]`
Clears the newest `message_count` messages in the current channel, either indiscriminately or only messages from `user`.

`.info [user]`
Shows all practically useful information about a member or yourself.

### Highlighter

Makes it easier to paste code into the chat. Has to be enabled using `.enable`

`.hl <code>`
Deletes your message and reports the code in a code box, with emojis for message deletion.

`.lang <language>`
Change what syntax highlighting the bot should use for your code. For example: `py`, `ahk`, `html`, etc.

`.guildlang <language>`
Sets the default server specific syntax highlighting for `.hl`. Only changable by users with the Manage Server permission.

### Coins

Bet virtual coins. Lose it all or get rich! Has to be enabled using `.enable`

`.bet <coins>`
Bet an amount of coins. 50% of losing your bet!

`.coins [member]`
Show your balance, and other misc. stats.

## Bot moderation

To moderate the bot, you can list available modules by doing:
```
.mods
```

Then to enable or disable any module, do:
```
.enable <module>
.disable <module>
```

## Installation

If you want this bot in your server, I would prefer if you invite the official instance (which has excellent uptime!) using the invite link above. Nevertheless, here's how to set it up!

Create a PostgreSQL database and a role:
```sql
CREATE ROLE ace WITH LOGIN PASSWORD 'your_pw';
CREATE DATABASE acebot OWNER ace;
```

Then in the root folder, make a file called `config.py` and insert your bot token, api keys and miscellaneous:
```py
BOT_TOKEN 		= 'your_bot_token'
COMMAND_PREFIX 	= '.'
OWNER_ID 		= your_user_id
DB_BIND 		= 'postgresql://user:pass@host/database'
LOG_LEVEL 		= 'INFO'

# leave as None to disable functionality
LOG_CHANNEL		= None  # currently only logs guild joins and leaves
FEEDBK_CHANNEL	= None  # where to log .feedback invocations
ERROR_CHANNEL 	= None  # where to log errors that occur

DBL_KEY 		= None
THECATAPI_KEY 	= None
WOLFRAM_KEY 	= None
APIXU_KEY 		= None
OXFORD_ID 		= None
OXFORD_KEY 		= None
```
## Acknowledgements

Avatar artwork: Vinter Borge
Contributors: CloakerSmoker #2459, Cap'n Odin #8812 and GeekDude #2532