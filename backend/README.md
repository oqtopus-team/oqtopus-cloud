# Backend API

Check out the [API documentation](../docs/en/developer_guidelines/backend.md) for details on the backend API.

## Run

The backend Makefile is placed at `oqtopus-cloud/backend/Makefile` ([here](./Makefile)).

### DB

#### Start the DB

  To start the DB, execute the command below:

  ```sh
  make up
  ```

  This command will run the docker container of DB in background, and execute migration to initialize.

#### Stop the DB

  To stop the DB, execute the command below:

  ```sh
  make down
  ```

### API

#### user API

  To start the User API, execute the command below:

  ```sh
  make run-user
  ```

#### provider API

  To start the Provider API, execute the command below:

  ```sh
  make run-provider
  ```

#### admin API

  To start the Admin API, execute the command below:

  ```sh
  make run-admin
  ```

#### user_signup API

  To start the user_signup API, execute the command below:

  ```sh
  make run-user_signup
  ```

