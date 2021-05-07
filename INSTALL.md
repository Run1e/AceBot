# Installation

**If you just want to add this bot to your Discord sever,
it is recommended that you add the official instance
with the link found [here](README.md#installing-the-bot).**

This file describes how you can setup your own insance
on your local PC or on a dedicated sever.
If you want to permanently host your own instance,
you should probably put it on a dedicated server,
but for development your local PC will suffice.

## Requirements

* PostgreSQL
* Python 3
* PIP (should come with Python)
* Git (or GitHub etc.)

Please install these according to their instructions.

## Setting up PostgreSQL

* **Windows**
  * When installing PostgreSQL, you will be asked to choose a password. **Remember it.**
  * Open up a Command Prompt and run `psql -U postgres`.
  * Log in using the password you chose during the installation.
* **Linux (and \*nix in general)**
  * The installation of PostgreSQL should have created a user account called `postgres`.
    (If not, it's probably best to reinstall PostgreSQL or search online for a solution.)
  * Log into that user's account (`sudo -u postgres -i` for example).
  * Run `psql`.
* In this `psql` shell, run the following commands:
  ```postgresql
  CREATE ROLE ace WITH LOGIN PASSWORD 'choose_a_password';
  CREATE DATABASE acebot OWNER ace;
  \c acebot
  CREATE EXTENSION pg_trgm;
  \q -- quit out of psql
  ```
* On Linux, you can now `exit` to return to your own user account.

## Setting up AceBot

* Clone this repository and change into its root folder:
  `git clone --recurse-submodules https://github.com/Run1e/AceBot && cd AceBot`
* Create a file called `config.py` and add this content to it:
  ```python
  import logging
  import discord

  DESCRIPTION = '''A.C.E. - Non-official Instance'''

  BOT_TOKEN = 'your_bot_token'
  BOT_INTENTS = discord.Intents.all()
  DEFAULT_PREFIX = '.'
  OWNER_ID = your_discord_id # do not put quotes around this
  DB_BIND = 'your_database_bind'
  LOG_LEVEL = logging.DEBUG  # logging.INFO recommended for production

  BOT_ACTIVITY = discord.Game(name='@me for help menu')

  CLOUDAHK_URL = None
  CLOUDAHK_USER = None
  CLOUDAHK_PASS = None

  DBL_KEY = None
  THECATAPI_KEY = None
  WOLFRAM_KEY = None
  APIXU_KEY = None

  USE_GAME_MODEL = False
  DEV_MODE = False
  ```
  * You can get your bot token from the [Discord Developer Portal](https://discord.com/developers/applications).
    If you haven't already:
    * Create a new application (its name doesn't matter).
    * Go to “Bot” in the left sidebar.
    * Click “Add Bot”, read the warning and accept it.
  * Your database bind will look like this:
    ```
    postgresql://ace:your_password@localhost/acebot
    ```
  * Your owner ID is the ID of your Discord account.
    * To obtain it, open your Discord user settings, go to “Appearance”, and enable “Developer Mode”.
      Exit the settings, then right-click yourself anywhere and click “Copy ID”.
* Create another file called `ids.py`, this time with these contents:
  ```python
  AHK_GUILD_ID = None

  # roles
  STAFF_ROLE_ID = None
  FORUM_ADM_ROLE_ID = None
  FORUM_MOD_ROLE_ID = None
  VIP_ROLE_ID = None
  LOUNGE_ROLE_ID = None

  # level roles
  LEVEL_ROLE_IDS = {}

  # channels
  ROLES_CHAN_ID = None
  RULES_CHAN_ID = None
  GENERAL_CHAN_ID = None
  LOGS_CHAN_ID = None
  FORUM_THRD_CHAN_ID = None
  ACTIVITY_CHAN_ID = None
  EDITED_CHAN_ID = None
  DELETED_CHAN_ID = None
  GUILD_CHAN_ID = None
  EMOJI_SUGGESTIONS_CHAN_ID = None
  SUGGESTIONS_CHAN_ID = None
  GET_HELP_CHAN_ID = None

  # messages
  RULES_MSG_ID = None

  # category ids
  OPEN_CATEGORY_ID = None
  ACTIVE_CATEGORY_ID = None
  ACTIVE_INFO_CHAN_ID = None
  CLOSED_CATEGORY_ID = None

  IGNORE_ACTIVE_CHAN_IDS = tuple()
  ```
Both of these files are templates and you can change almost any value in them as you see fit.
Particularly `ids.py` needs configuring if you want to use the bot to its full potential;
you can get the ID of channels, categories, roles, etc. by right-clicking on them
(if you've got the Developer Mode enabled).

## Finishing up

* Run `pip install -r requirements.txt`.
* Run `python migrate.py` to setup all necessary databases automatically.
* Create a folder called `logs`.

## That's it!

You should be able to start the bot with `python ace.py`!
