

changes:
- use lru cache for guild module usage holding
- also lru for prefix resolver
- be smarter about how to do toggleable cogs
- gino not used anymore. do plain SQL and create tables manually
- on the topic of rss fetchers and star cleaning - https://discordpy.readthedocs.io/en/latest/ext/tasks/index.html
- global timeout for all API commands (5, instead of 3 maybe?)

autohotkey specific:
- new users get PMd or pinged when they havent accepted for 24 hrs
- ban menu with public logging for transparency

fixes to do:

- ignore list shouldn't use user id as primary key
- html2markdown escapes code box contents
- .choose fails on zero entries
- status disappears on reconnect



guild config menu:
- prefix
- module disable/enable
- role that can moderate the bot


misc:
- status: "tag for help"
- help paginator shows appropriate prefix