from parsers import HeadersParser, TableParser

from .common import default, obj, subcommand, command

# listview, treeview, etc
view = dict(
    prefix_mapper=[(2, 1), (3, 1), (4, 3)],
    basic_name_check=lambda h, t, p: h in (1, 3),
)


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
    basic_name_check=lambda h, t, p: (
        not t.get("id", "").endswith("_Options")
        and not (h == 2 and t.find_next_sibling("p").text.startswith("Description:"))
    ),
)


def get(base):
    return (
        HeadersParser(base, 1, "lib/Math.htm", **default(prefix=2)),
        HeadersParser(base, 1, "lib/ListView.htm", **view),
        HeadersParser(base, 1, "lib/TreeView.htm", **view),
        HeadersParser(base, 1, "lib/Gui.htm", **subcommand("Gui, ")),
        HeadersParser(base, 1, "lib/Menu.htm", **subcommand("Menu, ")),
        HeadersParser(base, 1, "lib/Control.htm", **subcommand("Control, ")),
        HeadersParser(base, 1, "lib/GuiControl.htm", **subcommand("GuiControl, ")),
        HeadersParser(base, 1, "lib/GuiControls.htm", **guicontrols),
        HeadersParser(base, 1, "lib/File.htm", **obj("File")),
        HeadersParser(base, 1, "lib/Func.htm", **obj("Func")),
        HeadersParser(base, 1, "lib/Object.htm", **obj("Object")),
        HeadersParser(base, 1, "lib/Enumerator.htm", **obj("Enum")),
        HeadersParser(base, 1, "lib/ComObjArray.htm", **obj("ComObjArray")),
        HeadersParser(
            base,
            1,
            "lib/InputHook.htm",
            **obj("InputHook", prop="object"),
        ),  # TODO: docs are dumb I cba fixing this one
        HeadersParser(base, 1, "lib/Process.htm", **subcommand("Process, ")),
        HeadersParser(base, 1, "lib/Thread.htm", **subcommand("Thread, ")),
        HeadersParser(base, 1, "lib/ControlGet.htm", **subcommand("ControlGet, ")),
        HeadersParser(base, 1, "lib/Drive.htm", **subcommand("Drive, ")),
        HeadersParser(base, 1, "lib/DriveGet.htm", **subcommand("DriveGet, ")),
        HeadersParser(base, 1, "lib/GuiControlGet.htm", **subcommand("GuiControlGet, ")),
        HeadersParser(base, 1, "lib/SysGet.htm", **subcommand("SysGet, ")),
        HeadersParser(base, 1, "lib/Transform.htm", **subcommand("Transform, ")),
        HeadersParser(base, 1, "lib/WinGet.htm", **subcommand("WinGet, ")),
        HeadersParser(base, 1, "lib/WinSet.htm", **subcommand("WinSet, ")),
        HeadersParser(base, 1, "misc/RegEx-QuickRef.htm", **default(remap="RegEx")),
        HeadersParser(base, 1, "AHKL_DBGPClients.htm", **default()),
        HeadersParser(base, 1, "AHKL_Features.htm", **default()),
        HeadersParser(base, 1, "Concepts.htm", **default(remap="Concepts")),
        HeadersParser(base, 1, "FAQ.htm", **default(remap="FAQ")),
        HeadersParser(base, 1, "Functions.htm", **default(remap=None)),
        HeadersParser(base, 1, "Hotkeys.htm", **default(remap="Hotkeys")),
        HeadersParser(base, 1, "Hotstrings.htm", **default()),
        HeadersParser(base, 1, "Language.htm", **default(stop=2, remap=None)),
        HeadersParser(base, 1, "Objects.htm", **default()),
        HeadersParser(base, 1, "Program.htm", **default(stop=2, remap=None)),
        HeadersParser(base, 1, "Scripts.htm", **default(stop=2, remap=None)),
        HeadersParser(base, 1, "Tutorial.htm", **default(remap="Tutorial")),
        HeadersParser(base, 1, "Variables.htm", **default(remap=None, ignore=["loop"])),
        HeadersParser(base, 1, "KeyList.htm", **default(remap="List of Keys")),
        HeadersParser(base, 1, "HotkeyFeatures.htm", **default(remap=None)),
        TableParser(base, 1, "Variables.htm"),
        TableParser(base, 1, "KeyList.htm"),
        TableParser(base, 1, "Hotkeys.htm"),
    )
