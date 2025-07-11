# 04: Core Dependencies

This document specifies the primary Python libraries for this project, separated into runtime and development dependencies. All dependencies are managed in the `pyproject.toml` file.

**Dependency Stability**: The core dependencies listed below are sufficient for all planned implementation phases (v0.2.0 through v1.0.0). No additional runtime dependencies are anticipated for resource management, backup/migration, or extension management features.

---

## 1. Runtime Dependencies

These libraries are required for the CLI tool to function and are installed for end-users.

### 1.1. CLI Framework

- **`typer`**: The core framework for building the command-line interface.
    - **Justification**: Provides a modern, intuitive way to create commands, arguments, and options with type hints. Automatically generates help text and handles argument parsing.
- **`rich`**: A library for rich text and beautiful formatting in the terminal.
    - **Justification**: Used by `typer` for output and directly by our `display.py` module to render formatted tables, progress bars, and colored log messages, ensuring a clear and consistent cross-platform user experience.

### 1.2. Docker and Configuration

- **`docker`**: The official Python SDK for the Docker Engine API.
    - **Justification**: Enables robust, API-driven interaction with the Docker daemon, replacing fragile shell command parsing. This is the cornerstone of the tool's stability.
- **`python-dotenv`**: A library for managing environment variable configuration files.
    - **Justification**: Provides a simple and reliable interface for reading from and writing to the `.env` file, which configures the Docker Compose environment.

### 1.3. Data Modeling and Validation

- **`pydantic`**: A library for data validation and settings management using Python type annotations.
    - **Justification**: Essential for implementing our `schemas.py` module. Defines the expected structure of our `.ollama-stack.json` state file and other internal data structures. Provides clear, detailed errors when data doesn't conform to the schema, preventing runtime bugs.

---

## 2. Development Dependencies

These libraries are required for development activities like testing, formatting, and linting.

### 2.1. Testing Framework

- **`pytest`**: A mature, feature-rich testing framework.
    - **Justification**: The de facto standard for testing in the Python ecosystem. Provides a simple yet powerful way to write and organize our unit and integration tests.
- **`pytest-mock`**: A `pytest` plugin for simplifying the use of mock objects in tests.
    - **Justification**: Provides a clean fixture-based approach to "mocking" or simulating external services, like the Docker API. Essential for writing fast, reliable unit tests for our `docker_client.py` and command modules.

### 2.2. Code Quality Tools

- **`black`**: An uncompromising Python code formatter.
    - **Justification**: Provides deterministic, non-negotiable code formatting to ensure consistency across the codebase. Eliminates style debates and ensures uniform code appearance.
- **`ruff`**: An extremely fast Python linter and code analyzer.
    - **Justification**: Catches a wide range of potential bugs, style inconsistencies, and code quality issues. Combines multiple tools (flake8, isort, etc.) into a single, fast linter.

### 2.3. Development Status and Future Requirements

**Current Testing Status (v0.2.0):**
- ✅ 296 unit tests (100% pass rate)
- ✅ 11 integration tests (100% pass rate)  
- ✅ Comprehensive coverage of all core modules and command flows
- ✅ Automated testing pipeline ensures reliability

**Future Phase Testing (v0.3.0 - v1.0.0):**
- 🔄 **Phase 5**: Resource management testing (update, uninstall workflows)
- 🔄 **Phase 6**: Backup/migration testing (data integrity, version compatibility)
- 🔄 **Phase 7**: Extension management testing (lifecycle, dependencies)

**Dependency Stability**: Current testing dependencies are sufficient for all planned phases. The existing `pytest` and `pytest-mock` stack can handle the increased test complexity without additional tools. 