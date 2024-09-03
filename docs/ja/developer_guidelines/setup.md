# 開発環境のセットアップ

## 前提条件

開発を始める前に、以下のツールをインストールする必要があります：

## 開発環境

| ツール                                         | バージョン               | 説明                           |
|------------------------------------------------|--------------------------|-------------------------------|
| [Docker](https://docs.docker.com/get-docker/)  | -                        | コンテナ仮想化プラットフォーム |
| [Docker Compose](https://docs.docker.com/compose/install/) | -            | 複数のDockerコンテナの管理   |
| [Python](https://www.python.org/downloads/)    | 3.12.4                   | Pythonのプログラミング言語    |
| [Pyenv](https://github.com/pyenv/pyenv) (Optional) | -              | Pythonのバージョン管理ツール |
| [Poetry](https://python-poetry.org/)           | -                        | Pythonの依存関係管理ツール    |

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
Python version: Python 3.12.4
Poetry version: Poetry (version 1.8.3)
Docker version: Docker version 26.1.4, build 5650f9b

```

## Python環境のセットアップ

### Pyenv(推奨)

Python 3.12.4をインストールするには、以下のコマンドを実行します：

```bash
pyenv install 3.12.4
```

次に、Pythonのバージョンを3.12.4に設定します：

```bash
pyenv local 3.12.4
```

### Poetry

PyenvでインストールしたPythonバージョンを使用するには、以下のコマンドを実行します：

```bash
poetry env use ~/.pyenv/shims/python
```

Python環境をセットアップするには、以下のコマンドを実行します：

```bash
poetry config virtualenvs.in-project true
```

次に、依存関係をインストールします：

```bash
poetry install
```

これで、ルートディレクトリに.venvが作成されます。

## ドキュメンテーションサーバーの起動

ドキュメンテーションサーバーを起動するには、以下のコマンドを実行します：

```bash
make run
```

その後、[http://localhost:8000](http://localhost:8000) でドキュメンテーションを確認します。
