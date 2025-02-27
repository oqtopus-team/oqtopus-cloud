#!/bin/bash

config=$(cat <<EOF
exclude:
  - message: "ignores"
    paths:
      - 'site/**'
      - 'docs/**'
      - 'poetry.lock'
      - '*.html'
EOF
)

while IFS= read -r line; do
    if [[ -n "$line" && ! "$line" =~ ^# ]]; then
        config+="      - '$line'\n"
    fi
done < ".gitignore"

echo -e "$config" > ".trufflehog3.yml"
