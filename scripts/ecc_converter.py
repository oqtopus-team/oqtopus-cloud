import re
import sys


def remove_ansi_sequences(text):
    ansi_escape = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", text)


def convert_to_efm(text):
    current_file = None
    lines = text.splitlines()
    for line in lines:
        line = line.rstrip("\n")
        if line.endswith(":") and not line.startswith("\t"):
            current_file = line[:-1]
            continue
        if current_file and line.startswith("\t"):
            m_single = re.match(r"\t(\d+): (.+)", line)
            m_range = re.match(r"\t(\d+)-\d+:(\d+)\s+(.+)", line)
            if m_single:
                lineno = m_single.group(1)
                msg = m_single.group(2)
                print(f"{current_file}:{lineno}:1: {msg}")
            elif m_range:
                start_lineno = m_range.group(1)
                end_lineno = m_range.group(2)
                msg = m_range.group(3)
                print(
                    f"{current_file}:{start_lineno}:1: {msg} (Raw {start_lineno}-{end_lineno})"
                )
            elif "newline" in line:
                with open(current_file, "r") as f:
                    target_file_line_length = line.split("newline")[0].strip()
                print(f"{current_file}:{target_file_line_length}:1: {line}")
            else:
                msg = line.strip()
                print(f"{current_file}:1:1: {msg}")


if __name__ == "__main__":
    text = remove_ansi_sequences(sys.stdin.read())
    convert_to_efm(text)
