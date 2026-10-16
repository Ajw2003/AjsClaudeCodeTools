#!/bin/sh
# Find (or install) a Python that can `import bpy` + Pillow. Last stdout line: BPY_PYTHON=<interpreter> (bpy <version>)
# Idempotent: nothing is installed when an interpreter already works.
has() { "$1" -c 'import bpy, PIL' >/dev/null 2>&1; }
report() { echo "BPY_PYTHON=$1 (bpy $("$1" -c 'import bpy;print(bpy.app.version_string)'))"; exit 0; }

for py in python3.11 python3.13 python3 python; do
  command -v "$py" >/dev/null 2>&1 && has "$py" && report "$py"
done

# Nothing ready: install into the first interpreter that matches a bpy wheel (3.11 -> bpy 5.0.1, 3.13 -> latest).
for py in python3.11 python3.13; do
  command -v "$py" >/dev/null 2>&1 || continue
  case $py in python3.11) pkg="bpy==5.0.1" ;; *) pkg="bpy" ;; esac
  echo "installing $pkg pillow into $py" >&2
  "$py" -m pip install "$pkg" pillow >&2 && has "$py" && report "$py"
  echo "install into $py failed, trying next" >&2
done
echo "setup_bpy.sh: no usable Python. bpy wheels need python3.11 (bpy 5.0.1) or 3.13; install one and re-run." >&2
exit 1
