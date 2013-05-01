#!/usr/bin/python

import os
import re
import sys
import string

SEP = "----------------------------------"
BINARY_REGEX = "([0-9A-F]{2}[ ])+[0-9A-F]{2}"

TPL_FILE = """    ret = {func}("{path}");
    printf("ret: %d from creating {path}\\n", ret);
"""

TPL_REG = """    ret = registry_add({hkey}, "{subkey}", "{vname}", {value}, {vsize}, {vtype});
    printf("ret: %d from registry value {hkey}/{subkey}\\n", ret);
"""

KEYMAP = {
	"HKLM": "HKEY_LOCAL_MACHINE",
	"HKCU": "HKEY_CURRENT_USER",
}

class Ignore(Exception):
	pass

def only_printable(x):
	for c in x:
		if c not in string.printable: return False
	return True

def get_sections(regshot):
	out = {}
	pos = 0
	while pos < len(regshot) and pos != -1:
		pos = regshot.find(SEP, pos)
		pos += len(SEP)
		next = regshot.find(SEP, pos)

		# get section title
		title = regshot[pos:next].strip().split(":")[0]

		next += len(SEP)
		pos = regshot.find(SEP, next)

		# content of current section
		content = regshot[next:pos]

		out[title] = content

	return out

def makelines(data):
	lines = data.splitlines()
	for line in lines:
		line = line.strip()
		if not line: continue
		yield line

def generate_files_code(data):
	for line in makelines(data):
		fn = "copy_random_to"
		if line.endswith(".exe"): fn = "copy_exe_to"
		elif line.endswith(".dll"): fn = "copy_dll_to"

		line = line.replace("\\", "\\\\")
		print TPL_FILE.format(func=fn, path=line)

def generate_registry_code(data):
	for line in makelines(data):
		path, value = line.split(": ", 1)

		key = KEYMAP[path.split("\\", 1)[0]]
		subkey = r"\\".join( path.split("\\")[1:-1] )
		vname = path.split("\\")[-1]

		try:
			realvalue, vsize, vtype = registry_transform_value(value)
		except Ignore:
			continue

		print TPL_REG.format(hkey=key, subkey=subkey, vname=vname, value=realvalue, vsize=vsize, vtype=vtype)

def registry_transform_value(v):
	v = v.strip()
	if v.startswith("0x"):
		print "    value = {0};".format(v)
		return "(void *) &value", 4, "REG_DWORD"
	if v.startswith('"'):
		return v.replace("\\", "\\\\"), len(v)-1, "REG_SZ"
	if re.match(BINARY_REGEX, v):
		# decode, then create { byte, byte } notation
		decoded = v.replace(" ", "").decode('hex')

		if decoded.count("\0") >= len(decoded) / 2:
			# unicode string, given as hexdump from regshot
			asciistr = decoded.decode("utf16").replace("\\", "\\\\")
			if not only_printable(asciistr): raise Ignore()

			return '"' + asciistr + '"', len(asciistr)+1, "REG_SZ"

		bytenotation = r'"\x' + r"\x".join(i.encode('hex') for i in decoded) + '"'
		return bytenotation, len(decoded), "REG_BINARY"

	print "DBG", repr(v)
	raise Exception("unknown value format")

def main():
	content = open(sys.argv[1]).read()
	sections = get_sections(content)

	for title, content in sections.items():
		if title == 'Files added':
			generate_files_code(content)
		elif title == 'Values added':
			generate_registry_code(content)

	return 0

if __name__ == "__main__":
	try: sys.exit(main())
	except KeyboardInterrupt: pass
