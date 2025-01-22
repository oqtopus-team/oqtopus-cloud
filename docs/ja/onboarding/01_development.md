# 開発フロー
参考：[Development Flow](https://oqtopus-cloud.readthedocs.io/latest/developer_guidelines/)
## issue起票
**ルール**
- [QuantumCloudPlatform](https://github.com/FujitsuResearch/QuantumCloudPlatform)で発行する。
- 各自でどんどん発行して大丈夫。

## ブランチの命名規則
開発には、主に以下の3つを使う。
- `feature/xxx`: (xxx represents the feature being added)
- `bugfix/xxx`: (xxx represents the bug being fixed)
- `hotfix/xxx`: (xxx represents the urgent fix)

xxxは「{チケット番号}-{説明}」という形式が良い。例えば、「#999-fix-int-parse-bug」といった具合。

`chore/xxx`というパターンも存在。ドキュメント更新など、開発自体に影響を与えない雑務。

## プルリク(PR)
### ルール
- [oqtopus-cloud](https://github.com/oqtopus-team/oqtopus-cloud)へPRを出す。
- すべて英語で書く。
- 関連チケットがある場合：リンクを貼る。
- Descriptionを書く。
- 関連しているPRがある場合：リンクを貼る。例えば、「本PRが通れば、このPRもマージする」など。

### 補足
- 現在、テストはActionsのみで動いている。テスト結果の記述は、本当に必要な変更だけで大丈夫。