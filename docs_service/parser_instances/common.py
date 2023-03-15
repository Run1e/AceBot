from parsers import BULLET_SPACED


# for pages with commands that have subcommands
def subcommand(prefix):
    return dict(
        prefix_mapper=[
            (2, 1),
            (lambda h, t, p: p[-1] == "SubCommands", prefix + "{}"),
            (
                3,
                1,
            ),  # I removed this since it made gui.htm look nicer, maybe a dumb idea
            (4, 3),
        ],
        basic_name_check=lambda h, t, p: h in (1, 3) and p[-1] != "SubCommands",
    )


# for pages describing objects with methods and properties
def obj(
    prefix,
    instance_name=None,
    meth="Methods",
    prop="Properties",
    func="Functions",
    staticmeth="StaticMethods",
):
    instance_name = instance_name or prefix

    # v2 input hook has these two badboys...
    props = [prop, "General_Properties", "Option_Properties"]

    return dict(
        prefix_mapper=[
            (2, 1),
            (lambda h, t, p: p[-1] == meth, instance_name + ".{}()"),
            (lambda h, t, p: p[-1] in props, instance_name + ".{}"),
            (lambda h, t, p: p[-1] == func, "{}()"),
            (lambda h, t, p: p[-1] == staticmeth, prefix + "()"),
            (3, 1),
            (4, 3),
        ],
        basic_name_check=lambda h, t, p: h in (1, 3)
        and p[-1] not in [meth, func, staticmeth, *props],
    )


# stop: which h* to stop adding at
# remap: remap the name of the h1 tag when prefixing
# ignore: list of fragments to ignore
# prefix
def default(stop=3, remap=1, ignore=None, prefix=None):
    if stop > 3:
        raise ValueError("You gotta fix the mapper in this case")

    # always add basic name for h1 tags
    basic = set([1])

    if remap is None:
        mapper = None
    else:
        if isinstance(remap, int):
            one = remap
        elif isinstance(remap, str):
            one = BULLET_SPACED.join((remap, "{}"))
        mapper = [(i + 1, one) for i in range(1, prefix or stop)]

        # if we're doing remapping but also excluding some h* tags
        # because of *prefix*, then we need to add plain names for the
        # difference
        if prefix:
            for i in range(prefix, stop):
                basic.add(i + 1)

    d = dict(
        prefix_mapper=mapper,
        basic_name_check=lambda h, t, p: True if remap is None else h in basic,
        ignore=lambda h, t, p: h > stop or (ignore and t.get("id", None) in ignore),
    )

    return d
