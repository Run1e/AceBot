# ![Avatar](https://i.imgur.com/Sv7L0a1.png) A.C.E. - Autonomous Command Executor

[![Discord Bots](https://discordbots.org/api/widget/status/367977994486022146.svg)](https://discordbots.org/bot/367977994486022146)

A fun, general purpose Discord bot that I run!

Want it in your server? [Click here to add it!](https://discordapp.com/oauth2/authorize?&client_id=367977994486022146&scope=bot&permissions=67497025)

The bot was initially made for, and is mostly used in the [AutoHotkey server](https://discord.gg/tPGdSr2).

## Commands

To get a random animal picture:
```
.woof		Get a random doggo
.meow		Get a random cat
.quack		Get a random duck
.floof		Get a random fox
```
To use the tag system, do `.help tag` to see usage.

Miscellaneous other commands:
```
.stats		Gets command usage stats for your guild.
.define		Returns definition of a word.
.weather	Display weather information for a location.
.wolfram	Query Wolfram Alpha.
.fact		Get a random fact.
```

To otherwise see a list of commands you can use, do:
```
.help
```
## Moderator usage

To moderate the bot, you can list available modules by doing:
```
.mods
```
The `tags` and `stats` modules are enabled by default.

Then to enable or disable any module, do:
```
.enable <module>
.disable <module>
```

## Installation

If you want this bot in your server, I would prefer if you invite the official instance using the invite link above! Nevertheless, here's how to set it up.

Create a PostgreSQL database and a role:
```sql
CREATE ROLE ace WITH LOGIN PASSWORD 'your_pw';
CREATE DATABASE acebot OWNER ace;
```

Then in the root folder, make a file called `config.py` and insert your bot token, api keys and miscellaneous:
```py
token = 'your_bot_token'
command_prefix = '.'
owner_id = user_id
db_bind = 'postgresql://ace:your_pw@host/acebot'
log_level = 'INFO'

thecatapi_key = 'key'
wolfram_key = 'key'
apixu_key = 'key'
oxford_id, oxford_key = 'id', 'key'
```
## Credits

Avatar artwork: Vinter Borge

Contributors: Cap'n Odin #8812 and GeekDude #2532