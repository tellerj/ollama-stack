# 01: Project Architecture

This document defines the file and directory structure for the new Python-based CLI tool.

## 1. Top-Level Directory Structure

The root of the project will contain the CLI source code, stack configurations, and project metadata.

```
ollama-stack/
├── ollama_stack_cli/
├── docker-compose.yml
├── docker-compose.apple.yml
├── docker-compose.nvidia.yml
├── extensions/
├── install.sh
├── install.ps1
├── pyproject.toml
├── .ollama-stack.json
└── README.md
```

### 1.1. Component Responsibilities

- **`ollama_stack_cli/`**: The Python source package for the command-line tool.
- **`docker-compose.*.yml`**: The Docker Compose files that define the stack's services. These are considered static assets and are not modified by the CLI.
- **`extensions/`**: Directory containing all available extensions. The CLI reads from this directory but does not modify its contents.
- **`install.sh` / `install.ps1`**: Simplified installer scripts. Their sole responsibility is to verify the Python environment and run `pip install .`.
- **`pyproject.toml`**: The unified Python project definition file. It specifies build system requirements, project dependencies, and defines the `ollama-stack` console script entry point.
- **`.ollama-stack.json`**: A machine-readable file for storing the CLI's internal state, such as the list of enabled extensions.
- **`README.md`**: Project documentation, to be updated to reflect the new CLI tool and installation process.

## 2. Python Package Architecture (`ollama_stack_cli/`)

The source code is organized into modules with clear, single responsibilities.

```
ollama_stack_cli/
│
├── __init__.py
├── main.py
├── config.py
├── docker_client.py
├── schemas.py
│
└── commands/
    ├── __init__.py
    ├── start.py
    ├── stop.py
    ├── status.py
    └── extensions.py
```

### 2.1. Module Responsibilities

- **`main.py`**: The main entry point of the application. It uses `typer` to construct the CLI, register commands, and handle global options like `--verbose`. It is also responsible for executing pre-flight checks (e.g., loading configuration, verifying the Docker environment) before dispatching to a specific command.

- **`config.py`**: The interface for all persistent configuration and state.
    - **Reads/Writes `.ollama-stack.json`**: Manages the application's internal state.
    - **Reads/Writes `.env`**: Manages the environment variables required by Docker Compose. This is the only module that directly interacts with these files.

- **`docker_client.py`**: An abstraction layer over the Docker Engine.
    - It is the only module that imports and uses the `docker` Python SDK.
    - Provides high-level functions for managing the stack (e.g., `start_stack_services`, `get_stack_status`).
    - Hides the complexity of interacting with the Docker API from the command logic.

- **`schemas.py`**: Defines the data structures used throughout the application.
    - Contains dataclasses or Pydantic models for things like `StackService`, `Extension`, and the structure of `.ollama-stack.json`.
    - This centralizes data definitions and provides a single source of truth for the application's data model, avoiding the use of raw dictionaries.

- **`commands/`**: A Python sub-package containing the implementation for each CLI command.
    - Each file (e.g., `start.py`, `status.py`) contains a `typer` command function.
    - These functions are responsible for orchestrating calls to other modules (`config.py`, `docker_client.py`) to execute the command's logic. They contain minimal business logic themselves.

### 2.2. Internal Safety Mechanisms

The CLI tool implements several internal mechanisms to ensure safe operation and prevent conflicts:

1. **Operation State Management**
   - The `docker_client.py` module tracks operation state internally
   - Operations are atomic and can be rolled back if interrupted
   - State changes are verified before and after operations

2. **Concurrency Control**
   - The `docker_client.py` module implements internal locking
   - Prevents concurrent operations on the same resources
   - Automatically handles lock timeouts and cleanup

3. **Recovery Procedures**
   - Built-in recovery for common failure scenarios
   - Automatic rollback of partial operations
   - State verification and repair if needed
