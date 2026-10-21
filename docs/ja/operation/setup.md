# 運用

## 踏み台サーバのセットアップ

`operation/`配下に環境ごとのディレクトリを作成し（`operation/example-dev/`をコピーするのが最も手早いです）、以下の設定ファイルをそこに配置してください。

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

同階層の`Makefile`は、その`.env`の読み込みと共通ターゲットのincludeだけを行います。

```Makefile
include .env
export

include ../Makefile.common
```

ターゲットの実体はすべて`operation/Makefile.common`にあり、全環境で共有されます。ターゲットを追加する場合は環境ごとの`Makefile`ではなくこのファイルに追加してください。環境ごとにレシピを複製していたことが、ある環境にだけ修正が入り他の環境には入らない状態を生んでいました。利用可能なターゲットは環境ディレクトリで`make help`を実行すると確認できます。

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
make migrate-current   # 読み取り専用: 現在のリビジョンを確認
make migrate-up        # 未適用のマイグレーションを適用
make migrate-current   # 読み取り専用: head に到達したことを確認
```

> [!NOTE]
> `make migrate-up`は裏で以下のコマンドを実行しています。ポートフォワード済みの`localhost`のRDSに対して`alembic upgrade head`を適用します（`ALEMBIC_DATABASE_URL`で接続先を上書き）。
>
> ```bash
> SECRET=$$(aws secretsmanager get-secret-value --secret-id <SECRET_NAME> --profile <PROFILE> | jq -r .SecretString) && \
> export ALEMBIC_DATABASE_URL="mysql+pymysql://$$(echo "$$SECRET" | jq -j '.username|@uri'):$$(echo "$$SECRET" | jq -j '.password|@uri')@localhost:<MYSQL_PORT>/<DB_NAME>" && \
> cd ../../backend && uv run alembic upgrade head
> ```
>
> `backend/Makefile`経由ではなくalembicを直接実行しています。`backend/Makefile`はローカルのdocker環境用の設定であり`ENV=local`をexportするため、sub-makeではこちらから渡した値が上書きされてしまい、`alembic/env.py`が本番DBをローカルコンテナと見なしてTLSをスキップしてしまいます。

> [!WARNING]
> これらは必ず `operation/<env>/` で実行してください。`backend/` の `migrate-*` ターゲットを使ってはいけません。あちらはローカルのdocker DB用で（`backend/Makefile` が `ENV=local` と `DB_HOST=localhost` をexportします）、ポートフォワードを開いている間は `localhost:3306` が **リモートのRDS** になるため、ローカルコンテナのつもりで実環境に対して操作してしまいます（TLSのスキップも含む）。接続ごとに接続先とTLS状態をログ出力しているので、挙動がおかしいときはこの行を確認してください。
>
> ```
> INFO  [alembic.env] connecting to mysql+pymysql://admin:***@localhost:3306/main (TLS: on)
> ```

TLSの設定は不要です。RDS Proxyは平文接続を`ERROR 3159 (HY000): This RDS Proxy requires TLS connections`で拒否するため、`alembic/env.py`がアプリケーションと同様に`backend/oqtopus_cloud/common/certs`のRDS CAバンドルを自動的に付与します。接続先がループバックアドレスの場合のみホスト名検証を無効化します（ポートフォワード経由ではProxyの証明書が接続先ホスト名と一致し得ないため）。

> [!IMPORTANT]
> Alembic 導入前から存在するDB（すでにテーブルが作成済み）に初めて適用する場合は、`make migrate-up`の **前に一度だけ** `make migrate-stamp`を実行してください。DDLを実行せずに、マイグレーションチェーンの根のリビジョン（Alembic導入前のDBが既に持っているスキーマに対応するリビジョン）を baseline として記録します。その後`make migrate-up`で、baseline以降のリビジョンを適用します。
>
> これは意図的に`alembic stamp head`ではありません。`head`をstampすると、baselineからheadまでのリビジョンがDDL未実行のまま「適用済み」として記録され、Alembicが報告する状態よりスキーマが遅れたままになります。`make migrate-stamp`はリビジョンが既に記録されているDBに対しては実行を拒否するため、追跡済みのDBを巻き戻すことはできません。

`make migrate-check`はモデルとDBのスキーマ差分を報告します。Alembic導入前から存在するDBでは、旧`init.sql`が作成したがモデルにはもう存在しないレガシーなカラム・インデックスが報告されるのが正常で、エラーではありません。ただし今後`alembic revision --autogenerate`を実行するとそれらの **削除** が生成されるため、生成されたリビジョンから手で除去する必要があります。

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
