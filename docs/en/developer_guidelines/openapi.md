
# OpenAPI Specification-Based Code Generation

## Structure

The OpenAPI Specification (OAS) is placed under the `backend/oas` directory with the following structure:

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

The role and naming conventions for each file are as follows:

| File Name         | Role                                  | Naming Convention       |
|-------------------|----------------------------------------|-------------------------|
| root.yaml         | Root file for OAS                      | Fixed as `root.yaml`    |
| paths/*.yaml      | Files defining API endpoints. The file granularity is by resource. | `{resource_name}.yaml`  |
| schemas/*.yaml    | Files defining request and response schemas. The schema definitions are converted to Python data models using `datamodel-code-generator` (described later). | `{resource_name}.yaml`  |
| openapi.yaml      | A single OAS file generated based on `root.yaml`. This document renders `openapi.yaml`. | Fixed as `openapi.yaml` |

## How to Write `root.yaml`

### Sample

`root.yaml` is the root file of the OAS and should have the following structure:

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

### Notes

- `paths` definitions should refer to files placed in the `paths` directory.
- To improve readability, divide `paths` definitions by resource.
- Define path parameters in camelCase.
- The paths directly under the resource should refer to the `root` in the files placed in the `paths` directory.
- Deeper nested paths should be defined as `root.{path_name}.{path_name}`.

!!! note
    Define as `task/{taskId}` instead of `task/{task_id}`.

## How to Write `paths`

### Sample

The `paths` directory should be split into files by resource. Each file should have the following structure:

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
              detail: An internal system error has occurred.

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

### Notes

- The path directly under a resource should be `root`.
- Deeper nested paths should be defined as `root.{path_name}.{path_name}`.
- Define path parameters in camelCase.
- Include examples for both request and response.
- Use `$ref` to reference schema files located in the `schemas` directory.
- Ensure the file granularity for schemas matches the resource.

## How to Write `schemas`

### Sample

The `schemas` directory should be split into files by resource. Each file should have the following structure:

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

### Notes

- The schema file name should match the resource name.
- Schema definitions should follow the `{resource_name}.{schema_name}` format. The resource name will be generated as `{resource_name}.py` by `datamodel-code-generator`.
- Schema names are automatically generated as class names by `datamodel-code-generator`, so use PascalCase.
- Schema field names are automatically generated as class field names, so use snake_case.
- Since `description` and `example` will be reflected in the generated code, write them appropriately.

## Generating a Single API Definition File

Run `make generate-all` to generate `openapi.yaml`.

```bash
make generate-all
```

Below is a list of commands defined in `backend/oas/Makefile`.

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

## Displaying API Documentation with Swagger UI

In this document, `openapi.yaml` generated is rendered with Swagger UI.

- [User API](../../oas/user/README.md)
- [Provider API](../../oas/provider/README.md)

> [!NOTE]
> Swagger UI is set up with endpoints in the development environment, so you can send requests on Swagger UI by running `make run-user` or `make run-provider` under the backend directory.

## Generating Python Data Models with `datamodel-code-generator`

Below is a list of commands defined in the `backend/Makefile`.

```bash
make help
Usage: make [target]

Available targets:

down                           Stop the DB
fmt                            Format code
generate-all-schema            Generate user and  schemas
generate-user-schema           Generate user schema
generate-provider-schema       Generate provider schema
help                           Show this help message
lint                           Run linters
run-user                       Start the User API
run-provider                   Start the Provider API
test                           Run tests
up                             Start the DB
```

By running `make generate-all-schema`, Python data models will be generated in the `backend/oas/oqtopus_cloud/user/schemas` and `backend/oas/oqtopus_cloud/provider/schemas` directories.

```bash
make generate-all-schema
```

The generated data models will look like the following:

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
    Detail of task response
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
