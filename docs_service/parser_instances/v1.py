from parsers import BULLET, HeadersParser, TableParser

view_kwargs = dict(
    prefix_mapper=[(2, 1), (3, 1), (4, 3)],
    basic_name_check=lambda h, t, p: h in (1, 3),
)

function_list_kwargs = dict(
    prefix_mapper=[(2, 1)],
)


def make_subcommand_like(prefix):
    return dict(
        prefix_mapper=[
            (2, 1),
            (lambda h, t, p: p[-1] == "SubCommands", prefix + "{}"),
            # (3, 1),  # I removed this since it made gui.htm look nicer, maybe a dumb idea
            (4, 3),
        ],
        basic_name_check=lambda h, t, p: h in (1, 3) and p[-1] != "SubCommands",
    )


def make_object_like(prefix, method_id="Methods", property_id="Properties"):
    return dict(
        prefix_mapper=[
            (2, 1),
            (lambda h, t, p: p[-1] == method_id, prefix + ".{}()"),
            (lambda h, t, p: p[-1] == property_id, prefix + ".{}"),
            (3, 1),
            (4, 3),
        ],
        basic_name_check=lambda h, t, p: h in (1, 3)
        and p[-1] not in (method_id, property_id),
    )


guicontrols_kwargs = dict(
    prefix_mapper=[
        (
            lambda h, t, p: h == 2
            and t.find_next_sibling("p").text.startswith("Description:"),
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

functor_kwargs = dict(
    prefix_mapper=[(2, 1), (3, 1)],
    basic_name_check=lambda h, t, p: h < 2,
)

default_command_kwargs = dict(ignore=lambda h, t, p: h > 1)

default_misc_kwargs = dict(
    prefix_mapper=[(2, 1)],
    basic_name_check=lambda h, t, p: h == 1,
    ignore=lambda h, t, p: h > 2,
)


h1_h2_kwargs = dict(
    ignore=lambda h, t, p: h > 2,
)


variables_kwargs = dict(
    ignore=lambda h, t, p: h > 2 or t.get("id", None) not in ("BuiltIn", None),
)


def h1_simplifier(new):
    fmt = f"{new} " + BULLET + " {}"
    return dict(
        prefix_mapper=[(2, fmt), (3, fmt)],
        basic_name_check=lambda h, t, p: h == 1,
        ignore=lambda h, t, p: h > 3,
    )


def get(base):
    return (
        HeadersParser(base, 1, "lib/Math.htm", **function_list_kwargs),
        HeadersParser(base, 1, "lib/ListView.htm", **view_kwargs),
        HeadersParser(base, 1, "lib/TreeView.htm", **view_kwargs),
        HeadersParser(base, 1, "lib/Gui.htm", **make_subcommand_like("Gui, ")),
        HeadersParser(base, 1, "lib/Menu.htm", **make_subcommand_like("Menu, ")),
        HeadersParser(base, 1, "lib/Control.htm", **make_subcommand_like("Control, ")),
        HeadersParser(
            base, 1, "lib/GuiControl.htm", **make_subcommand_like("GuiControl, ")
        ),
        HeadersParser(base, 1, "lib/GuiControls.htm", **guicontrols_kwargs),
        HeadersParser(base, 1, "lib/File.htm", **make_object_like("File")),
        HeadersParser(base, 1, "lib/Func.htm", **make_object_like("Func")),
        HeadersParser(base, 1, "lib/Object.htm", **make_object_like("Object")),
        HeadersParser(base, 1, "lib/Enumerator.htm", **make_object_like("Enum")),
        HeadersParser(
            base,
            1,
            "lib/InputHook.htm",
            **make_object_like("InputHook", property_id="object"),
        ),  # TODO: docs are dumb I cba fixing this one
        HeadersParser(
            base, 1, "lib/ControlGet.htm", **make_subcommand_like("ControlGet, ")
        ),
        HeadersParser(base, 1, "lib/Drive.htm", **make_subcommand_like("Drive, ")),
        HeadersParser(
            base, 1, "lib/DriveGet.htm", **make_subcommand_like("DriveGet, ")
        ),
        HeadersParser(
            base, 1, "lib/GuiControlGet.htm", **make_subcommand_like("GuiControlGet, ")
        ),
        HeadersParser(base, 1, "lib/SysGet.htm", **make_subcommand_like("SysGet, ")),
        HeadersParser(
            base, 1, "lib/Transform.htm", **make_subcommand_like("Transform, ")
        ),
        HeadersParser(base, 1, "lib/WinGet.htm", **make_subcommand_like("WinGet, ")),
        HeadersParser(base, 1, "lib/WinSet.htm", **make_subcommand_like("WinSet, ")),
        HeadersParser(base, 1, "misc/RegEx-QuickRef.htm", **h1_simplifier("RegEx")),
        HeadersParser(base, 1, "AHKL_DBGPClients.htm", **default_misc_kwargs),
        HeadersParser(base, 1, "AHKL_Features.htm", **default_misc_kwargs),
        HeadersParser(base, 1, "Concepts.htm", **default_misc_kwargs),
        HeadersParser(base, 1, "FAQ.htm", **h1_simplifier("FAQ")),
        HeadersParser(base, 1, "Functions.htm", **default_misc_kwargs),
        HeadersParser(base, 1, "Hotkeys.htm", **h1_simplifier("Hotkeys")),
        HeadersParser(base, 1, "Hotstrings.htm", **default_misc_kwargs),
        HeadersParser(base, 1, "Language.htm", **h1_h2_kwargs),
        HeadersParser(base, 1, "Objects.htm", **default_misc_kwargs),
        HeadersParser(base, 1, "Program.htm", **h1_h2_kwargs),
        HeadersParser(base, 1, "Scripts.htm", **h1_h2_kwargs),
        HeadersParser(base, 1, "Tutorial.htm", **h1_simplifier("Tutorial")),
        HeadersParser(base, 1, "Variables.htm", **variables_kwargs),
        HeadersParser(base, 1, "KeyList.htm", **h1_simplifier("List of Keys")),
        TableParser(base, 1, "Variables.htm"),
        TableParser(base, 1, "KeyList.htm"),
        TableParser(base, 1, "Hotkeys.htm"),
    )
