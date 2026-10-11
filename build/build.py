#!/usr/bin/env python3
"""Rebuild deploy_storage_update.sh from build/deploy_template.sh and the files in src/.

Run from anywhere:  python3 build/build.py
"""
import base64
import hashlib
import os
import stat
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "build", "deploy_template.sh")
OUTPUT = os.path.join(ROOT, "deploy_storage_update.sh")
FILES = {
    "CONTRACTCHECK": os.path.join(ROOT, "src", "contractcheck.pl"),
    "DISKUSE": os.path.join(ROOT, "src", "diskuse.cgi"),
    "ADMIN": os.path.join(ROOT, "src", "contract", "index.cgi"),
}

with open(TEMPLATE, encoding="utf-8") as f:
    script = f.read()

for key, path in FILES.items():
    with open(path, "rb") as f:
        data = f.read()
    script = script.replace(f"__B64_{key}__", base64.b64encode(data).decode())
    script = script.replace(f"__MD5_{key}__", hashlib.md5(data).hexdigest())
    print(f"{key:<14} {hashlib.md5(data).hexdigest()}  {os.path.relpath(path, ROOT)}")

for key in FILES:
    if f"__B64_{key}__" in script or f"__MD5_{key}__" in script:
        sys.exit(f"ERROR: placeholder for {key} not replaced")

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(script)
os.chmod(OUTPUT, os.stat(OUTPUT).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
print(f"Wrote {os.path.relpath(OUTPUT, ROOT)}")
