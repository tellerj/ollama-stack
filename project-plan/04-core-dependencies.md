# 02: Core Dependencies

This document specifies the primary Python libraries for this project, separated into runtime and development dependencies. All dependencies will be managed in the `pyproject.toml` file.

---

## 1. Runtime Dependencies

These libraries are required for the CLI tool to function and will be installed for the end-user.

### 1.1. CLI Framework

- **`typer`**: The core framework for building the command-line interface.
    - **Justification**: Provides a modern, intuitive way to create commands, arguments, and options with type hints. It automatically generates help text and handles argument parsing.
- **`rich`**: A library for rich text and beautiful formatting in the terminal.
    - **Justification**: Used by `typer` for its output. We will use it directly to render formatted tables, progress bars, and colored log messages, ensuring a clear and consistent cross-platform user experience.

### 1.2. Docker and Configuration

- **`docker`**: The official Python SDK for the Docker Engine API.
    - **Justification**: Enables robust, API-driven interaction with the Docker daemon, replacing fragile shell command parsing. This is the cornerstone of the tool's stability.
- **`python-dotenv`**: A library for managing environment variable configuration files.
    - **Justification**: Provides a simple and reliable interface for reading from and writing to the `.env` file, which is used to configure the Docker Compose environment.

### 1.3. Data Modeling and Validation

- **`pydantic`**: A library for data validation and settings management using Python type annotations.
    - **Justification**: The ideal tool for implementing our `schemas.py` module. It allows us to define the expected structure of our `.ollama-stack.json` state file and other internal data structures. It provides clear, detailed errors when data does not conform to the schema, preventing a wide class of runtime bugs.

---

## 2. Development Dependencies

These libraries are only required for development activities like testing and are not needed by the end-user.

- **`pytest`**: A mature, feature-rich testing framework.
    - **Justification**: The de facto standard for testing in the Python ecosystem. It provides a simple yet powerful way to write and organize our unit and integration tests.
- **`pytest-mock`**: A `pytest` plugin for simplifying the use of mock objects in tests.
    - **Justification**: Provides a clean fixture-based approach to "mocking" or simulating external services, like the Docker API. This is essential for writing fast, reliable unit tests for our `docker_client.py` and command modules. 