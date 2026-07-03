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

.PHONY: help bastion port-forward db-session migrate-up migrate-stamp

include .env

bastion:
  @aws ec2-instance-connect ssh --instance-id $(BASTION_HOST) --connection-type eice --profile $(PROFILE)

port-forward:
  @aws ec2-instance-connect ssh --instance-id $(BASTION_HOST) --connection-type eice --local-forwarding $(MYSQL_PORT):$(MYSQL_HOST):$(MYSQL_PORT) --profile $(PROFILE)

db-session:
  @export MYSQL_USER=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .username) && \
  export MYSQL_PASSWORD=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .password) && \
  mysql --protocol TCP -h localhost -P $(MYSQL_PORT) -u $$MYSQL_USER --password=$$MYSQL_PASSWORD $(DB_NAME)

migrate-up:
  @SECRET=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString) && \
  export ALEMBIC_DATABASE_URL="mysql+pymysql://$$(echo "$$SECRET" | jq -j '.username|@uri'):$$(echo "$$SECRET" | jq -j '.password|@uri')@localhost:$(MYSQL_PORT)/$(DB_NAME)" && \
  $(MAKE) -C ../../backend migrate-up

migrate-stamp:
  @SECRET=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString) && \
  export ALEMBIC_DATABASE_URL="mysql+pymysql://$$(echo "$$SECRET" | jq -j '.username|@uri'):$$(echo "$$SECRET" | jq -j '.password|@uri')@localhost:$(MYSQL_PORT)/$(DB_NAME)" && \
  cd ../../backend && uv run alembic stamp head
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

## DBのマイグレーション

DBのスキーマは Alembic マイグレーションで管理しています（`backend/alembic/`）。`make port-forward`でリモートのRDSをポートフォワードした状態で、別のセッションで以下のコマンドを実行して、未適用のマイグレーションを適用します。

```bash
make migrate-up
```

> [!NOTE]
> `make migrate-up`は裏で以下のコマンドを実行しています。ポートフォワード済みの`localhost`のRDSに対して`alembic upgrade head`を適用します（`ALEMBIC_DATABASE_URL`で接続先を上書き）。
>
> ```bash
> SECRET=$$(aws secretsmanager get-secret-value --secret-id <SECRET_NAME> --profile <PROFILE> | jq -r .SecretString) && \
> export ALEMBIC_DATABASE_URL="mysql+pymysql://$$(echo "$$SECRET" | jq -j '.username|@uri'):$$(echo "$$SECRET" | jq -j '.password|@uri')@localhost:<MYSQL_PORT>/<DB_NAME>" && \
> make -C ../../backend migrate-up
> ```

> [!IMPORTANT]
> Alembic 導入前から存在するDB（すでにテーブルが作成済み）に初めて適用する場合は、`make migrate-up`ではなく **一度だけ** `make migrate-stamp`を実行してください。DDLを実行せずに現在のスキーマをマイグレーションの baseline（head）として記録します。以降は`make migrate-up`で差分を適用します。

`make db-session`を実行してDBに接続し、テーブルが作成されているか確認してください。以下のようにテーブルが作成されていればマイグレーション完了です。

```sql
mysql> show tables;
+-----------------+
| Tables_in_main  |
+-----------------+
| alembic_version |
| announcements   |
| devices         |
| jobs            |
| users           |
| whitelist_users |
+-----------------+
6 rows in set (0.05 sec)
```
