# 開発環境のセットアップ

## 前提条件

開発を始める前に、以下のツールをインストールする必要があります：

## 開発環境

| ツール                                         | バージョン               | 説明                           |
|------------------------------------------------|--------------------------|-------------------------------|
| [Docker](https://docs.docker.com/get-docker/)  | -                        | コンテナ仮想化プラットフォーム |
| [Docker Compose](https://docs.docker.com/compose/install/) | -            | 複数のDockerコンテナの管理   |
| [Python](https://www.python.org/downloads/)    | 3.12.3                   | Pythonのプログラミング言語    |
| [Pyenv](https://github.com/pyenv/pyenv) (Optional) | -              | Pythonのバージョン管理ツール |
| [uv](https://docs.astral.sh/uv/)               | -                        | Pythonの高速なパッケージ管理ツール   |

開発を始めるには、リポジトリをクローンし依存関係をインストールします：

```bash
git clone https://github.com/oqtopus-team/oqtopus-cloud.git
```

## Aquaのインストール

Aquaはプロジェクトの管理をサポートするツールです。 詳細は [こちら](https://aquaproj.github.io/)で確認できます。

Aquaをインストールするには、以下のコマンドを実行します：

```bash
make setup-aqua
```

このコマンドの最後に出てくるメッセージで`aqua`をPATHに追加するように指示されますので従ってください。

## 環境の確認

環境を確認するには、以下のコマンドを実行します：

```bash
make doctor
```

上記の手順を実行すると、以下のような出力が得られます：

```bash
make doctor
Checking the environment...
Aqua version: aqua version 2.29.0 (9ff65378f0c6197e3130a20f6d978b8a3042b463)
Python version: Python 3.12.3
uv version: uv 0.7.16 (b6b7409d1 2025-06-27)
Docker version: Docker version 26.1.4, build 5650f9b

```

## Gitフックファイルの生成

このリポジトリでは、クレデンシャルをスキャンするためにGitフック `pre-commit` を使用します。

スクリプトを生成するには、以下のコマンドを実行してください：

```bash
make setup-hooks
```

スクリプトは `.git/hooks/pre-commit`に生成されます。

## Python環境のセットアップ

### Pyenv(推奨)

Python 3.12.3をインストールするには、以下のコマンドを実行します：

```bash
pyenv install 3.12.3
```

次に、Pythonのバージョンを3.12.3に設定します：

```bash
pyenv local 3.12.3
```

### uv

環境設定の一環で**uv**を設定するために、以下のコマンドを実行します：

```
make setup-uv
```

このコマンドは、PyenvでインストールされたPythonバージョンの使用、Python環境のセットアップ、依存関係のインストールに必要です。これにより、ルートディレクトリに `.venv` が作成されます。

## ローカルでのバックエンド起動

以降のステップは別々のターミナルで実行します。各ターミナルで `cd backend` してから make コマンドを実行してください。

### 1. DB・SeaweedFSの起動（ターミナル1）

```bash
cd backend
make up
```

MySQL (ポート3306) と SeaweedFS (S3 APIポート8333、Web UIポート9333/9001) が起動します。
初回起動時はDBの初期化（テーブル作成・テストデータ投入）が自動で行われます。

`make up` はコンテナをバックグラウンドで起動して終了します。停止するときは `make down` を実行してください。

非推奨の MinIO スタックを起動する場合は `make up STORAGE_STACK=minio` を使います。[ストレージバックエンドの選定](../architecture/storage_backend_selection.md) を参照してください。

### 2. APIの起動

> [!NOTE]
> フロントエンドを `http://localhost:5173` から呼ぶ場合、CORS のため `ALLOW_ORIGINS` に当該オリジンを含める必要があります。Makefile の既定値 (`http://127.0.0.1:8000`) のままだとブラウザでブロックされます。

別のターミナルで User API / Provider API を起動します。フロントエンドからアクセスする場合は `ALLOW_ORIGINS` を上書きしてください：

```bash
# ターミナル2: User API（ジョブ投入用）
cd backend
ALLOW_ORIGINS=http://127.0.0.1:8000,http://localhost:5173 make run-user
```

```bash
# ターミナル3: Provider API（バックエンドインスタンスとの通信用）
cd backend
ALLOW_ORIGINS=http://127.0.0.1:8000,http://localhost:5173 make run-provider
```

サインアップ機能を試す場合はさらに User Signup API を起動します：

```bash
# ターミナル4（必要な場合のみ）: User Signup API
cd backend
ALLOW_ORIGINS=http://127.0.0.1:8000,http://localhost:5173 make run-user_signup
```

| API | ポート | 用途 |
|-----|--------|------|
| User API | 8080 | ジョブ投入・結果取得 |
| Provider API | 8888 | バックエンドインスタンスとの通信 |
| User Signup API | 8890 | サインアップ・ユーザー登録（任意） |

### 3. 動作確認

APIドキュメント（Swagger UI）で確認できます：

- User API: [http://localhost:8080/docs](http://localhost:8080/docs)
- Provider API: [http://localhost:8888/docs](http://localhost:8888/docs)
- User Signup API: [http://localhost:8890/docs](http://localhost:8890/docs)（起動した場合）

ストレージ経路だけを切り分けて確認したい場合は`make check-presigned-post`が使えます。
通常の開発では不要です。詳細は[ストレージバックエンドの選定](../architecture/storage_backend_selection.md)を参照してください。

## ローカルでのフロントエンド起動

[OQTOPUS Frontend](https://github.com/oqtopus-team/oqtopus-frontend) をローカルで起動し、上記のローカルバックエンドと組み合わせて動作確認ができます。

> [!IMPORTANT]
> フロントエンドの認証はAWS Cognitoを使用しています。ローカルで起動した場合でも、ログインには **既存のCognito User Pool（例: `oqtopus-dev` 環境）にアカウントが登録されている必要** があります。
> アカウントを持っていない場合はログイン画面から先に進めません。アカウントが必要な場合は運用担当者に依頼してください。

### 前提条件

- [bun](https://bun.sh/) がインストール済みであること
- 上記の「ローカルでのバックエンド起動」で User API (ポート8080) が起動済みで、`ALLOW_ORIGINS` に `http://localhost:5173` が含まれていること
- 利用可能なCognito User PoolのID / Web Client ID / 登録済みアカウント
- サインアップ機能を試す場合は User Signup API (ポート8890) も起動済みであること

### 1. リポジトリのクローン

```bash
git clone https://github.com/oqtopus-team/oqtopus-frontend.git
cd oqtopus-frontend
```

### 2. 依存関係のインストール

```bash
bun install
```

### 3. 環境変数の設定

`.env` ファイルを編集し、ローカルバックエンドを参照する設定と、認証用のCognito設定を行います：

```env
VITE_APP_API_ENDPOINT=http://localhost:8080
VITE_APP_API_SIGNUP_ENDPOINT=http://localhost:8890
VITE_APP_AUTH_REGION=ap-northeast-1
VITE_APP_AUTH_USER_POOL_ID=<利用するCognito User Pool ID>
VITE_APP_AUTH_USER_POOL_WEB_CLIENT_ID=<対応するWeb Client ID>
```

`VITE_APP_API_ENDPOINT` および `VITE_APP_API_SIGNUP_ENDPOINT` が未設定だとフロントエンドが起動時にエラーになります。User Signup API を起動しない場合でも、上記のように値を入れておく必要があります（サインアップ操作を行わなければ実際の通信は発生しません）。

`VITE_APP_AUTH_USER_POOL_ID` と `VITE_APP_AUTH_USER_POOL_WEB_CLIENT_ID` を空のままにするとログインできません。

### 4. 開発サーバーの起動

```bash
bun run dev
```

[http://localhost:5173](http://localhost:5173) にアクセスし、Cognitoに登録済みのアカウントでログインするとフロントエンドが表示されます。

## ドキュメンテーションサーバーの起動

ドキュメンテーションサーバーを起動するには、以下のコマンドを実行します：

```bash
make run
```

その後、[http://localhost:8000](http://localhost:8000) でドキュメンテーションを確認します。
