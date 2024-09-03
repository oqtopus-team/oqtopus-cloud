
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

### Merging

Follow the principles below for merging:

- For `main` ← `develop` merges, select "Create a merge commit."
- For `develop` ← `feature/xxx` merges, select "Squash and merge."

> [!NOTE]
> By merging in this way, complex commits are not left in the `main` branch, keeping the history simple and preventing issues during releases.
