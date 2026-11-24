#!/usr/bin/env python3
"""selftest.py - one self-judging test for something this machine could not test (#597).

Run:  python3 selftest.py     (prints PASS/FAIL per check, then one RESULT line)
Exit: 0 pass, 1 fail, 2 cannot run. Writes selftest-result.txt beside this script.
Never asks a question or waits for input. STDLIB ONLY, Python 3.8+.
"""
import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


# ===== BUILDER: put the checks below. Each returns (True/False, "one-line reason"). =====
def check_example():
    return True, "replace this example with a real check"


CHECKS = [check_example]
# ===== END of the builder's block =====


def main():
    lines = ["Assumed machine: %s %s, python %s" % (platform.system(), platform.release(), platform.python_version())]
    failed = 0
    for fn in CHECKS:
        try:
            ok, why = fn()
        except ImportError as e:
            lines.append("CANNOT RUN: missing library or module: %s" % e)
            return finish(lines, 2)
        except Exception as e:  # a raising check is a FAIL with its message, never a crash
            ok, why = False, "raised %s: %s" % (type(e).__name__, e)
        if ok:
            lines.append("PASS " + fn.__name__)
        else:
            failed += 1
            lines.append("FAIL %s: %s" % (fn.__name__, why))
    lines.append("RESULT: PASS" if not failed else "RESULT: FAIL (%d failed)" % failed)
    return finish(lines, 1 if failed else 0)


def finish(lines, code):
    text = "\n".join(lines)
    print(text)
    try:
        with open(os.path.join(HERE, "selftest-result.txt"), "w", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError as e:
        print("could not write selftest-result.txt: %s" % e)
    return code


if __name__ == "__main__":
    sys.exit(main())
