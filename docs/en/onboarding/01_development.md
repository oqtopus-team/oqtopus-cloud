# Development Flow
Reference: [Development Flow](https://oqtopus-cloud.readthedocs.io/latest/developer_guidelines/)
## Issue Creation
**Rules**
- Issues should be created in [QuantumCloudPlatform](https://github.com/FujitsuResearch/QuantumCloudPlatform).
- Feel free to create issues as needed.

## Branch Naming Conventions
For development, the following three branch types are primarily used:
- `feature/xxx`: (xxx represents the feature being added)
- `bugfix/xxx`: (xxx represents the bug being fixed)
- `hotfix/xxx`: (xxx represents the urgent fix)

The naming convention for `xxx` is `{ticket-number}-{description}`. For example: `#999-fix-int-parse-bug`.

There is also a pattern `chore/xxx`, which is used for non-development tasks, such as document updates that don't directly affect development.

## Pull Request (PR)
### Rules
- Submit PRs to[oqtopus-cloud](https://github.com/oqtopus-team/oqtopus-cloud).
- Write all PR content in English.
- If there is a related ticket, include a link to it.
- Write a description for the PR.
- If there is a related PR, include a link. For example: "If this PR is merged, also merge this related PR."

### Notes
- Currently, tests are only running through GitHub Actions. When documenting test results, only include changes that are absolutely necessary.