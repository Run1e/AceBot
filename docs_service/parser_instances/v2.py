from parser_instances.common import command, default, obj
from parsers import HeadersParser

# guicontrols.htm page which is unique
# also holy shit what is going on
guicontrols = dict(
    prefix_mapper=[
        (
            lambda h, t, p: h == 2 and t.find_next_sibling("p").text.startswith("Description:"),
            "{} Control",
        ),
        (2, 1),
        (3, -1),
        (4, -1),
    ],
    basic_name_check=lambda h, t, p: h == 1,
    ignore=lambda h, t, p: h > 3,
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
        HeadersParser(base, 2, "lib/Gui.htm", **obj("Gui", "MyGui", staticmeth="Static_Methods")),
        HeadersParser(base, 2, "lib/GuiControl.htm", **obj("GuiControl", "GuiCtrl")),
        HeadersParser(base, 2, "lib/Map.htm", **obj("Map", "MapObj")),
        HeadersParser(base, 2, "lib/Menu.htm", **obj("Menu", "MyMenu")),
        HeadersParser(base, 2, "lib/Object.htm", **obj("Object", "Obj")),
        # HeadersParser(base, 2, "lib/InputHook.htm", **object("InputHook")),  # h3 tags that should be h2, and new property id names???
        HeadersParser(base, 2, "lib/GuiControls.htm", **guicontrols),
        HeadersParser(base, 2, "lib/Hotstring.htm", **default(stop=2)),
        HeadersParser(base, 2, "lib/ListView.htm", **obj("ListView", "LV", meth="BuiltIn")),
        HeadersParser(base, 2, "lib/TreeView.htm", **obj("TreeView", "TV", meth="BuiltIn")),
        HeadersParser(base, 2, "lib/Math.htm", **default(prefix=2)),
    )


"""
issues:
ClassObj.Call() should also have an entry for ClassObj() really
"""
