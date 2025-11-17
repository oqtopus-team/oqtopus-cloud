# Backend API

Check out the [API documentation](../docs/en/developer_guidelines/backend.md) for details on the backend API.

## Run

- user API

  ```sh
  make run-user
  ```

- provider API

  ```sh
  make run-provider
  ```

- admin API

  ```sh
  make run-admin
  ```

- user_signup API

  ```sh
  make run-user_signup
  ```

## Host backend

- Build minio
  
  Before you host backend locally, you have to build minio image.

  ```sh
  make build-minio
  ```


- Start backend

  ```sh
  make up
  ```

- Stop backend

  ```sh
  make down
  ```
