import json

alias = {
	  "bugz":       	"http://i.imgur.com/dWMFR68.jpg"
	, "paste":      	"Paste your code at http://p.ahkscript.org/"
	, "hello":      	"Hello {0.author.mention}!"
	, "mae":        	"*{0.author.mention} bows*"
	, "code":      		"Use the highlight command to paste code: !hl [paste code here]"
	, "shrug":			"¯\_(ツ)_/¯"
	, "source": 		"https://github.com/Run1e/A_AhkBot"
	, "ask":			"Just ask your question, don't ask if you can ask!"
  	, "tutorial":       {"title": "Tutorial by tidbit", "description": "https://autohotkey.com/docs/Tutorial.htm"}
	, "documentation":  {"title": "AutoHotkey documentation", "description": "https://autohotkey.com/docs/AutoHotkey.htm"}
	, "forums":         {"title": "AutoHotkey forums", "description": "https://autohotkey.com/boards/"}
}

alias_assoc = {
	  "c": "code"
	, "p": "paste"
	, "f": "forum"
	, "g": "search"
	, "s": "search"
	, "w": "weather"
	, "a": "ask"
	, "tut": "tutorial"
	, "doc": "documentation"
	, "ahk": "update"
	, "version": "update"
	, "hl": "highlight"
	, "h1": "highlight"
	, "hlp": "highlightpython"
	, "github": "source"
}

plain = {
	"\o": "o/"
}

ignore_chan = [
	  'music'
	, 'irc'
	, 'reddit'
]

ignore_user = [
	  '327874898284380161'
	, '155149108183695360'
	, '159985870458322944'
]

ignore_cmd = [
	  'clear'
	, 'mute'
	, 'levels'
	, 'rank'
	, 'mute'
	, 'unmute'
	, 'manga'
	, 'pokemon'
	, 'urban'
	, 'imgur'
	, 'anime'
	, 'twitch'
	, 'youtube'
]

del_cmd = [
	  'highlight'
	, 'highlightpython'
	, 'mae'
]

ahk_char = 1920
ahk_line = 28

forum_char = 250
forum_line = 8

with open("Docs.json", "r") as f:
	docs_assoc = json.loads(f.read())
docs = []
for x in docs_assoc:
	docs.append(x)

with open("weather.txt", "r") as f:
	weatherapi = f.read()