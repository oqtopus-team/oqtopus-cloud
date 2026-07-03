# FAQ

開発を進めるうえでよくある質問についての回答をまとめています。

Q. 開発環境DBの初期値はどこで設定しますか？

A. スキーマは Alembic マイグレーション（`backend/alembic/`）で、初期データは `backend/scripts/seed.py`（DB）と `backend/storage/init_storage.py`（オブジェクトストレージ / MinIO）で管理しています。`make up` を実行するとマイグレーション適用とシードが自動的に行われます。
初期値を変更する場合はこれらのファイルを編集してください。

Q. MFAを有効にしている場合、Terraformの実行はどのように行いますか？

A. `~.aws/config`に下記を設定してください

```bash
[profile myprofile]
output=json
region=ap-northeast-1
role_arn=arn:aws:iam::01234567890:role/<IAMロール名>
mfa_serial=arn:aws:iam::12345678901:mfa/<IAMユーザ名>

[profile myprofile-tf]
credential_process = aws configure export-credentials --profile myprofile
```

terraformの各設定ファイルでは`myprofile-tf`を利用します。下記のように設定してください。

```bash
# terraform/infrastructure/oqtopus-dev/oqtopus-dev.tfbackend
bucket         = "xxxxxxxxxxxxxx"
key            = "xxxxxxxxxxxxxx"
encrypt        = true
profile        = "myprofile-tf"
region         = "ap-northeast-1"
use_lockfile   = true
```

```bash
# terraform/infrastructure/oqtopus-dev/terraform.tfvars
product = "oqtopus"
org     = "example"
env     = "dev"
region  = "ap-northeast-1"
db_user_name = "xxxxxxxxxxxxx"
profile = "myprofile-tf"
```

`terraform/infrastructure/oqtopus-dev`配下で`terraform init -backend-config=oqtopus-dev.tfbackend -reconfigure`を実行後、`terraform plan`を実行することでMFA認証付きでのTerraform実行が可能です。

詳細は以下を参照してください。 : [Terraform AWS Provider Issue #2420](https://github.com/hashicorp/terraform-provider-aws/issues/2420#issuecomment-1899137746)
