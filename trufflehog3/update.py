with open("../.gitignore", "r") as f:
    ignores = f.read().splitlines()

ignores = [(f"      - '{i}'") for i in ignores if not i.startswith("#") and i != ""]
text = """\
exclude:
  - message: "ignores"
    paths:
"""
text += "\n".join(ignores) + "\n"

with open("../.trufflehog3.yml", "w") as f:
    f.write(text)
