# OpenAPI Specification

## 1. 命名規約

### 1.1 ファイル名の命名規則

- ファイル名は、原則`{tag}.{FooBar}.yaml`の形式とし、FooBarはキャメルケースとする
- ファイル名の`tag`は、APIのリソース名とする
- ファイル名の`FooBar`は、後続するAPIのメソッド名とする(例: `job/{job_id}`→`job.JobId.yaml`)
- `datamodel-code-generator`は、`{tag}.{FooBar}.yaml`の形式のファイルを読み込むため、`tag`は、APIのリソース名とし、`FooBar`は、自動生成されるコードのクラス名とする

#### 例1.1

```bash
tree
.
├── openapi.yaml
├── parameters
│   └── job.JobId.yaml
├── paths
│   ├── hello.yaml
│   ├── job.JobId.yaml
│   └── job.yaml
├── root.yaml
└── schemas
    ├── error.BadRequest.yaml
    ├── error.InternalServerError.yaml
    ├── error.NotFoundError.yaml
    ├── hello.HelloWorldResponse.yaml
    ├── job.GetJobResponse.yaml
    ├── job.PostJobRequest.yaml
    ├── job.PostJobResponse.yaml
    └── job.JobId.yaml
```

### 1.2 スキーマの命名規則

- スキーマの定義は、キャメルケースとする
- スキーマの各フィールド名は、`datamodel-code-generator`によって自動生成されるクラスのフィールド名となるため、スネークケースとする

#### 例1.2

```yaml
# schemas/job.GetJobResponse.yaml
description: detail of job response
type: object
properties:
  job_id:
    $ref: "job.JobId.yaml"
  code: {type: string, example: "OPENQASM 3; qubit[2] q; bit[2] c; h q[0]; cnot q[0], q[1]; c = measure q;"}
  device: {type: string, example: "Kawasaki"}
  n_qubits:
    type: integer
    example: null
  n_nodes:
    description: "Parameter valid only for 'simulator' devices"
    type: integer
    example: 12
  qubit_allocation:
    description: "Parameter valid only for QPU devices"
    type: object
    additionalProperties:
      type: integer
    example:
      "0": 12
      "1": 16
  skip_transpilation:
    type: boolean
    example: false
  seed_transpilation:
    description: "Parameter valid only if skipTranspilation is false"
    type: integer
    example: 873
  seed_simulation:
    description: "Parameter valid only for 'simulator' devices"
    type: integer
    example: 39058567
  ro_error_mitigation:
    description: "Parameter valid only for QPU devices"
    type: string
    enum: ["none", "pseudo_inverse", "least_square"]
    example: "pseudo_inverse"
  n_per_node:
    description: "Parameter valid only for simulator devices"
    type: integer
    minimum: 1
    example: 5
  simulation_opt:
    description: "Parameter valid only for simulator devices"
    type: object
    example: {
        optimization_method: "light",
        optimization_block_size: 1,
        optimization_swap_level: 1
      }
required: [
  jobId, code, device, skip_transpilation
]

```

## 2. 単一API定義書の生成

API Gatewayや各種ツールは、分割したyamlファイルを利用することができないため、RedoclyCLIを利用して単一のyamlファイルを生成する。
以下のコマンドを実行することで、`openapi.yml`が生成される。

```bash
make generate
```

## 3. API Gatewayへの利用

API GatewayではOpenAPIの定義書をインポートすることで、APIを作成することができる。

[AWS variables for OpenAPI import](https://docs.aws.amazon.com/apigateway/latest/developerguide/import-api-aws-variables.html)

この際に下記の通り、変数名を設定することでAPI Gateway側で適切に変数が設定される。

| Variable name   | Description                                                                 |
|-----------------|-----------------------------------------------------------------------------|
| AWS::AccountId  | The AWS account ID that imports the API—for example, 123456789012.           |
| AWS::Partition  | The AWS partition in which the API is imported. For standard AWS Regions, the partition is aws. |
| AWS::Region     | The AWS Region in which the API is imported—for example, us-east-2.          |

## 4. Terraformへの組み込み

Terraformを利用したAPIの定義更新は以下の記事が参考となる。
[How to use OpenAPI to deploy an API Gateway HTTP API](https://advancedweb.hu/how-to-use-openapi-with-api-gateway-rest-apis/#request-validation)
