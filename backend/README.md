# Backend API

Check out the [API documentation](../docs/en/developer_guidelines/backend.md) for details on the backend API.

## Run

```sh
make up
```

`make up` starts the DB, storage and otel-collector. `make infra-up` starts only the DB and storage, and `make infra-down` stops only those, and `make infra-status` shows whether they are running (it fails only when the state is unknown; run `uv run oqtopus-cloud-infra status` to get the exit code); `make down` removes all containers and the network of this compose project. The data of the DB and the storage lives in volumes and survives `stop` and `down`; to discard it, run `docker compose down -v`.

- user API

  ```sh
  make run-user
  ```

- provider API

  ```sh
  make run-provider
  ```


### Start commands and uvicorn options

Each service has a command defined in `[project.scripts]` of `pyproject.toml`:

| Command | Service |
|---------|---------|
| `oqtopus-cloud-user-api` | User API |
| `oqtopus-cloud-provider-api` | Provider API |
| `oqtopus-cloud-admin-api` | Admin API |
| `oqtopus-cloud-user-signup-api` | User Signup API |
| `oqtopus-cloud-worker` | Pending jobs updater (local scheduler) |
| `oqtopus-cloud-infra` | Start, stop and inspect the local DB and storage |

> [!IMPORTANT]
> `oqtopus-cli` (`cloud-local`) depends on these command names. Renaming them is a breaking change.

The API commands accept any option of `uvicorn --help` through environment variables:

- `<SCOPE>_<OPTION>` sets it for one API (e.g. `USER_API_LOG_LEVEL=info`).
- `UVICORN_<OPTION>` sets it for all APIs. `<SCOPE>_<OPTION>` takes precedence.
- Only names of real uvicorn options are used; other variables with the same prefix (e.g. `USER_API_URL`) are ignored. An empty value is treated as unset.

`POWERTOOLS_SERVICE_NAME` and `POWERTOOLS_METRICS_NAMESPACE` can be set per API in the same way (`<SCOPE>_POWERTOOLS_SERVICE_NAME`, `<SCOPE>_POWERTOOLS_METRICS_NAMESPACE`). The default is the API's service name, e.g. `user-api`.

`SCOPE` is one of `USER_API`, `PROVIDER_API`, `ADMIN_API` or `USER_SIGNUP_API`.
Without any setting, the commands listen on `127.0.0.1` with reload disabled. The port has no default in the command and must be set with `<SCOPE>_PORT` (`make run-*` takes it from the Makefile: 8080 / 8888 / 8889 / 8890).
`make run-*` defaults to `HOST=0.0.0.0`, `RELOAD=true` and `LOG_LEVEL=debug`, which you can override:

```sh
make run-user USER_API_HOST=127.0.0.1 USER_API_LOG_LEVEL=info
```

### `oqtopus-cloud-infra`

`oqtopus-cloud-infra <start|stop|status>` starts, stops and inspects the local DB and object storage as one unit (job payloads and `device_info` live only in the storage, while the DB rows refer to them). Call it after `uv sync --no-dev`, with `uv run --no-sync oqtopus-cloud-infra ...`.

Input (environment variables):

| Variable | Meaning |
|----------|---------|
| `STORAGE_STACK` | Stack name: `seaweedfs` or `minio`. Unset, empty or unknown ends with exit code 6 (4 for `status`). There is no default in the command. |
| `COMPOSE_PROJECT_NAME` | The standard docker compose variable. |
| `DB_HOST`, `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD`, `STORAGE_*` | Settings of the DB and of each stack. The caller exports them. `start` waits until `DB_HOST` (`host` or `host:port`; port 3306 if omitted) accepts connections, the address Alembic and the seed script connect to. |

`STORAGE_DRIVER` is set from `STORAGE_STACK` (any existing value is overwritten), here and in the API and worker commands. If `STORAGE_STACK` is unset, the API and worker commands leave `STORAGE_DRIVER` alone.

| Subcommand | Guarantee on exit code 0 |
|------------|--------------------------|
| `start` | The DB accepts connections, the schema is up to date and the initial data is seeded. Idempotent. Services of other stacks are stopped first. |
| `stop` | The DB and the storage containers of all stacks are stopped. The containers and the volumes (the data) are kept, and other containers and networks are untouched. Idempotent. |
| `status` | Reports the state through the exit code; stdout is for humans and its format is not part of the contract. |

Exit codes (LSB init-script conventions):

| Subcommand | Code | Meaning |
|------------|------|---------|
| `start` / `stop` | 0 | Success (also when already running / stopped) |
| `start` / `stop` | 1 | Generic error, including a timeout while waiting |
| any | 2 | Invalid arguments |
| `start` / `stop` | 5 | A required program (docker) is missing |
| `start` / `stop` | 6 | Missing configuration (`STORAGE_STACK` or a `DB_*` setting, including an invalid port in `DB_HOST`) |
| `status` | 0 | Running: the DB and the stack's main service are up |
| `status` | 3 | Stopped, including partially running |
| `status` | 4 | Unknown (docker unusable, invalid configuration) |

Logs go to stderr; stdout is used only for `status`. The one-shot init services (`seaweedfs-bucket-init`, `mc`) are not part of `status`. `oqtopus-cloud-infra` is depended on by `oqtopus-cli`; renaming it is a breaking change.
