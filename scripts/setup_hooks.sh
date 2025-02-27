#!/bin/bash

# pre-commit
pre_commit=$(cat <<EOF
#!/bin/bash

aqua exec -- lefthook run pre-commit --no-auto-install
EOF
)
echo -e "$pre_commit" > .git/hooks/pre-commit
