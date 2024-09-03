# OpenAPI 仕様書によるコード生成

## 構成

OpenAPI仕様書(以下oas)はbackend/oas配下に以下の構成で配置する。

```bash
tree
.
├── openapi.yaml
├── paths
│   ├── hello.yaml
│   └── task.yaml
├── root.yaml
└── schemas
    ├── error.yaml
    ├── hello.yaml
    └── task.yaml
```

それぞれのファイルの役割と命名規則は以下の通り。

| ファイル名 | 役割 | ファイルの命名規則 |
|-------------------|-----|-----------------|
| root.yaml         | oasのルートファイル | `root.yaml`固定 |
| paths/*yaml             | APIのエンドポイントを定義するファイル、ファイルの粒度はリソースとする | `{リソース名}.yaml`とする |
| schemas/*.yaml           | レスポンスやリクエストのスキーマを定義するファイル、schemasの定義はdatamodel-code-generator(後述)によって、Pythonのデータモデルに変換される | `{リソース名}.yaml` |
| openapi.yaml      | root.yamlをもとに生成される単一のoasファイル本ドキュメントでは、`openapi.yaml`をレンダリングしている | `openapi.yaml`固定 |

## root.yamlの書き方

### サンプル

`root.yaml`は、oasのルートファイルであり、以下のような構成とする。

```yaml
#root.yaml
openapi: 3.0.1
info:
  title: OQTOPUS Cloud User API
  version: '1.0'
  contact:
    name: oqtopus-team
    email: oqtopus-team[at]googlegroups.com
  description: OQTOPUS Cloud User API. This API is used to interact with the OQTOPUS Cloud service. The API provides endpoints to manage devices, tasks, and results.
  license:
    name: Apache 2.0
    url: https://www.apache.org/licenses/LICENSE-2.0.html
servers:
  - url: http://localhost:8080
    description: Local server url
paths:
  /hello:
    $ref: ./paths/hello.yaml#/root
  /hello/{name}:
    $ref: ./paths/hello.yaml#/root.name
  /task:
    $ref: ./paths/task.yaml#/root
  /task/{taskId}:
    $ref: ./paths/task.yaml#/root.taskId
```

### 注意点

- `paths`の定義は、`paths`ディレクトリに配置されたファイルを参照するようにする。
- pathsの定義は、リソースごとに分割することで、可読性を向上させる。
- パスパラメータはキャメルケースで定義する。
- リソース直下のパスは、`paths`ディレクトリに配置されたファイルの`root`を参照するようにする。
- ネストの深いパスは`root.{パス名}.{パス名}`のように定義する。

> [!NOTE]
> `task/{task_id}`ではなく、`task/{taskId}`とすること。

## pathsの書き方

### サンプル

`paths`ディレクトリは、リソースごとにファイルを分割する。各ファイルは以下のような構成とする。

```yaml
root:
  post:
    tags:
      - task
    summary: post task
    description: post task
    operationId: postTask
    security: []
    requestBody:
      description: "Quantum task to be submitted"
      content:
        application/json:
          schema:
            $ref: "../schemas/task.yaml#/task.PostTaskRequest"
          example:
            code: "OPENQASM 3; qubit[2] q; bit[2] c; h q[0]; cnot q[0], q[1]; c = measure q;"
            name: "Bell State Sampling"
            device: "Kawasaki"
            n_nodes: 12
            n_shots: 1000
            skip_transpilation: false
            seed_transpilation: 873
            seed_simulation: 39058567
            n_per_node: 2
            simulation_opt: {
              optimization_method: "light",
              optimization_blockSize: 1,
              optimization_swapLevel: 1,
              }
            note: "Bell State Sampling Example"
    responses:
      '200':
        description: "Task submitted"
        content:
          application/json:
            schema:
              type: object
              properties:
                task_id:
                  $ref: "../schemas/task.yaml#/task.TaskId"
              required: [
                task_id
              ]
      '500':
        description: Internal Server Error
        content:
          application/json:
            schema:
              $ref: '../schemas/error.yaml#/error.InternalServerError'
            example:
              detail: システムエラーが発生しました。

root.taskId:
  get:
    tags:
      - task
    summary: get task
    description: get task
    operationId: getTaskByTaskId
    security: []
    parameters:
      - in: path
        name: taskId
        description: "Quantum task identifier"
        required: true
        schema:
          $ref: "../schemas/task.yaml#/task.TaskId"
    responses:
      '200':
        description: task response
        content:
          application/json:
            schema:
              $ref: '../schemas/task.yaml#/task.GetTaskResponse'
            example:
              task_id: 7af020f6-2e38-4d70-8cf0-4349650ea08c
              code: OPENQASM 3; qubit[2] q; bit[2] c; h q[0]; cnot q[0], q[1]; c = measure q;
              device: Kawasaki
              n_qubits: 12
              n_nodes: 12
              skip_transpilation: false
              seed_transpilation: 873
              seed_simulation: 39058567
              n_per_node: 2
              simulation_opt: {
                optimization_method: "light",
                optimization_block_size: 1,
                optimization_swap_level: 1
              }
      '400':
        description: Bad Request
        content:
          application/json:
            schema:
              $ref: '../schemas/error.yaml#/error.BadRequest'
            example:
              detail: invalid task_id
      '404':
        description: Not Found
        content:
          application/json:
            schema:
              $ref: '../schemas/error.yaml#/error.NotFoundError'
            example:
              detail: task not found with given id
      '500':
        description: Internal Server Error
        content:
          application/json:
            schema:
              $ref: '../schemas/error.yaml#/error.InternalServerError'
            example:
              detail: internal server error
```

### 注意点

- リソース直下のパスは、`root`とする。
- ネストの深いパスは、`root.{パス名}.{パス名}`のように定義する。
- パスパラメータはキャメルケースで定義する。
- リクエストとレスポンスはexampleを記載する。
- スキーマは、`$ref`を利用して、`schemas`ディレクトリに配置されたファイルを参照するようにする。
- スキーマのファイル粒度もリソースに揃える。

## schemasの書き方

### サンプル

`schemas`ディレクトリには、リソースごとにファイルを分割する。各ファイルは以下のような構成とする。

```yaml
task.TaskId:
  type: string
  format: uuid
  example: "7af020f6-2e38-4d70-8cf0-4349650ea08c"

task.GetTaskResponse:
  description: detail of task response
  type: object
  properties:
    task_id:
      $ref: "task.yaml#/task.TaskId"
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
    task_id, code, device, skip_transpilation
  ]


task.PostTaskRequest:
  type: object
  properties:
    code: {type: string, example: "OPENQASM 3; qubit[2] q; bit[2] c; h q[0]; cnot q[0], q[1]; c = measure q;"}
    name:
      type: string
      example: "Bell State Sampling"
    device:
      type: string
      example: "Kawasaki"
    n_qubits:
      description: "Parameter exclusive with nNodes"
      type: integer
    n_nodes:
      description: "Parameter exclusive with nQubits<br/>Parameter valid only for 'simulator' devices"
      type: integer
      example: 12
      default: 1
    n_shots:
      type: integer
      minimum: 1
      maximum: 1e7
      example: "1000"
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
      default: false
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
      default: "none"
      example: "pseudo_inverse"
    n_per_node:
      description: "Parameter valid only for simulator devices"
      type: integer
      minimum: 1
      default: 1
      example: 5
    simulation_opt:
      description: "Parameter valid only for simulator devices"
      type: object
      example: {
          optimization_method: "light",
          optimization_block_size: 1,
          optimization_swap_level: 1
        }
    note:
      type: string
      example: "Bell State Sampling Example"
  required: [
    code, device, n_shots
  ]
```

### 注意点

- スキーマのファイル名は、リソース名と一致させる。
- スキーマ定義は`{リソース名}.{スキーマ名}`とする。リソース名は`datamodel-code-generator`によって`リソース名.py`として生成される。
- スキーマ名は、`datamodel-code-generator`によって自動生成され、クラス名となるため、パスカルケースとする。
- スキーマのフィールド名は、`datamodel-code-generator`によって自動生成されるクラスのフィールド名となるため、スネークケースとする。
- descriptionやexampleは自動生成されるコードに反映されるため、適切に記載する。

## 単一API定義書の生成

`make generate-all`を実行することで、`openapi.yaml`が生成される。

```bash
make generate-all
```

以下、`backend/oas/Makefile`に定義したコマンド一覧である。

```bash
make help
Usage: make [target]

Available targets:

generate-all                   Generate user and provider openapi.yaml
generate-user                Generate user openapi.yaml
generate-provider                Generate provider openapi.yaml
help                           Show this help message
lint-all                       Lint user and provider
lint-user                    Lint user openapi.yaml
lint-provider                    Lint provider openapi.yaml
```

## Swagger UIによるAPIドキュメントの表示

本ドキュメントで、生成した`openapi.yaml`をSwagger UIしている。

- [User API](../../oas/user/README.md)
- [Provider API](../../oas/provider/README.md)

> [!NOTE]
> Swagger UIは、開発環境にエンドポイントを設定しているため、backend配下で`make run-user`または`make run-provider`を実行することで、実際にSwagger UI上でリクエストを送信することができます。

## datamodel-code-generatorによるPythonデータモデルの生成

以下、`backend/Makefile`に定義したコマンド一覧である。

```bash
make help
Usage: make [target]

Available targets:

down                           Stop the DB
fmt                            Format code
generate-all-schema            Generate user and server schemas
generate-user-schema         Generate user schema
generate-provider-schema         Generate provider schema
help                           Show this help message
lint                           Run linters
run-user                     Start the User API
run-provider                     Start the Provider API
test                           Run tests
up                             Start the DB
```

`make generate-all-schema`を実行することで、`backend/oas/oqtopus_cloud/user/schemas`と`backend/oas/oqtopus_cloud/provider/schemas`ディレクトリにPythonデータモデルが生成される。

```bash
make generate-all-schema
```

出力されるデータモデルは以下のようになる。

```python
# generated by datamodel-codegen:
#   filename:  openapi.yaml
#   timestamp: 2024-04-04T03:36:51+00:00
#   version:   0.25.5

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, RootModel


class GetTaskResponse(BaseModel):
    """
    detail of task response
    """

    task_id: TaskId
    code: Annotated[
        str,
        Field(
            examples=[
                "OPENQASM 3; qubit[2] q; bit[2] c; h q[0]; cnot q[0], q[1]; c = measure q;"
            ]
        ),
    ]
    device: Annotated[str, Field(examples=["Kawasaki"])]
    n_qubits: Annotated[Optional[int], Field(None, examples=[None])]
    n_nodes: Annotated[Optional[int], Field(None, examples=[12])]
    """
    Parameter valid only for 'simulator' devices
    """
    qubit_allocation: Annotated[
        Optional[Dict[str, int]], Field(None, examples=[{"0": 12, "1": 16}])
    ]
    """
    Parameter valid only for QPU devices
    """
    skip_transpilation: Annotated[bool, Field(examples=[False])]
    seed_transpilation: Annotated[Optional[int], Field(None, examples=[873])]
    """
    Parameter valid only if skipTranspilation is false
    """
    seed_simulation: Annotated[Optional[int], Field(None, examples=[39058567])]
    """
    Parameter valid only for 'simulator' devices
    """
    ro_error_mitigation: Annotated[
        Optional[RoErrorMitigation], Field("none", examples=["pseudo_inverse"])
    ]
    """
    Parameter valid only for QPU devices
    """
    n_per_node: Annotated[Optional[int], Field(None, examples=[5], ge=1)]
    """
    Parameter valid only for simulator devices
    """
    simulation_opt: Annotated[
        Optional[Dict[str, Any]],
        Field(
            None,
            examples=[
                {
                    "optimization_method": "light",
                    "optimization_block_size": 1,
                    "optimization_swap_level": 1,
                }
            ],
        ),
    ]
    """
    Parameter valid only for simulator devices
    """


class PostTaskRequest(BaseModel):
    code: Annotated[
        str,
        Field(
            examples=[
                "OPENQASM 3; qubit[2] q; bit[2] c; h q[0]; cnot q[0], q[1]; c = measure q;"
            ]
        ),
    ]
    name: Annotated[Optional[str], Field(None, examples=["Bell State Sampling"])]
    device: Annotated[str, Field(examples=["Kawasaki"])]
    n_qubits: Optional[int] = None
    """
    Parameter exclusive with nNodes
    """
    n_nodes: Annotated[Optional[int], Field(1, examples=[12])]
    """
    Parameter exclusive with nQubits<br/>Parameter valid only for 'simulator' devices
    """
    n_shots: Annotated[int, Field(examples=["1000"], ge=1, le=10000000)]
    qubit_allocation: Annotated[
        Optional[Dict[str, int]], Field(None, examples=[{"0": 12, "1": 16}])
    ]
    """
    Parameter valid only for QPU devices
    """
    skip_transpilation: Annotated[Optional[bool], Field(False, examples=[False])]
    seed_transpilation: Annotated[Optional[int], Field(None, examples=[873])]
    """
    Parameter valid only if skipTranspilation is false
    """
    seed_simulation: Annotated[Optional[int], Field(None, examples=[39058567])]
    """
    Parameter valid only for 'simulator' devices
    """
    ro_error_mitigation: Annotated[
        Optional[RoErrorMitigation], Field("none", examples=["pseudo_inverse"])
    ]
    """
    Parameter valid only for QPU devices
    """
    n_per_node: Annotated[Optional[int], Field(1, examples=[5], ge=1)]
    """
    Parameter valid only for simulator devices
    """
    simulation_opt: Annotated[
        Optional[Dict[str, Any]],
        Field(
            None,
            examples=[
                {
                    "optimization_method": "light",
                    "optimization_block_size": 1,
                    "optimization_swap_level": 1,
                }
            ],
        ),
    ]
    """
    Parameter valid only for simulator devices
    """
    note: Annotated[
        Optional[str], Field(None, examples=["Bell State Sampling Example"])
    ]


class RoErrorMitigation(Enum):
    """
    Parameter valid only for QPU devices
    """

    none = "none"
    pseudo_inverse = "pseudo_inverse"
    least_square = "least_square"


class TaskId(RootModel[UUID]):
    root: Annotated[UUID, Field(examples=["7af020f6-2e38-4d70-8cf0-4349650ea08c"])]
```
