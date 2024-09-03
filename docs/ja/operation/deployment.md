# デプロイメント

本章では、サービスのデプロイメントについて、解説します。

## AWS環境のデプロイ

AWS環境の構築には、[Terraform](https://www.terraform.io/) を使用します。

terraformディレクトリには、プロジェクトのAWS環境をデプロイするためのコードが含まれています。

```bash
.
├── Makefile
├── README.md
├── infrastructure
│   ├── Makefile
│   ├── README.md
│   ├── example-dev
│   └── modules
└── service
    ├── Makefile
    ├── README.md
    ├── example-dev
    └── modules

7 directories, 6 files
```

infrastructureディレクトリには、ネットワークやデータストアなどのインフラ環境をデプロイするためのコードが含まれています。
一方で比較的頻繁に設定が変わる層は、serviceディレクトリに切り出しています。

まずはネットワークやデータストアなどのインフラ環境をデプロイするための手順について説明します。

### インフラ層のデプロイ

terraform/infrastructure/example-devが各環境のデプロイメントディレクトリです。
stateファイルはS3で管理されるため、S3バケットを作成する必要があります。
以下のコマンドを実行して、S3バケットを作成します。

```bash
aws s3api create-bucket --bucket tfstate.oqtopus-example-dev --profile example-dev --region ap-northeast-1 --create-bucket-configuration LocationConstraint=ap-northeast-1
```

次に、terraformの設定ファイルを用意します。以下の2つのファイルを作成します。

```hcl:infrastructure/example-dev/example-dev.tfbackend
# infrastructure/example-dev.tfbackend
bucket         = "tfstate.oqtopus-example-dev"
key            = "infrastructure.tfstate"
encrypt        = true
profile        = "example-dev"
region         = "ap-northeast-1"
```

```hcl:infrastructure/example-dev/terraform.tfvars
# infrastructure/terraform.tfvars
product="oqtopus"
org="example"
env="dev"
region = "ap-northeast-1"
```

それぞれ、stateファイルの保存先と、環境変数を設定しています。

`terraform init`で初期化を行います。以下のコマンドを実行します。

```bash
cd infrastructure/example-dev
terraform init -backend-config=example-dev.tfbackend
```

その後`terrafom apply`でデプロイを行います。

```bash
terraform apply
```

### サービス層のデプロイ

次に、サービスのデプロイについて説明します。

先ほどと同様に、terraformの設定ファイルを用意します。以下の2つのファイルを作成します。

```hcl:service/example-dev/example-dev.tfbackend
# service/example-dev.tfbackend
bucket         = "tfstate.oqtopus-example-dev"
key            = "service.tfstate"
encrypt        = true
profile        = "example-dev"
region         = "ap-northeast-1"
```

```hcl:service/example-dev/terraform.tfvars
# service/terraform.tfvars
product          = "oqtopus"
org              = "example"
env              = "dev"
region           = "ap-northeast-1"
state_bucket     = "tfstate.oqtopus-example-dev"
remote_state_key = "infrastructure.tfstate"
profile          = "example-dev"
```

`terraform init`で初期化を行います。以下のコマンドを実行します。

```bash
cd service/example-dev
terraform init -backend-config=example-dev.tfbackend
```

## アプリケーションのデプロイ

### マルチアカウント構成

マルチアカウントでのデプロイメントを行うために環境ごとにディレクトリを分割しています。

```bash
├── README.md
├── example-dev
│   ├── Makefile
│   └── .env
└── foo-dev
    ├── Makefile
    └── .env
```

続いて、各ディレクトリの環境変数の設定とデプロイ方法について説明します。

### 環境変数の設定

サービスをデプロイする前に、次の内容で `.env` ファイルを作成する必要があります。

```.env
PROFILE=foo-dev

CLIENT_API_URL=https://foo-bar.execute-api.ap-northeast-1.amazonaws.com
CLIENT_COGNITO_USER_POOL_ID=ap-northeast-1_foobar
CLIENT_COGNITO_CLIENT_ID=foobar
CLIENT_COGNITO_USER_NAME=foobar
CLIENT_COGNITO_USER_PASSWORD=FooBar@123

SERVER_API_URL=https://baz-qux.execute-api.ap-northeast-1.amazonaws.com
SERVER_COGNITO_USER_POOL_ID=ap-northeast-1_bazqux
SERVER_COGNITO_CLIENT_ID=bazqux
SERVER_COGNITO_USER_NAME=bazqux
SERVER_COGNITO_USER_PASSWORD=BazQux@123
```

ディレクトリ構成は以下のようになります:

```bash
foo-dev
├── .env
└── Makefile
```

### サービスのデプロイ

デプロイするには、次のコマンドを実行します:

```bash
make deploy-usr
make deploy-provider
```

### サービスのテスト

サービスのテストを行うには、次のコマンドを実行します:

```bash
make test-user
make test-provider
```

## コマンド一覧

```bash
make help
Usage: make [target]

Available targets:

all-user                     Deploy User API Lambda Package and Test
all-provider                     Deploy Provider API Lambda Package and Test
all                            Deploy All Lambda Packages and Test
clean                          Clean up Binaries
deploy-all                     Deploy All Lambda Packages
deploy-user                  Deploy User API Lambda Package
deploy-provider                  Deploy Provider API Lambda Package
help                           Show this help message
test-all                       Test All APIs(connect to the dev environment)
test-user                    Test User API(connect to the dev environment)
test-provider                    Test Provider API API(connect to the dev environment)
zip-all                        Build All Lambda Packages
zip-user                     Build User API Lambda Package
zip-provider                     Build Provider API Lambda Package
```
