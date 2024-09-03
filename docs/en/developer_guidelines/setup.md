
# Development Environment Setup

## Prerequisites

Before starting development, you need to install the following tools:

## Development Environment

| Tool                                          | Version                  | Description                           |
|------------------------------------------------|--------------------------|---------------------------------------|
| [Docker](https://docs.docker.com/get-docker/)  | -                        | Container virtualization platform     |
| [Docker Compose](https://docs.docker.com/compose/install/) | -            | Management of multiple Docker containers |
| [Python](https://www.python.org/downloads/)    | 3.12.4                   | Python programming language           |
| [Pyenv](https://github.com/pyenv/pyenv) (Optional) | -              | Python version management tool        |
| [Poetry](https://python-poetry.org/)           | -                        | Python dependency management tool     |

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
Python version: Python 3.12.4
Poetry version: Poetry (version 1.8.3)
Docker version: Docker version 26.1.4, build 5650f9b

```

## Setting Up the Python Environment

### Pyenv (Recommended)

To install Python 3.12.4, run the following command:

```bash
pyenv install 3.12.4
```

Next, set the Python version to 3.12.4:

```bash
pyenv local 3.12.4
```

### Poetry

To use the Python version installed with Pyenv, run the following command:

```bash
poetry env use ~/.pyenv/shims/python
```

To set up the Python environment, run the following command:

```bash
poetry config virtualenvs.in-project true
```

Next, install the dependencies:

```bash
poetry install
```

This will create a `.venv` in the root directory.

## Starting the Documentation Server

To start the documentation server, run the following command:

```bash
make run
```

Then, check the documentation at [http://localhost:8000](http://localhost:8000).
