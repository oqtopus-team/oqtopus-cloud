#!/bin/bash

config="exclude:\n  - message: \"ignores\"\n    paths:\n      - 'site/**'\n      - 'docs/**'\n      - 'poetry.lock'\n"

while IFS= read -r line; do
    if [[ -n "$line" && ! "$line" =~ ^# ]]; then
        config+="      - '$line'\n"
    fi
done < ".gitignore"

echo -e "$config" > ".trufflehog3.yml"
