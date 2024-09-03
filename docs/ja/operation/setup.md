# 運用

## 踏み台サーバのセットアップ

`backend/operation`ディレクトリに移動して、以下の設定ファイルを作成してください。

> [!NOTE]
> `<>`を適切な値に置き換えてください。

```.env
MYSQL_HOST=<DB_HOST>
MYSQL_PORT=<DB_PORT>
DB_NAME=<DB_NAME>
PROFILE=<YOUR_PROFILE>
BASTION_HOST=<BASTION_HOST_ID>
SECRET_ID=<SECRET_NAME>
```

同階層にはいかのMakefileを定義しており、.envを読み込むように設定しています。

```Makefile
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: help port-forward session db-init

include .env

bastion:
  @aws ec2-instance-connect ssh --instance-id $(BASTION_HOST) --connection-type eice --profile $(PROFILE)

port-forward:
  @aws ec2-instance-connect ssh --instance-id $(BASTION_HOST) --connection-type eice --local-forwarding $(MYSQL_PORT):$(MYSQL_HOST):$(MYSQL_PORT) --profile $(PROFILE)

db-session:
  @export MYSQL_USER=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .username) && \
  export MYSQL_PASSWORD=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .password) && \
  mysql --protocol TCP -h localhost -P $(MYSQL_PORT) -u $$MYSQL_USER --password=$$MYSQL_PASSWORD $(DB_NAME)

db-init:
  @export MYSQL_USER=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .username) && \
  export MYSQL_PASSWORD=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .password) && \
  mysql --protocol TCP -h localhost -P $(MYSQL_PORT) -u $$MYSQL_USER --password=$$MYSQL_PASSWORD < ./db/init.sql
```

それでは、`make bastion`を実行して踏み台サーバーに接続してみましょう。

```bash
make bastion
```

> [!NOTE]
>`make bastion`は裏で以下のコマンドを実行しています。
>
>```bash
> aws ec2-instance-connect ssh --instance-id <踏み台サーバーのID> --profile <実行環境のprofile>
> ```

踏み台サーバーへ接続が完了したら、以下のコマンドを実行して、踏み台サーバにmysqlクライアントをインストールします。

```bash
sudo yum install -y mysql
```

これで踏み台サーバーへのセットアップは完了です。

## ポートフォワードでRDSに接続

以下のコマンドを実行して、リモートのRDSをポートフォワードすることができます。

```bash
make port-forward
```

> [!NOTE]
> `make port-forward`は裏で以下のコマンドを実行しています。
>
> ```bash
> aws ec2-instance-connect ssh --instance-id <踏み台サーバーのID> --connection-type eice --local-forwarding <ポート>:<RDSのエンドポイント>:<ポート> --profile <実行環境のprofile>
> ```

## DBに接続

`make port-foward`でリモートのRDSをポートフォワードした状態で別のセッションで以下のコマンドを実行して、DBに接続します。

```bash
make db-session
```

> [!NOTE]
> `make db-session`は裏で以下のコマンドを実行しています。
>
> ```bash
> export MYSQL_USER=$$(aws secretsmanager get-secret-value --secret-id <SECRET_NAME> --profile <PROFILE> | jq -r .SecretString | jq -r .username) && \
> export MYSQL_PASSWORD=$$(aws secretsmanager get-secret-value --secret-id <SECRET_NAME> --profile <PROFILE> | jq -r .SecretString | jq -r .password) && \
> mysql --protocol TCP -h localhost -P <MYSQL_PORT> -u $$MYSQL_USER --password=$$MYSQL_PASSWORD <DB_NAME>
> ```

以上で、RDSへの接続が完了しました。

## DBの初期化

以下のコマンドを実行して、DBの初期化を行います。

```bash
make db-init
```

> [!NOTE]
> `make db-init`は裏で以下のコマンドを実行しています。
>
> ```bash
> export MYSQL_USER=$$(aws secretsmanager get-secret-value --secret-id <SECRET_NAME> --profile <PROFILE> | jq -r .SecretString | jq -r .username) && \
> export MYSQL_PASSWORD=$$(aws secretsmanager get-secret-value --secret-id <SECRET_NAME> --profile <PROFILE> | jq -r .SecretString | jq -r .password) && \
> mysql --protocol TCP -h localhost -P <MYSQL_PORT> -u $$MYSQL_USER --password=$$MYSQL_PASSWORD <DB_NAME> < ./db/init.sql
> ```

`make db-session`を実行して、DBに接続して、初期化が完了しているか確認してください。以下のコマンドを実行してテーブルが作成されていれば初期化完了です。

```sql
mysql> show tables;
+---------------------+
| Tables_in_main      |
+---------------------+
| devices             |
| results             |
| tasks               |
+---------------------+
4 rows in set (0.05 sec)
```
