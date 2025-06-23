# 06: Implementation Plan

This document outlines the sequential, phased plan for implementing the `ollama-stack` CLI tool. Each phase represents a major milestone, and each step is an actionable, testable unit of work.

---

## Phase 1: Core Lifecycle Commands

**Goal:** Implement the fundamental commands for managing the core stack lifecycle, leveraging Docker's capabilities while adding Ollama-specific functionality and consistent styling.

**Success Criteria:**
- CLI tool can be installed and run
- Core services can be started, stopped, and restarted reliably
- Platform-specific configurations are handled correctly
- Health checks verify service availability
- All operations are safe and recoverable
- Clear, consistently formatted error messages guide users through issues

**Step 1.1: Project Initialization and Onboarding**
- **Goal**: Prepare the repository for development by setting up tooling and creating contributor guides.
- **Tasks**:
    - Initialize `pyproject.toml` with project metadata and dependencies.
    - Configure `black` and `ruff` for code formatting and linting within `pyproject.toml`.
    - Create the `CONTRIBUTING.md` file with a comprehensive developer setup guide.
    - Create the `CHANGELOG.md` file.
    - Create the initial directory structure (`ollama_stack_cli/`, `tests/`).
  ```
  ollama-stack/
  ├── ollama_stack_cli/
  │   ├── __init__.py
  │   ├── main.py
  │   ├── context.py
  │   ├── config.py
  │   ├── display.py
  │   ├── docker_client.py
  │   └── schemas.py
  ├── tests/
  │   └── test_*.py
  ├── pyproject.toml
  └── README.md
  ```

**Step 1.2: Core Module Implementation**
- **`main.py`**:
  - Create and initialize a single `AppContext`.
  - Implement Typer app, passing the `AppContext` to all commands.
  - Handle global options like `--verbose`.

- **`context.py`**:
  - Define the `AppContext` class.
  - Initialize and hold the `Config` object.
  - Initialize and hold the `DockerClient` instance.
  - Initialize and hold the `Display` handler.

- **`display.py`**:
  - Create a `Display` class that abstracts `rich`.
  - Implement methods for all user-facing output (`success`, `error`, `table`, etc.).
  - This is the only module that imports `rich`.

- **`docker_client.py`**:
  - Implement platform detection (cpu/nvidia/apple).
  - Wrap Docker Compose operations for service management.
  - Implement Ollama-specific health checks.
  - Implement internal operation safety (locking, state management).

- **`schemas.py`**:
  - Define Pydantic models for configuration, state, and other data structures.

- **`config.py`**:
  - Implement loading of `.env` and `.ollama-stack.json`.
  - Handle default values and configuration validation.

**Step 1.3: Command Implementation**
- **Commands receive an `AppContext` (`ctx`)**.
- **`start` command**:
  - Use `ctx.docker_client` to perform platform detection and start services.
  - Use `ctx.display` for progress reporting and results.
- **`stop` command**:
  - Use `ctx.docker_client` to stop services.
  - Use `ctx.display` to report status.
- **`restart` command**:
  - Orchestrate `stop` and `start` logic through the `ctx.docker_client`.
  - Use `ctx.display` to report progress.

**Step 1.4: Testing**
- **Unit Tests**:
  - Test command logic by passing a mocked `AppContext`.
  - Test `docker_client` methods by mocking the Docker SDK.
  - Test configuration and schema validation.
- **Integration Tests**:
  - Test the full `start` -> `stop` -> `restart` lifecycle against a live Docker daemon.
  - Verify output formatting consistency.

**Testable Outcomes:**
1. `ollama-stack start`, `stop`, `restart` commands are fully functional.
2. All command output is consistently styled.
3. The `AppContext` is successfully used to manage application state and services.

---

## Phase 2: State and Information Commands

**Goal:** Implement a consistent, user-friendly interface for monitoring and managing the Ollama stack.

**Success Criteria:**
- Commands provide a comprehensive and consistently formatted overview of the stack.
- All output is styled through the `display` module.

**Step 2.1: Enhance Core Modules**
- **`docker_client.py`**:
  - Add methods to aggregate data from Docker (stats, inspect, logs).
  - Add methods for Ollama-specific health checks and extension status tracking.
- **`schemas.py`**:
  - Add Pydantic models for `ServiceStatus`, `ExtensionStatus`, `ResourceUsage`, etc.

**Step 2.2: Command Implementation**
- **Commands receive an `AppContext` (`ctx`)**.
- **`status` command**:
  - Call `ctx.docker_client.get_stack_status()`.
  - Pass the resulting data model to `ctx.display.status_table()`.
- **`logs` command**:
  - Use `ctx.docker_client` to stream logs.
  - Use `ctx.display` to format and print each log entry.
- **`check` command**:
  - Call `ctx.docker_client.run_environment_checks()`.
  - Pass the results to `ctx.display.check_report()`.

**Step 2.3: Testing**
- **Unit Tests**: Test logic for `get_stack_status`, etc., by mocking Docker SDK responses.
- **Integration Tests**: Verify the formatted output of `status`, `logs`, and `check` against a live stack.

**Testable Outcomes:**
1. `ollama-stack status`, `logs`, `check` commands are fully functional.
2. The CLI provides a rich, consistently styled view of the stack's state.

---

## Phase 3: Resource Management

**Goal:** Implement robust commands for managing the stack's underlying resources, with a focus on safety and adherence to the established architecture.

**Step 3.1: Enhance Core Modules (`stack_manager.py` and `docker_client.py`)**
-   **In `docker_client.py`**:
    -   Implement a method `find_resources_by_label(label: str)` that returns a list of all containers, networks, and volumes matching the given Docker label.
    -   Implement a method `remove_resources(resources: list, remove_volumes: bool)` that safely removes the provided resources.
    -   Ensure the `pull_images()` method can show progress.
-   **In `stack_manager.py`**:
    -   Implement an `update_stack()` method that orchestrates checking if the stack is running, stopping it if necessary, pulling images, and restarting.
    -   Implement `cleanup_resources(force: bool, remove_volumes: bool)` and `uninstall_stack(...)` methods that use the new `docker_client` methods to discover and remove resources, handling all user-facing prompts and warnings.

**Step 3.2: Command Implementation**
-   **`update` command**:
    -   Call `ctx.stack_manager.update_stack()`.
    -   Use `ctx.display` to report progress and results.
-   **`cleanup` and `uninstall` commands**:
    -   Call `ctx.stack_manager.cleanup_resources(...)` or `uninstall_stack(...)`, passing the appropriate flags from the CLI.
    -   Use `ctx.display` to present warnings and confirmation prompts.

**Step 3.3: Testing**
-   **Unit Tests**:
    -   Mock `docker_client` to test the orchestration logic in `stack_manager` (e.g., test that `update_stack` calls `stop` before `pull`).
    -   Mock the Docker SDK to test that `find_resources_by_label` correctly filters resources.
-   **Integration Tests**:
    -   Test that `update` pulls new images.
    -   Test that `cleanup` with `--remove-volumes` correctly removes all resources, and without it, preserves volumes.

**Testable Outcomes:**
1.  All resource management commands are fully functional and architecturally sound.
2.  The `cleanup` and `uninstall` commands include user safety prompts and respect the `--force` and `--remove-volumes` flags.
3.  The CLI can successfully find and manage only those Docker resources that are labeled as part of the stack.

---

## Phase 4: Backup and Migration

**Goal:** Implement robust backup, restore, and migration capabilities.

**Step 4.1: Enhance Core Modules**
- **`docker_client.py`**: Add methods for creating and restoring volume backups.
- **`config.py`**: Add methods for exporting and importing configuration files.

**Step 4.2: Command Implementation**
- **Commands receive an `AppContext` (`ctx`)**.
- **`backup` command**: Orchestrate calls to `ctx.docker_client` and `ctx.config`.
- **`restore` command**: Orchestrate calls to `ctx.docker_client` and `ctx.config`.
- **`migrate` command**: Implement version-specific migration logic.

**Step 4.3: Testing**
- **Unit Tests**: Test backup/restore logic by mocking file system and Docker volume operations.
- **Integration Tests**: Test a full backup and restore cycle.

**Testable Outcomes:**
1. `ollama-stack backup`, `restore`, `migrate` commands are fully functional.

---

## Phase 5: Extension Management

**Goal:** Implement the full lifecycle management for MCP extensions.

**Step 5.1: Enhance Core Modules**
- **`docker_client.py`**: Add methods to run Compose commands within an extension's directory.
- **`config.py`**: Add methods to manage the `enabled_extensions` list in `.ollama-stack.json`.
- **`schemas.py`**: Add `Extension` data schema.

**Step 5.2: Command Implementation**
- **Commands receive an `AppContext` (`ctx`)**.
- Implement all `extensions` subcommands by orchestrating calls to `ctx.docker_client` and `ctx.config`.
- Use `ctx.display` to show all extension-related information.

**Step 5.3: Testing**
- **Unit Tests**: Test extension discovery, parsing, and state-change logic.
- **Integration Tests**: Test the full `enable` -> `start` -> `stop` -> `disable` lifecycle for an extension.

**Testable Outcomes:**
1. All `ollama-stack extensions` subcommands are fully functional.

---

## Phase 6: Finalization & Quality Assurance

**Goal:** Ensure the CLI is robust, has a polished user experience, and is ready for release.

-   **Step 6.1: Refine `display.py`**:
    -   Ensure all user-facing messages are clear and consistent.
    -   Integrate `logging` with the `display` handler so the `--verbose` flag controls both `print` and `log` output.
-   **Step 6.2: Write Comprehensive Integration Tests**:
    -   Write end-to-end tests for the primary user workflows (`start` -> `status` -> `stop`).
    -   Write an integration test for the full extension lifecycle.
-   **Step 6.3: Update `README.md`**:
    -   Replace the `README.md` content with instructions for the new Python CLI.