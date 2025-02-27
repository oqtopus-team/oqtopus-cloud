#!/bin/bash

config=$(cat <<EOF
exclude:
  - message: "ignores"
    paths:
      - 'site/**'
      - 'docs/**'
      - 'poetry.lock'
      - 'scripts/setup_aqua.sh'
      - '*.html'
EOF
)

while IFS= read -r line; do
    if [[ -n "$line" && ! "$line" =~ ^# ]]; then
        config+="\n      - '$line'"
    fi
done < ".gitignore"

echo -e "$config" > ".trufflehog3.yml"
