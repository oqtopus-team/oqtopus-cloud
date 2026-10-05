# Backend API

Check out the [API documentation](../docs/en/developer_guidelines/backend.md) for details on the backend API.

## Run

```sh
make up
```

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
