# 03: Command Specifications

This document defines the functional requirements for each command in the `ollama-stack` CLI, based on the current v0.2.0 implementation and planned features.

---

## 1. Global Behavior and Pre-flight Checks

Before executing any command, the CLI application performs pre-flight checks to ensure environment validity:

1. **Context Loading**: Locates and loads configuration from `.env` and `.ollama-stack.json` into a shared application context. Proceeds with sensible defaults if essential files are missing.
2. **Docker Check**: Verifies Docker daemon availability via the SDK. Exits with clear error message if unavailable.

---

## 2. Command Index

### 2.1. Core Lifecycle Commands ✅ (Implemented)
- `start`: Starts the core stack services with platform detection and health verification
- `stop`: Stops and removes the core stack's containers and network
- `restart`: Restarts the core stack services with full option support

### 2.2. State & Information Commands ✅ (Implemented)
- `status`: Displays comprehensive stack status with unified health checking
- `logs`: Views logs from core services with consistent formatting
- `check`: Verifies environment requirements and Docker setup

### 2.3. Resource Management Commands 🔄 (Planned)
- `install`: Initialize fresh stack configuration and prepare environment
- `update`: Pulls the latest Docker images for the stack and enabled extensions
- `uninstall`: Clean up all stack resources (containers, networks, images, optionally volumes/config)
- *(Note: cleanup functionality integrated as `--remove-volumes` flag on uninstall)*

### 2.4. Backup and Migration Commands 🔄 (Planned)
- `backup`: Create a backup of the current stack state and data
- `restore`: Restore the stack from a backup
- `migrate`: Migrate the stack to a new version or configuration

### 2.5. Extension Management Commands 🔄 (Planned)
- `extensions`: A subcommand group for managing MCP extensions

---

## 3. Core Lifecycle Commands ✅

### `start`
- **Purpose**: Start the core Ollama Stack services (`ollama`, `open-webui`, `mcp-proxy`).
- **Options**:
    - `--platform [cpu|nvidia|apple]`: Specify platform configuration. Defaults to auto-detection.
    - `--update`: Pull latest Docker images before starting.
- **Behavior**:
    1. Check if stack is already running - if so, display status and exit gracefully
    2. Auto-detect host platform if `--platform` not specified. On Apple platform, warn that native Ollama must be running
    3. Generate `WEBUI_SECRET_KEY` for fresh installations or preserve existing for upgrades
    4. If `--update` specified, pull latest images for core services
    5. Select appropriate Docker Compose files and start services in detached mode
    6. Perform unified health checks using HTTP → TCP fallback, displaying progress
    7. On success, display access URLs. On failure, provide clear error messages

### `stop`
- **Purpose**: Stop and remove containers and network for the core stack.
- **Behavior**:
    1. Detect host platform to use correct Docker Compose files
    2. Execute `docker compose down` equivalent
    3. Preserve all Docker volumes (never removes user data)

### `restart` 
- **Purpose**: Perform graceful restart of the core stack.
- **Options**: Accepts all options from `start` command (`--platform`, `--update`).
- **Behavior**:
    1. Execute `stop` command logic
    2. Execute `start` command logic with provided options

---

## 4. State & Information Commands ✅

### `status`
- **Purpose**: Provide comprehensive, consistently formatted overview of stack status and health.
- **Options**:
    - `--json`: Output in JSON format for programmatic use
- **Behavior**:
    1. Read `PROJECT_NAME` from `.env` to identify installation context
    2. Find all Docker containers for current installation
    3. Display core service status with:
        - Unified health information (HTTP → TCP fallback)
        - Container status from Docker API
        - Port mappings and accessibility
        - Resource usage when available
    4. Show extension status from registry and enabled state
    5. Format output using rich tables with consistent styling
    6. If no containers running, display helpful getting-started message

### `logs`
- **Purpose**: View logs from core services with consistent formatting.
- **Arguments**:
    - `service_name`: (Optional) Specific service to view logs from
- **Options**:
    - `-f`, `--follow`: Follow log output in real-time
    - `--tail N`: Show last N lines (default: all)
- **Behavior**:
    1. If `service_name` provided, validate it exists in current stack
    2. Use Docker Compose to stream logs with appropriate filtering
    3. Format output with timestamps and service identification
    4. Pass follow/tail flags to underlying Docker Compose command
    5. Handle service not found with clear error and available options

### `check`
- **Purpose**: Validate environment requirements and configuration.
- **Behavior**:
    1. Check Docker daemon availability and version
    2. Verify Docker Compose plugin availability  
    3. Test port availability (11434, 8080, 8200)
    4. On Apple platforms, check for native Ollama installation
    5. On NVIDIA platforms, verify Container Toolkit if applicable
    6. Validate project configuration files
    7. Report all checks with clear pass/fail status using rich formatting
    8. Provide actionable guidance for any failures

---

## 5. Resource Management Commands 🔄

### `update`
- **Purpose**: Pull the latest Docker images for the core stack and all enabled extensions.
- **Options**:
    - `--services`: Only update core stack services (default: all)
    - `--extensions`: Only update enabled extensions
- **Behavior**:
    1. Check if the stack is currently running. If so, prompt for confirmation before stopping
    2. Stop the stack if running and user confirms
    3. Pull latest images for core services (`ollama`, `open-webui`, `mcp-proxy`) with progress display
    4. For each enabled extension, pull images defined in its Docker Compose files
    5. If the stack was running before update, restart it automatically
    6. Display summary of updated images and any failures
    7. Report final status and any next steps needed

### `uninstall`
- **Purpose**: Clean up all stack resources (containers, networks, images, and optionally volumes/config).
- **Options**:
    - `--remove-volumes`: Also remove Docker volumes (destroys models, conversations, databases)
    - `--remove-config`: Also remove configuration directory (`~/.ollama-stack/`)
    - `-a`, `--all`: Remove everything (equivalent to `--remove-volumes --remove-config`)
    - `--force`: Skip all confirmation prompts
- **Behavior**:
    1. If `--all` specified, enable both `--remove-volumes` and `--remove-config` flags
    2. Display warning about resource removal (escalated warning for `--remove-volumes` or `--all`)
    3. Find all Docker containers, networks, and images with stack labels
    4. Show summary of resources to be removed
    5. Prompt for confirmation unless `--force` is used
    6. Stop and remove all found containers and networks
    7. Remove Docker images for stack and extensions
    8. If `--remove-volumes` specified, remove all volumes with additional confirmation
    9. If `--remove-config` specified, remove `~/.ollama-stack/` directory
    10. Display completion message and note: "To remove CLI tool: `pip uninstall ollama-stack-cli`"

### `install`
- **Purpose**: Initialize fresh stack configuration and prepare environment for first use.
- **Options**:
    - `--force`: Overwrite existing configuration files without prompting
- **Behavior**:
    1. Check if configuration directory (`~/.ollama-stack/`) already exists
    2. If exists and not `--force`, prompt user whether to overwrite or preserve existing config
    3. Create `~/.ollama-stack/` directory structure
    4. Generate fresh `.env` file with default values (PROJECT_NAME, WEBUI_SECRET_KEY)
    5. Create default `.ollama-stack.json` with platform configurations and empty extensions
    6. Run environment checks (`check` command logic) to validate setup
    7. Display success message with next steps: "Run `ollama-stack start` to begin"

---

## 6. Backup and Migration Commands 🔄

### `backup`
- **Purpose**: Create a backup of the current stack state and data.
- **Options**:
    - `--include-volumes`: Also backup Docker volumes (default: false)
    - `--output PATH`: Specify backup location (default: `./backups/<timestamp>`)
    - `--compress`: Create compressed backup archive
- **Behavior**:
    1. Create backup directory structure
    2. Backup configuration files (`.env`, `.ollama-stack.json`)
    3. Export current Docker Compose configuration and service status
    4. If `--include-volumes` specified, create volume backups using Docker
    5. Create manifest file listing all backed-up components with checksums
    6. If `--compress` specified, create tar.gz archive
    7. Verify backup integrity by checking all files and checksums
    8. Display backup location, size, and verification status

### `restore`
- **Purpose**: Restore the stack from a backup.
- **Arguments**:
    - `backup_path`: Path to the backup directory or archive
- **Options**:
    - `--include-volumes`: Also restore Docker volumes (default: false)
    - `--force`: Overwrite existing configuration without prompting
- **Behavior**:
    1. Verify backup integrity using manifest and checksums
    2. Check for existing stack installation and warn about conflicts
    3. Stop running services if necessary
    4. Restore configuration files (`.env`, `.ollama-stack.json`)
    5. If `--include-volumes` specified, restore Docker volumes
    6. Verify restored configuration is valid
    7. Display success message with next steps (e.g., run `ollama-stack start`)

### `migrate`
- **Purpose**: Migrate the stack to a new version or configuration.
- **Arguments**:
    - `target_version`: Target version to migrate to (optional, defaults to latest)
- **Options**:
    - `--backup`: Create backup before migration (default: true)
    - `--dry-run`: Show what would be changed without making changes
- **Behavior**:
    1. Detect current stack version and configuration
    2. Determine migration path to target version
    3. If `--backup` is true, create automatic backup
    4. If `--dry-run`, display planned changes and exit
    5. Apply version-specific migration steps:
        - Update configuration file formats
        - Migrate Docker Compose configurations
        - Update extension registry and state
    6. Verify migrated state is valid and consistent
    7. Display migration summary and any manual steps required

---

## 7. Extension Management Commands 🔄

### `extensions`
- **Purpose**: A command group to manage the lifecycle of modular MCP extensions.
- **Subcommands**: `list`, `info <name>`, `enable <name>`, `disable <name>`, `start <name>`, `stop <name>`, `restart <name>`.

### `extensions list`
- **Purpose**: Show the status of all available extensions.
- **Options**:
    - `--enabled`: Show only enabled extensions
    - `--running`: Show only currently running extensions
- **Behavior**:
    1. Scan the `extensions/` directory and registry
    2. For each extension, determine its status (available/enabled/running)
    3. Display results in formatted table with extension details
    4. Show dependency information and compatibility status

### `extensions info <name>`
- **Purpose**: Display detailed configuration of a single extension.
- **Behavior**:
    1. Validate that extension exists in registry
    2. Parse extension configuration files (`mcp-config.json`, Docker Compose)
    3. Display comprehensive information: description, ports, dependencies, status
    4. Show installation and usage instructions

### `extensions enable <name>`
- **Purpose**: Enable a disabled extension.
- **Behavior**:
    1. Validate extension exists and is not already enabled
    2. Check extension dependencies and compatibility
    3. Add extension to enabled list in `.ollama-stack.json`
    4. Display success message and next steps

### `extensions disable <name>`
- **Purpose**: Disable an enabled extension.
- **Behavior**:
    1. Check if extension is currently running and stop if necessary
    2. Remove extension from enabled list in `.ollama-stack.json`
    3. Preserve extension data unless explicitly requested to remove
    4. Display success message

### `extensions start <name>`
- **Purpose**: Start an enabled extension.
- **Behavior**:
    1. Verify extension is enabled and not already running
    2. Check that core stack is running (extensions require it)
    3. Detect platform and use appropriate Docker Compose files
    4. Start extension services with health checking
    5. Display success message with access information

### `extensions stop <name>`
- **Purpose**: Stop a running extension.
- **Behavior**:
    1. Verify extension is currently running
    2. Stop extension services using Docker Compose
    3. Preserve extension volumes and data
    4. Display success message

### `extensions restart <name>`
- **Purpose**: Restart a running extension.
- **Behavior**:
    1. Execute `extensions stop <name>` logic
    2. Execute `extensions start <name>` logic
    3. Handle any configuration changes during restart

---

## 8. Command Output Standards

All commands follow consistent output standards:

### 8.1. Success States
- Use rich formatting with clear success indicators
- Display relevant URLs and next steps
- Show timing information for longer operations

### 8.2. Error Handling  
- Provide specific, actionable error messages
- Include relevant context (port conflicts, missing dependencies)
- Suggest concrete remediation steps

### 8.3. Progress Reporting
- Show progress spinners for health checks
- Display service status updates during operations
- Use consistent terminology across all commands

### 8.4. JSON Output
- `status --json` provides machine-readable output
- Structured data for programmatic integration
- Maintains same information as human-readable format 