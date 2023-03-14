from parsers import HeadersParser, TableParser, BULLET

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
        HeadersParser(base, "lib/Math.htm", **function_list_kwargs),
        HeadersParser(base, "lib/ListView.htm", **view_kwargs),
        HeadersParser(base, "lib/TreeView.htm", **view_kwargs),
        HeadersParser(base, "lib/Gui.htm", **make_subcommand_like("Gui, ")),
        HeadersParser(base, "lib/Menu.htm", **make_subcommand_like("Menu, ")),
        HeadersParser(base, "lib/Control.htm", **make_subcommand_like("Control, ")),
        HeadersParser(
            base, "lib/GuiControl.htm", **make_subcommand_like("GuiControl, ")
        ),
        HeadersParser(base, "lib/GuiControls.htm", **guicontrols_kwargs),
        HeadersParser(base, "lib/File.htm", **make_object_like("File")),
        HeadersParser(base, "lib/Func.htm", **make_object_like("Func")),
        HeadersParser(base, "lib/Object.htm", **make_object_like("Object")),
        HeadersParser(base, "lib/Enumerator.htm", **make_object_like("Enum")),
        HeadersParser(
            base,
            "lib/InputHook.htm",
            **make_object_like("InputHook", property_id="object"),
        ),  # TODO: docs are dumb I cba fixing this one
        HeadersParser(
            base, "lib/ControlGet.htm", **make_subcommand_like("ControlGet, ")
        ),
        HeadersParser(base, "lib/Drive.htm", **make_subcommand_like("Drive, ")),
        HeadersParser(base, "lib/DriveGet.htm", **make_subcommand_like("DriveGet, ")),
        HeadersParser(
            base, "lib/GuiControlGet.htm", **make_subcommand_like("GuiControlGet, ")
        ),
        HeadersParser(base, "lib/SysGet.htm", **make_subcommand_like("SysGet, ")),
        HeadersParser(base, "lib/Transform.htm", **make_subcommand_like("Transform, ")),
        HeadersParser(base, "lib/WinGet.htm", **make_subcommand_like("WinGet, ")),
        HeadersParser(base, "lib/WinSet.htm", **make_subcommand_like("WinSet, ")),
        HeadersParser(base, "misc/RegEx-QuickRef.htm", **h1_simplifier("RegEx")),
        HeadersParser(base, "AHKL_DBGPClients.htm", **default_misc_kwargs),
        HeadersParser(base, "AHKL_Features.htm", **default_misc_kwargs),
        HeadersParser(base, "Concepts.htm", **default_misc_kwargs),
        HeadersParser(base, "FAQ.htm", **h1_simplifier("FAQ")),
        HeadersParser(base, "Functions.htm", **default_misc_kwargs),
        HeadersParser(base, "Hotkeys.htm", **h1_simplifier("Hotkeys")),
        HeadersParser(base, "Hotstrings.htm", **default_misc_kwargs),
        HeadersParser(base, "Language.htm", **h1_h2_kwargs),
        HeadersParser(base, "Objects.htm", **default_misc_kwargs),
        HeadersParser(base, "Program.htm", **h1_h2_kwargs),
        HeadersParser(base, "Scripts.htm", **h1_h2_kwargs),
        HeadersParser(base, "Tutorial.htm", **h1_simplifier("Tutorial")),
        HeadersParser(base, "Variables.htm", **variables_kwargs),
        HeadersParser(base, "KeyList.htm", **h1_simplifier("List of Keys")),
        TableParser(base, "Variables.htm"),
        TableParser(base, "KeyList.htm"),
        TableParser(base, "Hotkeys.htm"),
    )
