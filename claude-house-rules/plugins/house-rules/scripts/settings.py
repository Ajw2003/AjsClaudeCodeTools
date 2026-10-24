#!/usr/bin/env python3
"""settings.py - read and write the house-rules plugin's settings (#341).

  python <plugin>/scripts/settings.py set agent_name <name>
  python <plugin>/scripts/settings.py set extra_owned_prefixes "<prefix/>,<prefix/>"   ("" for none)
  python <plugin>/scripts/settings.py get agent_name
  python <plugin>/scripts/settings.py show

It prints what it saved and where. While a setting is unset the guard refuses every tool except this script.
What the settings are, where the file lives and the read order: scripts/house_rules/settings.py.
STDLIB ONLY.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_rules import settings  # noqa: E402

USAGE = ("usage: settings.py set <name> <value> | get <name> | show\n"
         "names: " + ", ".join(settings.SETTING_NAMES) + "\n")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "set" and len(argv) == 4 and argv[2] in settings.SETTING_NAMES:
        try:
            path = settings.set_value(argv[2], argv[3])
        except (ValueError, OSError) as exc:
            sys.stderr.write("settings: not saved: %s\n" % exc)
            return 1
        print("saved %s = %r to %s" % (argv[2], argv[3].strip(), path))
        val, source = settings.get(argv[2])
        if source and not source.startswith("settings file"):
            print("note: the effective value is still %r, from the %s, which is read before the settings file."
                  % (val, source))
        return 0
    if cmd == "get" and len(argv) == 3 and argv[2] in settings.SETTING_NAMES:
        val, source = settings.get(argv[2])
        if source is None:
            sys.stderr.write("settings: %s is not set\n" % argv[2])
            return 1
        print(val)
        return 0
    if cmd == "show" and len(argv) == 2:
        _vals, problem = settings.read_file()
        print("settings file: %s" % settings.settings_path())
        if problem:
            print("problem: %s" % problem)
        for n in settings.SETTING_NAMES:
            val, source = settings.get(n)
            print("%s = %s   [%s]" % (n, repr(val) if source else "(not set)", source or "unset"))
        return 0
    sys.stderr.write(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
