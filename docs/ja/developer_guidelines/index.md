# 開発フロー

## ブランチ戦略

以下の図のように、`main` ブランチから `develop` ブランチを分岐させ、`develop` ブランチから `feature/xxx` ブランチを分岐させて開発を行います。
`main`ブランチはリリース用のブランチであり、`develop`ブランチは開発用のブランチです。

`develop`ブランチは常に最新のコードがマージされている状態を保たれているため、hotfixを行う際も、`develop`ブランチから分岐させて修正を行います。

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

### ブランチ名

明確なルールは設けませんが、以下のような命名規則を推奨します。

- `feature/xxx`: (xxxは機能追加の内容)
- `bugfix/xxx`: （xxxはバグ修正の内容）
- `hotfix/xxx`: (xxxは緊急修正の内容)

### マージ

以下の原則に従ってマージを行います。

- `main`←`develop`のマージは、Create a merge commitを選択してマージします。
- `develop`←`feature/xxx`のマージは、Squash and mergeを選択してマージします。

> [!NOTE]
> 上記のようにマージを行うことで、煩雑なコミットが`main`ブランチに残らないため、履歴がシンプルになり、リリース時のトラブルを防ぐことができます。

