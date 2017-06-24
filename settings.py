import json

ignore_chan = ['music', 'irc', 'reddit']
ignore_cmd = ['help']

del_cmd = ['highlight', 'hl', 'mae']

ahk_char = 1920
ahk_line = 32

forum_char = 250
forum_line = 8

commands = {
      "bugz":       "http://i.imgur.com/dWMFR68.jpg"
    , "p":          "Paste your code at http://p.ahkscript.org/"
    , "paste":      "Paste your code at http://p.ahkscript.org/"
    , "hello":      "Hello {0.author.mention}"
    , "mae":        "*{0.author.mention} bows*"
    , "c":          "To paste code type: `!hl [code here]`"
    , "code":       "To paste code type: `!hl [code here]`"
}

embeds = {
      "tut":            {"title": "Tutorial by tidbit", "description": "https://autohotkey.com/docs/Tutorial.htm"}
    , "tutorial":       {"title": "Tutorial by tidbit", "description": "https://autohotkey.com/docs/Tutorial.htm"}
    , "docs":           {"title": "AutoHotkey documentation", "description": "https://autohotkey.com/docs/AutoHotkey.htm"}
    , "documentation":  {"title": "AutoHotkey documentation", "description": "https://autohotkey.com/docs/AutoHotkey.htm"}
    , "forum":          {"title": "AutoHotkey forums", "description": "https://autohotkey.com/boards/"}
    , "forums":         {"title": "AutoHotkey forums", "description": "https://autohotkey.com/boards/"}
}

file = open("Docs.json", "r")
docs_assoc = json.loads(file.read())
file.close()
docs = []
for x in docs_assoc:
    docs.append(x)