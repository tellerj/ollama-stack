# 03: Command Specifications

This document defines the functional requirements for each command in the `ollama-stack` CLI. The specifications herein should guide the implementation of the `commands/` module.

---

## 1. Global Behavior and Pre-flight Checks

Before executing any command, the CLI application will perform a set of pre-flight checks to ensure the environment is valid.

1.  **Context Loading**: It will locate and load configuration from `.env` and `.ollama-stack.json` into a shared application context. If essential files are missing, it will proceed with sensible defaults.
2.  **Docker Check**: It will verify that the Docker daemon is running and accessible via the SDK. If not, it will exit with a clear error message.

---

## 2. Command Index

### 2.1. Core Lifecycle Commands
- `start`: Starts the core stack services.
- `stop`: Stops and removes the core stack's containers and network.
- `restart`: Restarts the core stack services.

### 2.2. State & Information Commands
- `status`: Displays comprehensive stack status with consistent formatting, including Ollama-specific health and resource usage.
- `logs`: Views logs from the core stack or a specific extension with unified styling and formatting.
- `check`: Verifies Ollama-specific environment requirements and basic Docker setup with consistent output formatting.

### 2.3. Resource Management Commands
- `update`: Pulls the latest Docker images for the stack and enabled extensions.
- `cleanup`: Removes orphaned or all stack-related Docker resources.
- `uninstall`: Decommissions the stack's Docker resources to prepare for tool removal.

### 2.4. Backup and Migration Commands
- `backup`: Create a backup of the current stack state and data.
- `restore`: Restore the stack from a backup.
- `migrate`: Migrate the stack to a new version or configuration.

### 2.5. Extension Management Commands
- `extensions`: A subcommand group for managing extensions.


---

## 3. Command Specifications

### `start`
- **Purpose**: Start the core Ollama Stack services (`ollama`, `webui`, `mcp_proxy`).
- **Options**:
    - `--platform [cpu|nvidia|apple]`: Specify platform configuration. Defaults to auto-detection.
    - `--update`: Pull the latest Docker images before starting.
- **Behavior**:
    1.  If the stack is already running, print the status and exit gracefully.
    2.  Detect the host platform if `--platform` is not specified. On the `apple` platform, display a warning that the native Ollama application must be running.
    3.  Ensure the `WEBUI_SECRET_KEY` is correctly managed for fresh vs. existing installations based on volume presence.
    4.  If `--update` is specified, pull the latest images for the core services.
    5.  Determine the correct set of Docker Compose files and start services in detached mode.
    6.  Perform health checks by polling service URLs, showing a progress indicator.
    7.  On success, print access point URLs. On failure, report the error.

### `stop`
- **Purpose**: Stop and remove the containers and network for the core stack.
- **Behavior**:
    1.  Detect the host platform to ensure the correct Docker Compose files are used.
    2.  Run the equivalent of `docker compose down`.
    3.  This command does **not** remove any Docker volumes.

### `restart`
- **Purpose**: Perform a graceful restart of the core stack.
- **Options**: Accepts all options from the `start` command (e.g., `--platform`).
- **Behavior**:
    1.  Execute the logic of the `stop` command.
    2.  Execute the logic of the `start` command, passing through any provided options.

---

## 3. State & Information Commands

### `status`
- **Purpose**: Provide a comprehensive, consistently formatted overview of the Ollama stack's status and health.
- **Options**:
    - `--json`: Output in JSON format
    - `--extensions`: Show only extension status
    - `--watch`: Continuously monitor status
- **Behavior**:
    1.  Identify the current installation context by reading the `PROJECT_NAME` from `.env`.
    2.  Find all Docker containers for the current installation. If none are running, display a helpful message for new users.
    3.  Display the status of core services with:
        - Ollama-specific health information
        - Container status (from Docker)
        - Resource usage (from Docker stats)
        - Port mappings (from Docker inspect)
    4.  Scan `extensions/` and `.ollama-stack.json` to determine the status of all extensions.
    5.  Display the status of all extensions with compatibility information.
    6.  Format all output consistently using rich tables and styling.

### `logs`
- **Purpose**: View logs from the core services or a specific extension with consistent formatting and styling.
- **Arguments**:
    - `service_or_extension_name`: (Optional) The name of a service or extension.
- **Options**:
    - `-f`, `--follow`: Follow the log output in real-time.
    - `--tail`: Show last N lines.
    - `--level`: Filter by log level.
    - `--since`: Show logs since timestamp.
    - `--until`: Show logs until timestamp.
- **Behavior**:
    1.  If `service_or_extension_name` is provided but does not match a known service or extension, exit with an error listing available targets.
    2.  If it matches an enabled extension, view logs from that extension's compose context.
    3.  Otherwise, view logs from the core stack's compose context.
    4.  Format logs consistently with:
        - Timestamps
        - Service names
        - Log levels
        - Consistent styling
    5.  Pass appropriate flags to the underlying Docker Compose command.

### `check`
- **Purpose**: Inspect the user's environment for Ollama-specific requirements and basic Docker setup with consistent output formatting.
- **Options**:
    - `--fix`: Attempt to fix issues where possible
    - `--verbose`: Show detailed information
- **Behavior**:
    1.  Check for Ollama-specific requirements:
        - Model directory permissions
        - API port availability
        - WebUI port availability
        - Extension compatibility
    2.  Check basic Docker requirements:
        - Docker daemon status
        - Docker Compose version
        - NVIDIA toolkit (if applicable)
        - Resource availability
    3.  Report the status of each check to the user in a clear, consistently formatted list.
    4.  If `--fix` is specified, attempt to fix any issues that can be automatically resolved.
    5.  Format all output consistently using rich styling.

---

## 4. Resource Management Commands

### `update`
- **Purpose**: Pull the latest Docker images for the core stack and all enabled extensions.
- **Behavior**:
    1.  Check if the stack is currently running. If so, prompt for confirmation, then execute the `stop` logic.
    2.  Pull the latest images for `ollama`, `open-webui`, and `mcpo`, displaying progress.
    3.  For each enabled extension, pull the images defined in its `docker-compose.yml`.
    4.  If the stack was running before the update, execute the `start` logic.
    5.  If the stack was not running, print a success message confirming which images were updated.

### `cleanup`
- **Purpose**: Remove Docker resources associated with any `ollama-stack` installation.
- **Options**:
    - `--remove-volumes`: Also remove core and extension Docker volumes (destructive).
    - `-f`, `--force`: Skip confirmation prompts.
- **Behavior**:
    1.  Find all Docker containers, networks, and volumes with the `ollama-stack.installation` label.
    2.  Prompt the user for confirmation unless `--force` is used.
    3.  Stop and remove all found containers and networks.
    4.  If `--remove-volumes` is specified, remove all found volumes.

### `uninstall`
- **Purpose**: Decommission all Docker resources to prepare for tool removal via `pip`.
- **Options**:
    - `--remove-volumes`: Also remove core and extension Docker volumes.
    - `-f`, `--force`: Skip confirmation prompts.
- **Behavior**:
    1.  Clearly warn the user that this is a destructive operation.
    2.  Execute the logic of the `cleanup` command with `--force`.
    3.  After successful resource removal, print a final message instructing the user to run `pip uninstall ollama-stack-cli`.

---

## 5. Backup and Migration Commands

### `backup`
- **Purpose**: Create a backup of the current stack state and data.
- **Options**:
    - `--include-volumes`: Also backup Docker volumes (default: false)
    - `--output`: Specify backup location (default: `./backups/<timestamp>`)
- **Behavior**:
    1. Create a backup of `.env` and `.ollama-stack.json`
    2. If `--include-volumes` is specified, backup relevant Docker volumes
    3. Create a manifest file listing all backed-up components
    4. Verify backup integrity
    5. Display backup location and size

### `restore`
- **Purpose**: Restore the stack from a backup.
- **Arguments**:
    - `backup_path`: Path to the backup directory
- **Options**:
    - `--include-volumes`: Also restore Docker volumes (default: false)
- **Behavior**:
    1. Verify backup integrity
    2. Stop running services if necessary
    3. Restore `.env` and `.ollama-stack.json`
    4. If `--include-volumes` is specified, restore Docker volumes
    5. Verify restored state
    6. Display success message with next steps

### `migrate`
- **Purpose**: Migrate the stack to a new version or configuration.
- **Options**:
    - `--version`: Target version to migrate to
    - `--backup`: Create backup before migration (default: true)
- **Behavior**:
    1. If `--backup` is true, create a backup
    2. Verify current state
    3. Apply version-specific migration steps
    4. Update configuration files
    5. Verify migrated state
    6. Display success message with next steps

---

## 6. Extension Management Commands

### `extensions`
- **Purpose**: A command group to manage the lifecycle of modular extensions.
- **Subcommands**: `list`, `info <name>`, `enable <name>`, `disable <name>`, `start <name>`, `stop <name>`, `restart <name>`.

### `extensions list`
- **Purpose**: Show the status of all available extensions.
- **Behavior**:
    1.  Scan the `extensions/` directory. If empty, print a message and exit.
    2.  For each extension, determine its status (enabled/disabled/running).
    3.  Display the results in a formatted table.

### `extensions info <name>`
- **Purpose**: Display the detailed configuration of a single extension.
- **Behavior**:
    1.  Validate that an extension with the given `<name>` exists.
    2.  Parse the `mcp-config.json` file from the extension's directory.
    3.  Display the contents in a clean, human-readable format.

### `extensions enable <name>`
- **Purpose**: Enable a disabled extension.
- **Behavior**:
    1.  Validate that an extension with the given `<name>` exists.
    2.  Add the extension's name to the `enabled_extensions` array in `.ollama-stack.json`.
    3.  Print a success message.

### `extensions disable <name>`
- **Purpose**: Disable an enabled extension.
- **Behavior**:
    1.  If the extension is running, automatically execute the `extensions stop <name>` logic first.
    2.  Remove the extension's name from the `enabled_extensions` array in `.ollama-stack.json`.
    3.  Print a success message.

### `extensions start <name>`
- **Purpose**: Start an enabled extension.
- **Behavior**:
    1.  Verify the extension is enabled in `.ollama-stack.json`.
    2.  Detect the host platform to select the correct compose file(s) from the extension's directory.
    3.  Start the extension's services in detached mode from its directory.

### `extensions stop <name>`
- **Purpose**: Stop a running extension.
- **Behavior**:
    1.  Run `docker compose down` from within the extension's directory. This removes the container and network but preserves the extension's volume.

### `extensions restart <name>`
- **Purpose**: Restart a running extension.
- **Behavior**:
    1.  Execute the `extensions stop <name>` logic.
    2.  Execute the `extensions start <name>` logic.
