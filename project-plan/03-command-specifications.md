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
- `update`: Pulls the latest Docker images for the stack and enabled extensions.

### 2.2. State & Information Commands
- `status`: Displays the current status of the core stack and extensions.
- `logs`: Views logs from the core stack or a specific extension.
- `check`: Verifies the user's environment meets runtime requirements.

### 2.3. Resource Management Commands
- `extensions`: A subcommand group for managing extensions.
- `cleanup`: Removes orphaned or all stack-related Docker resources.
- `uninstall`: Decommissions the stack's Docker resources to prepare for tool removal.

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

### `update`
- **Purpose**: Pull the latest Docker images for the core stack and all enabled extensions.
- **Behavior**:
    1.  Check if the stack is currently running. If so, prompt for confirmation, then execute the `stop` logic.
    2.  Pull the latest images for `ollama`, `open-webui`, and `mcpo`, displaying progress.
    3.  For each enabled extension, pull the images defined in its `docker-compose.yml`.
    4.  If the stack was running before the update, execute the `start` logic.
    5.  If the stack was not running, print a success message confirming which images were updated.

### `status`
- **Purpose**: Provide a comprehensive, read-only overview of the state of the local Ollama Stack installation.
- **Behavior**:
    1.  Identify the current installation context by reading the `PROJECT_NAME` from `.env`.
    2.  Find all Docker containers for the current installation. If none are running, display a helpful message for new users (e.g., "Stack is not running. Use `ollama-stack start`.").
    3.  Display the status of core services in a formatted table (`Service Name`, `Status`, `Ports`).
    4.  Scan `extensions/` and `.ollama-stack.json` to determine the status of all extensions. If none exist, state this clearly.
    5.  Display the status of all extensions in a formatted table (`Extension Name`, `Status`, `Description`).
    6.  Identify and warn about any orphaned resources from other installations.

### `logs`
- **Purpose**: View logs from the core services or a specific extension.
- **Arguments**:
    - `service_or_extension_name`: (Optional) The name of a service or extension.
- **Options**:
    - `-f`, `--follow`: Follow the log output in real-time.
- **Behavior**:
    1.  If `service_or_extension_name` is provided but does not match a known service or extension, exit with an error listing available targets.
    2.  If it matches an enabled extension, view logs from that extension's compose context.
    3.  Otherwise, view logs from the core stack's compose context.
    4.  Pass the `--follow` flag to the underlying Docker Compose command.

### `check`
- **Purpose**: Inspect the user's environment to diagnose common issues and verify requirements.
- **Behavior**:
    1.  Check for the presence and version of the `docker compose` CLI plugin.
    2.  If on a Linux host, check for the presence of the NVIDIA Container Toolkit.
    3.  Report the status of each check to the user in a clear, formatted list.

### `extensions`
- **Purpose**: A command group to manage the lifecycle of modular extensions.
- **Subcommands**: `list`, `info <name>`, `enable <name>`, `disable <name>`, `start <name>`, `stop <name>`, `restart <name>`.
- **Note**: Detailed subcommand behavior is specified in the next section.

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

## 4. Command Group: `extensions` (Subcommand Specifications)

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