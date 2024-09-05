
# Development Flow

## Branch Strategy

As shown in the diagram below, the `develop` branch is branched off from the `main` branch, and feature branches (`feature/xxx`) are branched off from the `develop` branch for development. The `main` branch is the release branch, while the `develop` branch is for development.

The `develop` branch always maintains the latest merged code, so when performing hotfixes, branches are created from the `develop` branch for the necessary fixes.

```mermaid
gitGraph LR:
    commit tag:"release-v1.0.0"
    branch develop
    commit
    branch feature/xxx
    commit
    commit
    checkout develop
    branch feature/yyy
    commit
    checkout develop
    merge feature/yyy
    checkout feature/xxx
    commit
    checkout develop
    merge feature/xxx
    checkout main
    merge develop tag:"release-v1.1.0"
    checkout develop
    branch hotfix/zzz
    commit
    commit
    checkout develop
    merge hotfix/zzz
    checkout main
    merge develop tag:"release-v1.2.0"
```

### Branch Naming

While there are no strict rules, the following naming conventions are recommended:

- `feature/xxx`: (xxx represents the feature being added)
- `bugfix/xxx`: (xxx represents the bug being fixed)
- `hotfix/xxx`: (xxx represents the urgent fix)

## Conventional Commits

The commit messages should preferably follow the　[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) guidelines.

### Commit Message Format

By using `.gitmessage`, a template for commit messages is provided. This template can be enabled locally for this project by configuring `git config --local`.

```bash
git config --local commit.template .gitmessage
```

Once configured, running `git commit` will display the contents of `.gitmessage` in your editor (Vim by default).

```bash
git commit
# Overview (Uncomment one of the following templates)
#feat: 
# └  A new feature
#fix:
# └  A bug fix
#docs:
# └  Documentation only changes
#style:
# └  Changes that do not affect the meaning of the code
#    (white-space, formatting, missing semi-colons, etc)
#refactor:
# └  A code change that neither fixes a bug nor adds a featur
#test:
# └  Adding missing or correcting existing tests
#ci:
# └  Changes to our CI configuration files and scripts
#chore:
# └  Updating grunt tasks etc; no production code change

```

Select the appropriate template and uncomment it, then write your commit message.

```bash
docs: Update README.md
# └  Documentation only changes
```

## Correspondence between Commit Messages and Labels

When creating a PR to the `develop` branch, labels are automatically assigned based on the commit messages.
Below is the correspondence between prefixes and labels:

| Prefix | Label | Description |
|---|---|---|
|feat: | `feature` | Adding a new feature |
|fix: | `bugfix` | Bug fixes |
|docs: | `documentation` | Documentation only changes |
|style: | `style` | Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc) |
|refactor: | `refactor` | Code changes that neither fix a bug nor add a feature |
|test: | `test` | Adding or correcting existing tests |
|ci: | `ci` | Adding or updating CI configuration and scripts |
|chore: | `chore` | Minor changes or maintenance tasks |

## Merging

Follow the principles below for merging:

- For `main` ← `develop` merges, select "Create a merge commit."
- For `develop` ← `feature/xxx` merges, select "Squash and merge."

> [!NOTE]
> By merging in this way, complex commits are not left in the `main` branch, keeping the history simple and preventing issues during releases.
