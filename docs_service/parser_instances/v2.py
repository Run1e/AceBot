from parser_instances.common import default, obj
from parsers import HeadersParser

# for simple function pages
command = dict(
    # prefix_mapper=[
    #     (lambda h, t, p: True, "{}()"),
    # ],
    # basic_name_check=lambda h, t, p: False,
    ignore=lambda h, t, p: h
    > 1,
)


def get(base):
    return (
        HeadersParser(base, 2, "AHKL_DBGPClients.htm", **default()),
        HeadersParser(base, 2, "Concepts.htm", **default(remap="Concepts")),
        HeadersParser(base, 2, "FAQ.htm", **default(remap="FAQ")),
        HeadersParser(base, 2, "Functions.htm", **default(remap=None)),
        HeadersParser(base, 2, "Hotkeys.htm", **default(remap="Hotkeys")),
        HeadersParser(base, 2, "Hotstrings.htm", **default()),
        HeadersParser(base, 2, "Language.htm", **default(stop=2, remap=None)),
        HeadersParser(base, 2, "Objects.htm", **default()),
        HeadersParser(base, 2, "Program.htm", **default(stop=2, remap=None)),
        HeadersParser(base, 2, "Scripts.htm", **default(stop=2, remap=None)),
        HeadersParser(base, 2, "Tutorial.htm", **default(remap="Tutorial")),
        HeadersParser(base, 2, "Variables.htm", **default(remap=None, ignore=["loop"])),
        HeadersParser(base, 2, "KeyList.htm", **default(remap="List of Keys")),
        HeadersParser(base, 2, "HotkeyFeatures.htm", **default(remap=None)),
        HeadersParser(base, 2, "v1-changes.htm", **default(stop=1)),
        HeadersParser(base, 2, "v2-changes.htm", **default(stop=1)),
        HeadersParser(base, 2, "lib/Any.htm", **obj("Value")),
        HeadersParser(base, 2, "lib/Array.htm", **obj("Array", "ArrayObj")),
        HeadersParser(base, 2, "lib/Buffer.htm", **obj("Buffer", "BufferObj")),
        HeadersParser(base, 2, "lib/Class.htm", **obj("ClassObj")),
        # HeadersParser(base, 2, "lib/ComObjArray.htm", **object("ComObjArray")),  # page not formatted correctly
        HeadersParser(
            base, 2, "lib/Enumerator.htm", **obj("Enum")
        ),  # kind of weird, has a function thing too?
        HeadersParser(base, 2, "lib/File.htm", **obj("File", "FileObj")),
        HeadersParser(base, 2, "lib/Func.htm", **obj("Func", "FuncObj")),
        HeadersParser(
            base, 2, "lib/Gui.htm", **obj("Gui", "MyGui", staticmeth="Static_Methods")
        ),
        HeadersParser(base, 2, "lib/GuiControl.htm", **obj("GuiControl", "GuiCtrl")),
        HeadersParser(base, 2, "lib/Map.htm", **obj("Map", "MapObj")),
        HeadersParser(base, 2, "lib/Menu.htm", **obj("Menu", "MyMenu")),
        HeadersParser(base, 2, "lib/Object.htm", **obj("Object", "Obj")),
        # HeadersParser(base, 2, "lib/InputHook.htm", **object("InputHook")),  # h3 tags that should be h2, and new property id names???
    )


"""
issues:
ClassObj.Call() should also have an entry for ClassObj() really

DllCall.htm set()
Format.htm set()
FormatTime.htm set()
GuiControls.htm set()
GuiOnEvent.htm set()
Hotstring.htm set()
InputHook.htm set()
InstallKeybdHook.htm set()
ListView.htm set()
Math.htm set()
MsgBox.htm set()
RegExMatch.htm set()
Send.htm set()
Sort.htm set()
String.htm set()
Thread.htm set()
TreeView.htm set()
_HotIf.htm set()
_Hotstring.htm set()
"""
