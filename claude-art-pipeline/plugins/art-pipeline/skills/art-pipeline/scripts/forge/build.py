#!/usr/bin/env python3
"""Build and validate assets from a spec and a blueprints file.

  python3.13 forge/build.py --spec spec.json --blueprints blueprints.py [--only slug ...] --out DIR

blueprints.py defines BLUEPRINTS = {slug: builder}; a builder takes the spec Entry and
returns a forge.Blueprint. A slug the spec lacks is refused (exit 2). Exit 0 only if every
asset built passed the validator; 1 if any failed; 2 on bad input.
"""

import argparse
import importlib.util
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # so `import forge` works


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--blueprints", required=True)
    ap.add_argument("--only", action="append", default=[], metavar="SLUG", help="build only this slug (repeatable)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        from forge.spec import load_spec
        spec = load_spec(args.spec)
        mod_spec = importlib.util.spec_from_file_location("forge_blueprints", os.path.abspath(args.blueprints))
        mod = importlib.util.module_from_spec(mod_spec)
        sys.modules["forge_blueprints"] = mod
        mod_spec.loader.exec_module(mod)
        blueprints = getattr(mod, "BLUEPRINTS", None)
        if not isinstance(blueprints, dict) or not blueprints:
            raise ValueError(f"{args.blueprints} must define a non-empty BLUEPRINTS = {{slug: builder}}")
    except Exception as error:   # bad input: say what, exit 2
        print(f"build.py: {error}", file=sys.stderr)
        return 2

    missing = sorted(set(blueprints) - set(spec))
    if missing:
        print(f"build.py: refusing: blueprints for slugs the spec does not list: {missing}; "
              f"spec lists {sorted(spec)}", file=sys.stderr)
        return 2
    unknown = [s for s in args.only if s not in blueprints]
    if unknown:
        print(f"build.py: --only {unknown} has no blueprint; blueprints are {sorted(blueprints)}",
              file=sys.stderr)
        return 2
    todo = args.only or list(blueprints)
    for slug in sorted(set(spec) - set(blueprints)):
        print(f"note: spec lists {slug!r} but blueprints.py has no builder for it; skipped")

    from forge.pipeline import build_asset
    out = os.path.abspath(args.out)
    failed = []
    for slug in todo:
        try:
            rep = build_asset(spec[slug], blueprints[slug], out)
            print(rep.text())
            if not rep.passed:
                failed.append(slug)
        except Exception:
            traceback.print_exc()
            print(f"[FAIL] {slug}: build raised (traceback above)")
            failed.append(slug)
    print(f"{len(todo) - len(failed)}/{len(todo)} passed" + (f"; failed: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
