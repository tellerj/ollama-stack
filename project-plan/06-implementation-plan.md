# 06: Implementation Plan

This document outlines the sequential, phased plan for implementing the `ollama-stack` CLI tool. Each phase represents a major milestone, and each step is an actionable, testable unit of work.

---

## Phase 1: Core Lifecycle Commands

**Goal:** Implement the fundamental commands for managing the core stack lifecycle: `start`, `stop`, and `restart`.

**Success Criteria:**
- CLI tool can be installed and run
- Core services can be started, stopped, and restarted reliably
- Platform-specific configurations are handled correctly
- Health checks verify service availability
- All operations are safe and recoverable
- Clear error messages guide users through issues

**Step 1.1: Project Setup**
- Create project structure:
  ```
  ollama-stack/
  ├── ollama_stack_cli/
  │   ├── __init__.py
  │   ├── main.py
  │   ├── config.py
  │   ├── docker_client.py
  │   └── schemas.py
  ├── tests/
  │   └── test_*.py
  ├── pyproject.toml
  └── README.md
  ```
- Define dependencies in `pyproject.toml`:
  - Runtime: typer, rich, docker, python-dotenv, pydantic
  - Development: pytest, pytest-mock
- Create development environment setup guide

**Step 1.2: Core Module Implementation**
- **`main.py`**:
  - Implement Typer app with global options
  - Add command structure for start/stop/restart
  - Implement logging setup
  - Add error handling middleware
  - Add platform detection and validation

- **`config.py`**:
  - Define configuration schema using Pydantic
  - Implement `.env` loading with defaults:
    - `PROJECT_NAME`: Generated from directory name
    - `WEBUI_SECRET_KEY`: Generated if not present
  - Implement `.ollama-stack.json` state management
  - Add configuration validation
  - Add platform-specific configuration handling

- **`docker_client.py`**:
  - Implement platform detection (cpu/nvidia/apple)
  - Add Docker Compose operations with error handling
  - Implement health check system:
    - HTTP endpoint polling for each service
    - Timeout handling
    - Retry logic
  - Add operation safety:
    - Atomic operations
    - State verification
    - Recovery procedures
  - Add platform-specific compose file selection

- **`schemas.py`**:
  - Define data models for:
    - Configuration
    - Service state
    - Health check results
    - Operation status
    - Platform configuration

**Step 1.3: Command Implementation**
- **`start` command**:
  - Platform detection and validation
  - Service startup sequence:
    1. Verify Docker daemon is running
    2. Check for existing stack
    3. Load platform-specific configuration
    4. Start services in correct order
    5. Perform health checks
  - Progress reporting with rich
  - Error handling and recovery
  - Apple platform warning for native Ollama

- **`stop` command**:
  - Graceful service shutdown sequence:
    1. Verify services are running
    2. Stop services in correct order
    3. Remove containers and networks
    4. Preserve volumes
  - State verification
  - Error handling

- **`restart` command**:
  - Stop with verification
  - Start with health checks
  - State consistency checks
  - Option passing between stop/start

**Step 1.4: Testing**
- **Unit Tests**:
  - Configuration loading and validation
  - Platform detection
  - Docker client operations
  - Health check system
  - Error handling
  - Service state management

- **Integration Tests**:
  - Full start/stop/restart cycle
  - Health check verification
  - Error recovery
  - State management
  - Platform-specific behavior

**Testable Outcomes:**
1. `ollama-stack start`:
   - Launches core services in correct order
   - Verifies health of all services
   - Reports success/failure clearly
   - Handles platform-specific requirements
2. `ollama-stack stop`:
   - Stops services gracefully
   - Cleans up resources properly
   - Preserves volumes
   - Verifies shutdown
3. `ollama-stack restart`:
   - Completes full cycle
   - Maintains state consistency
   - Verifies service health
   - Preserves configuration

**Extension Points:**
- Configuration schema for future options
- Health check system for additional services
- State management for extensions
- Error handling for new operations
- Platform-specific configurations

---

## Phase 2: State and Information Commands

**Goal:** Implement a consistent, user-friendly interface for monitoring and managing the Ollama stack, leveraging Docker's capabilities while adding stack-specific enhancements.

**Success Criteria:**
- Users can view comprehensive stack status with consistent formatting
- Users can access service logs with unified styling
- Users can verify Ollama-specific environment requirements
- All operations provide clear, consistently formatted feedback
- Error states are clearly reported in a unified style

**Step 2.1: Enhance Core Modules**
- **Update `docker_client.py`**:
  - Add Ollama-specific health checks:
    - Model loading status
    - API endpoint availability
    - WebUI connectivity
    - Extension compatibility
  - Add extension status tracking:
    - Enabled/disabled state
    - Running status
    - Compatibility checks
  - Add Docker data aggregation:
    - Container stats (using Docker's stats API)
    - Port mappings (using Docker's inspect)
    - Log streaming (using Docker's log API)
    - Resource usage (using Docker's stats)

- **Update `schemas.py`**:
  - Add `ServiceStatus` model:
    ```python
    class ServiceStatus:
        name: str
        status: str  # running, stopped, starting, etc.
        health: str  # healthy, unhealthy, starting, etc.
        ollama_health: Optional[Dict[str, str]]  # model status, API status, etc.
        ports: List[str]
        resources: ResourceUsage
        last_updated: datetime
    ```
  - Add `ResourceUsage` model:
    ```python
    class ResourceUsage:
        cpu_percent: float  # from Docker stats
        memory_usage: int   # from Docker stats
        memory_limit: int   # from Docker stats
        network_io: Dict[str, int]  # from Docker stats
    ```
  - Add `ExtensionStatus` model:
    ```python
    class ExtensionStatus:
        name: str
        enabled: bool
        running: bool
        compatible: bool
        last_checked: datetime
    ```
  - Add `EnvironmentCheck` model:
    ```python
    class EnvironmentCheck:
        name: str
        status: bool
        message: str
        required: bool
        fix_hint: Optional[str]
    ```

**Step 2.2: Implement Status Command**
- **Features**:
  - Ollama-specific health status
  - Extension status
  - Container status (using Docker's data)
  - Resource usage (using Docker's stats)
- **Options**:
  - `--json`: Output in JSON format
  - `--extensions`: Show only extension status
  - `--watch`: Continuously monitor status
- **Output Format**:
  ```
  Core Services:
  ┌────────────┬────────────┬────────────┬────────────┬────────────┐
  │ Service    │ Status     │ Health     │ Ollama     │ Resources  │
  ├────────────┼────────────┼────────────┼────────────┼────────────┤
  │ ollama     │ Running    │ Healthy    │ API: OK    │ 45% CPU    │
  │ webui      │ Running    │ Healthy    │ UI: OK     │ 30% CPU    │
  └────────────┴────────────┴────────────┴────────────┴────────────┘

  Extensions:
  ┌────────────┬────────────┬────────────┐
  │ Extension  │ Status     │ Compatible │
  ├────────────┼────────────┼────────────┤
  │ example    │ Running    │ Yes        │
  └────────────┴────────────┴────────────┘
  ```

**Step 2.3: Implement Logs Command**
- **Features**:
  - Stack-specific log aggregation
  - Extension log handling
  - Log viewing (using Docker's logs)
  - Consistent formatting
- **Options**:
  - `--service`: Filter by service
  - `--level`: Filter by log level
  - `--follow`: Stream logs in real-time
  - `--tail`: Show last N lines
  - `--since`: Show logs since timestamp
  - `--until`: Show logs until timestamp
- **Output Format**:
  ```
  [2024-03-14 10:15:23] [ollama] Starting service...
  [2024-03-14 10:15:24] [webui] Initializing UI...
  [2024-03-14 10:15:25] [mcp_proxy] Connection failed
  ```

**Step 2.4: Implement Check Command**
- **Checks**:
  - Ollama-specific requirements:
    - Model directory permissions
    - API port availability
    - WebUI port availability
    - Extension compatibility
  - Basic Docker requirements:
    - Docker daemon status
    - Docker Compose version
    - NVIDIA toolkit (if applicable)
    - Resource availability
- **Options**:
  - `--fix`: Attempt to fix issues
  - `--verbose`: Show detailed information
- **Output Format**:
  ```
  Ollama Stack Checks:
  ✓ Docker daemon running
  ✓ Docker Compose v2.0.0
  ✓ NVIDIA toolkit installed
  ✓ Model directory accessible
  ✓ Ports available
  ✓ Resources sufficient
  ✗ Extension compatibility (fix available)
  ```

**Step 2.5: Testing**
- **Unit Tests**:
  - Ollama health check logic
  - Extension status tracking
  - Environment validation
  - Error handling
  - Output formatting

- **Integration Tests**:
  - Full status reporting
  - Log access across services
  - Environment validation
  - Error recovery
  - Format consistency

**Testable Outcomes:**
1. `ollama-stack status`:
   - Shows Ollama-specific health
   - Reports extension status
   - Displays container info and resources
   - Maintains consistent formatting
2. `ollama-stack logs`:
   - Shows stack-specific logs
   - Handles extension logs
   - Uses Docker's log data
   - Maintains consistent formatting
3. `ollama-stack check`:
   - Validates Ollama requirements
   - Reports issues clearly
   - Suggests solutions
   - Attempts fixes when requested
   - Maintains consistent formatting

**Extension Points:**
- Additional Ollama health checks
- Extension compatibility checks
- Custom environment validations
- Additional output formatting options

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

### Phase 4: Backup and Migration

**Goal:** Implement robust backup, restore, and migration capabilities.

- **Step 4.1: Implement Backup System**
    - Create backup command structure
    - Implement configuration backup
    - Implement volume backup
    - Add backup verification

- **Step 4.2: Implement Restore System**
    - Create restore command structure
    - Implement configuration restore
    - Implement volume restore
    - Add restore verification

- **Step 4.3: Implement Migration System**
    - Create migration command structure
    - Implement version detection
    - Implement migration steps
    - Add migration verification

- **Step 4.4: Write Unit Tests**
    - Test backup creation and verification
    - Test restore procedures
    - Test migration steps
    - **Testable Outcome:** Users can backup, restore, and migrate their stack safely

---

## Phase 5: Extension Management

**Goal:** Implement the full lifecycle management for MCP extensions.

-   **Step 5.1: Define Schemas and Scan for Extensions:**
    -   Create an `Extension` data schema in `schemas.py`.
    -   Implement logic to scan the `extensions/` directory and parse `mcp-config.json` files.

-   **Step 5.2: Implement `extensions list`, `info`, `enable`, `disable`:**
    -   Implement the informational commands and the logic to modify `.ollama-stack.json`.

-   **Step 5.3: Implement `extensions start`, `stop`, and `restart`:**
    -   Add functions to `docker_client.py` to run Compose commands within an extension's directory.
    -   Wire up the subcommands.

-   **Step 5.4: Write Unit Tests:**
    -   Write unit tests for the extension discovery, parsing, and state-change logic.
    -   **Testable Outcome:** A user can `list`, `enable`, `start`, `stop`, and `disable` an extension.

---

## Phase 6: Finalization & Quality Assurance

**Goal:** Ensure the CLI is robust, has a polished user experience, and is ready for release.

-   **Step 6.1: Implement Logging:**
    -   Integrate `rich` with Python's `logging` module and the global `--verbose` flag.
    -   Ensure all user-facing messages are clear and consistent.

-   **Step 6.2: Write Integration Tests:**
    -   Write end-to-end tests for the primary user workflows (`start` -> `status` -> `stop`).
    -   Write an integration test for the full extension lifecycle.

-   **Step 6.3: Update `README.md`:**
    -   Replace the `README.md` content with instructions for the new Python CLI. 