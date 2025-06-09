# 06: Implementation Plan

This document outlines the sequential, phased plan for implementing the `ollama-stack` CLI tool. Each phase represents a major milestone, and each step is an actionable, testable unit of work.

---

## Phase 1: Foundation & Core Service Lifecycle

**Goal:** Establish the basic CLI structure and implement the core commands required to start and stop the main stack.

-   **Step 1.1: Initialise `main.py` with Typer:**
    -   Create the main `Typer` app object and placeholder functions for all commands.
    -   Verify the `ollama-stack` entry point works (`pip install -e .`).

-   **Step 1.2: Implement Configuration Loading (`config.py`):**
    -   Implement functions to load `.env` and to read/write `.ollama-stack.json`.
    -   Handle missing files with sensible defaults.

-   **Step 1.3: Implement Docker Client Basics (`docker_client.py`):**
    -   Implement platform detection (CPU, Apple, Nvidia).
    -   Implement functions to run `docker compose up` and `docker compose down`.

-   **Step 1.4: Implement `start`, `stop`, and `restart` Commands:**
    -   Wire the command functions to call the `config` and `docker_client` modules.

-   **Step 1.5: Write Unit Tests:**
    -   Write `pytest` unit tests for `config.py` loading and default-handling.
    -   Write unit tests for `docker_client.py` platform detection, mocking the Docker SDK.
    -   **Testable Outcome:** `ollama-stack start` launches core services; `ollama-stack stop` terminates them.

---

## Phase 2: State, Information & Updates

**Goal:** Provide the user with visibility into the stack's status and the ability to manage it.

-   **Step 2.1: Enhance Docker Client for Queries:**
    -   Add functions to `docker_client.py` to get the status of stack containers.

-   **Step 2.2: Implement `status`, `logs`, and `check` Commands:**
    -   Implement logic to display service status, stream logs, and run environment checks.

-   **Step 2.3: Implement the `update` Command:**
    -   Implement logic to pull the latest Docker images for the core services.

-   **Step 2.4: Write Unit Tests:**
    -   Write unit tests for the Docker client query functions, mocking SDK responses.
    -   Write unit tests for the logic within the `check` command.
    -   **Testable Outcome:** `status`, `logs`, `check`, and `update` are all functional.

---

## Phase 3: Resource Management

**Goal:** Implement the safe and effective cleanup of all stack-related Docker resources.

-   **Step 3.1: Implement Resource Discovery:**
    -   Add functions to `docker_client.py` to find all resources (containers, networks, volumes) with the `ollama-stack.installation` label.

-   **Step 3.2: Implement `cleanup` and `uninstall` Commands:**
    -   Implement logic to remove discovered resources, checking for `--remove-volumes` and `--force`.
    -   The `uninstall` command will call `cleanup` and print the final instruction.

-   **Step 3.3: Write Unit Tests:**
    -   Write unit tests for the resource discovery functions, mocking SDK responses for tagged resources.
    -   **Testable Outcome:** `uninstall --remove-volumes` leaves no stack-related Docker resources on the system.

---

## Phase 4: Extension Management

**Goal:** Implement the full lifecycle management for MCP extensions.

-   **Step 4.1: Define Schemas and Scan for Extensions:**
    -   Create an `Extension` data schema in `schemas.py`.
    -   Implement logic to scan the `extensions/` directory and parse `mcp-config.json` files.

-   **Step 4.2: Implement `extensions list`, `info`, `enable`, `disable`:**
    -   Implement the informational commands and the logic to modify `.ollama-stack.json`.

-   **Step 4.3: Implement `extensions start`, `stop`, and `restart`:**
    -   Add functions to `docker_client.py` to run Compose commands within an extension's directory.
    -   Wire up the subcommands.

-   **Step 4.4: Write Unit Tests:**
    -   Write unit tests for the extension discovery, parsing, and state-change logic.
    -   **Testable Outcome:** A user can `list`, `enable`, `start`, `stop`, and `disable` an extension.

---

## Phase 5: Finalization & Quality Assurance

**Goal:** Ensure the CLI is robust, has a polished user experience, and is ready for release.

-   **Step 5.1: Implement Logging:**
    -   Integrate `rich` with Python's `logging` module and the global `--verbose` flag.
    -   Ensure all user-facing messages are clear and consistent.

-   **Step 5.2: Write Integration Tests:**
    -   Write end-to-end tests for the primary user workflows (`start` -> `status` -> `stop`).
    -   Write an integration test for the full extension lifecycle.

-   **Step 5.3: Update `README.md`:**
    -   Replace the `README.md` content with instructions for the new Python CLI. 