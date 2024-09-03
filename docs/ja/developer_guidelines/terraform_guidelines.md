# Terraform ガイドライン

## スタイルガイド

Terraform公式からスタイルガイドが提供されています。
原則、以下のドキュメントに準拠するようにしてください。

[Style Guide \- Configuration Language \| Terraform \| HashiCorp Developer](https://developer.hashicorp.com/terraform/language/style)

## AWSリソースの命名規則

AWSリソースは以下の規約に従うようにしてください。

### 名前の構成要素

- {product} : 製品名 (ex. oqtopus)
- {org} : 組織名 (ex. example)
- {env} : 環境名 (ex. dev, stg, prd)
- {identifier} : 識別子 (ex. user, provider)

### 原則

例外がない限り、リソース名は以下のフォーマットに従うようにしてください。

```bash
{product}-{org}-{env}-{identifier}-{name}
```

例えば、USER APIのLambda関数の場合は以下のようになります。

```bash
oqtopus-example-user-api
```

## 参考資料

- [Future Enterprise Naming Convention Standards for AWS infrastructure resource](https://future-architect.github.io/coding-standards/documents/forAWSResource/AWS%E3%82%A4%E3%83%B3%E3%83%95%E3%83%A9%E3%83%AA%E3%82%BD%E3%83%BC%E3%82%B9%E5%91%BD%E5%90%8D%E8%A6%8F%E7%B4%84.html)
