"""Builds templates/index.html from your Index.html: only adds the shim script tag."""
import sys
src = open(sys.argv[1], encoding="utf-8").read()
tag = '<script src="/static/shim.js"></script>\n'
i = src.lower().find("<script")
out = src[:i] + tag + src[i:]
open("templates/index.html", "w", encoding="utf-8").write(out)
print("templates/index.html written; Index.html itself was not changed")
