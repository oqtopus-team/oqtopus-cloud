import re
import sys


def convert_to_efm(lines):
    current_file = None
    for line in lines:
        line = line.rstrip("\n")
        if line.endswith(":") and not line.startswith("\t"):
            current_file = line[:-1]
            continue
        if current_file and line.startswith("\t"):
            m = re.match(r"\t(\d+): (.+)", line)
            if m:
                lineno = m.group(1)
                msg = m.group(2)
                print(f"{current_file}:{lineno}:1: {msg}")
            else:
                msg = line.strip()
                print(f"{current_file}:?:1: {msg}")


if __name__ == "__main__":
    print("Converting to EFM format...")
    convert_to_efm(sys.stdin)
    print("Conversion complete.")
