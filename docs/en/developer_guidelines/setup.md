
# Development Environment Setup

## Prerequisites

Before starting development, you need to install the following tools:

## Development Environment

| Tool                                          | Version                  | Description                           |
|------------------------------------------------|--------------------------|---------------------------------------|
| [Docker](https://docs.docker.com/get-docker/)  | -                        | Container virtualization platform     |
| [Docker Compose](https://docs.docker.com/compose/install/) | -            | Management of multiple Docker containers |
| [Python](https://www.python.org/downloads/)    | 3.12.3                   | Python programming language           |
| [Pyenv](https://github.com/pyenv/pyenv) (Optional) | -              | Python version management tool        |
| [uv](https://docs.astral.sh/uv/)               | -                        | Python lightweight package management tool     |

To start development, clone the repository and install dependencies:

```bash
git clone https://github.com/oqtopus-team/oqtopus-cloud.git
```

## Installing Aqua

Aqua is a tool that supports project management. For more details, check [here](https://aquaproj.github.io/).

To install Aqua, run the following command:

```bash
make setup-aqua
```

The message at the end of the command will instruct to add aqua to the PATH, so be sure to follow the instructions.

## Verifying the Environment

To verify the environment, run the following command:

```bash
make doctor
```

After running the above steps, you will get output similar to the following:

```bash
make doctor
Checking the environment...
Aqua version: aqua version 2.29.0 (9ff65378f0c6197e3130a20f6d978b8a3042b463)
Python version: Python 3.12.3
uv version: uv 0.7.16 (b6b7409d1 2025-06-27)
Docker version: Docker version 26.1.4, build 5650f9b

```

## Generating Git Hooks File

This repository uses the Git hook `pre-commit` to scan for credentials.

To generate the script, run the following command:

```bash
make setup-hooks
```

The script will be generated in `.git/hooks/pre-commit`.

## Setting Up the Python Environment

### Pyenv (Recommended)

To install Python 3.12.3, run the following command:

```bash
pyenv install 3.12.3
```

Next, set the Python version to 3.12.3:

```bash
pyenv local 3.12.3
```

### uv

To set up **uv** as part of the environment setup, run the following command:

```
make setup-uv
```

This command is required to use the Python version installed with Pyenv, to set up the Python environment, and to install dependencies. This will create a `.venv` in the root directory.

## Running the Backend Locally

The following steps each run in a separate terminal. In every terminal, `cd backend` first before running the make commands.

### 1. Start DB and SeaweedFS (Terminal 1)

```bash
cd backend
make up
```

MySQL (port 3306) and SeaweedFS (S3 API port 8333, web UI port 9333/9001) will start.
On the first run, DB initialization (table creation and test data insertion) is performed automatically.

`make up` starts the containers in the background and exits. Stop them with `make down`.

### 2. Start the APIs

> [!NOTE]
> When the frontend is served from `http://localhost:5173`, you must include that origin in `ALLOW_ORIGINS` to satisfy CORS. The Makefile default (`http://127.0.0.1:8000`) alone will be blocked by the browser.

Open additional terminals and start the User / Provider APIs. Override `ALLOW_ORIGINS` so the local frontend can reach them:

```bash
# Terminal 2: User API (for job submission)
cd backend
ALLOW_ORIGINS=http://127.0.0.1:8000,http://localhost:5173 make run-user
```

```bash
# Terminal 3: Provider API (for backend instance communication)
cd backend
ALLOW_ORIGINS=http://127.0.0.1:8000,http://localhost:5173 make run-provider
```

If you want to exercise the signup flow, also start the User Signup API:

```bash
# Terminal 4 (optional): User Signup API
cd backend
ALLOW_ORIGINS=http://127.0.0.1:8000,http://localhost:5173 make run-user_signup
```

| API | Port | Purpose |
|-----|------|---------|
| User API | 8080 | Job submission and result retrieval |
| Provider API | 8888 | Communication with backend instances |
| User Signup API | 8890 | Sign-up and user registration (optional) |

### 3. Verify

Check the API documentation (Swagger UI):

- User API: [http://localhost:8080/docs](http://localhost:8080/docs)
- Provider API: [http://localhost:8888/docs](http://localhost:8888/docs)
- User Signup API: [http://localhost:8890/docs](http://localhost:8890/docs) (if started)

To exercise the storage path on its own, `make check-presigned-post` is available.
It is not needed for normal development. See
[Storage Backend Selection](../architecture/storage_backend_selection.md) for details.

## Running the Frontend Locally

You can run the [OQTOPUS Frontend](https://github.com/oqtopus-team/oqtopus-frontend) locally and connect it to the local backend started above.

> [!IMPORTANT]
> The frontend uses AWS Cognito for authentication. Even when running locally, you need an account registered in an existing Cognito User Pool (e.g., the `oqtopus-dev` environment) to log in.
> Without a registered account, you cannot proceed past the login screen. Please contact the operations team if you need an account.

### Prerequisites

- [bun](https://bun.sh/) installed
- The User API (port 8080) running, as described in "Running the Backend Locally", with `ALLOW_ORIGINS` including `http://localhost:5173`
- An accessible Cognito User Pool ID / Web Client ID and a registered account
- The User Signup API (port 8890) running if you want to exercise the signup flow

### 1. Clone the Repository

```bash
git clone https://github.com/oqtopus-team/oqtopus-frontend.git
cd oqtopus-frontend
```

### 2. Install Dependencies

```bash
bun install
```

### 3. Configure Environment Variables

Edit the `.env` file to point to the local backend and configure Cognito for authentication:

```env
VITE_APP_API_ENDPOINT=http://localhost:8080
VITE_APP_API_SIGNUP_ENDPOINT=http://localhost:8890
VITE_APP_AUTH_REGION=ap-northeast-1
VITE_APP_AUTH_USER_POOL_ID=<your Cognito User Pool ID>
VITE_APP_AUTH_USER_POOL_WEB_CLIENT_ID=<corresponding Web Client ID>
```

If `VITE_APP_API_ENDPOINT` or `VITE_APP_API_SIGNUP_ENDPOINT` is unset, the frontend will throw at startup. Set these even if you do not run the User Signup API (no traffic will be sent to it unless you trigger a signup action).

If `VITE_APP_AUTH_USER_POOL_ID` and `VITE_APP_AUTH_USER_POOL_WEB_CLIENT_ID` are left empty, you will not be able to log in.

### 4. Start the Development Server

```bash
bun run dev
```

Open [http://localhost:5173](http://localhost:5173) and log in with an account registered in Cognito to access the frontend.

## Starting the Documentation Server

To start the documentation server, run the following command:

```bash
make run
```

Then, check the documentation at [http://localhost:8000](http://localhost:8000).
