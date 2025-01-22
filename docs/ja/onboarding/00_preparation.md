# クラウドバイト オンボーディング

## はじめに
このオンボーディング資料は、完璧ではありません。キャッチアップが多岐渡るので、分からないことがあればどんどん聞いていきましょう。
自分が導入で困ったことがあれば、本資料に書き足していただいて大丈夫です。

## AWS導入
はじめに、AWSの開発環境にアクセスできるようにします。本アルバイトでは、AWSの環境が用意されているので、個人でAWSアカウントを作成する必要はありません。

### 1. アクセスキー発行の依頼
slackのチャンネルなどで、AWSの管理者に依頼します。管理者が不明の場合、クラウドバイトのチャンネルで、誰かにメンションをつけて質問してください。

以下を教えてもらいます。

**IAMユーザー**
- ユーザー名 (基本的に、自分が利用しているemail)
- パスワード (初期用。後で自分で設定する)
- コンソールサインインURL (https://qiqb-jump.signin.aws.amazon.com/console)

**IAMアクセスキー**
- Access key ID
- Secret access key

### 2. アカウントユーザーマニュアル
機密情報を含むため、Slackにて「アカウントユーザーマニュアルをください」と依頼してください。

## GitHub導入
### リポジトリ一覧

**[QuantumCloudPlatform](https://github.com/FujitsuResearch/QuantumCloudPlatform)** (※ アクセスには権限が必要です)

→ issue発行はこちらへ。[oqtopus-cloud](https://github.com/oqtopus-team/oqtopus-cloud)の前身なので、更新してない。

**[oqtopus-cloud](https://github.com/oqtopus-team/oqtopus-cloud)**

→ 変更はこちらへ。

### 1. 招待を受ける
slackのチャンネルなどで、上記2つの招待を、GitHubの管理者に依頼します。依頼と同時に、GitHubの「アカウント名」「メールアドレス」を書きます。
管理者が不明の場合、クラウドバイトのチャンネルで、誰かにメンションをつけて質問してください。

メールに招待が届くので、招待を受け入れてください。

### 2. cloneする
[oqtopus-cloud](https://github.com/oqtopus-team/oqtopus-cloud)の方をgit cloneします。

### 3. 開発環境を構築する
[Development Environment Setup](https://oqtopus-cloud.readthedocs.io/latest/developer_guidelines/setup/)を参考に、DockerやPoetryをセットアップする

## terraform導入
### terraformとは？
インフラをコードとして管理するためのツール。いわゆる「Infrastructure as Code」(IaC)。
LambdaやRDSの設定などをコードで記述する。

参考：[詳解 Terraform 第3版](https://www.oreilly.co.jp/books/9784814400522/)

### 主要コマンド

```bash
# 初回セットアップ
terraform init
```

```bash
# 差分を確認 (任意)
terraform plan
```

```bash
# 差分を適用
terraform apply
```

### 1. 疎通確認
(1) ターミナルを開く

(2) `oqtopus-cloud/terraform/service/oqtopus-dev`に移動する

(3) `terraform plan`を実行する → まだ変更前なので、最後に「No changes」と出ればOK